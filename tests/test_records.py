import pytest
import yaml
from fastapi.testclient import TestClient

from grc_lite.loader import load
from grc_lite.web.app import create_app

TOKEN = "test-token-123"
AUTH = {"X-Grc-Token": TOKEN}
JSON = {"X-Grc-Token": TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def work(tmp_path):
    return tmp_path / "assessment"


@pytest.fixture
def client(tmp_path, work):
    level = tmp_path / "level"
    level.mkdir()
    return TestClient(create_app(level, work, token=TOKEN), base_url="http://127.0.0.1:8765")


def post(client, kind, fields=None):
    return client.post(f"/api/records/{kind}", json={"fields": fields or {}}, headers=JSON)


def put(client, kind, ident, fields):
    return client.put(f"/api/records/{kind}/{ident}", json={"fields": fields}, headers=JSON)


def test_empty_assessment_has_no_records_and_no_problems(client, work):
    data = client.get("/api/records", headers=AUTH).json()
    assert data["problems"] == []
    assert data["meta"]["scale"] == 3
    assert all(data[k] == [] for k in ("criteria", "evidence", "findings", "requests", "risks"))
    assert not work.exists()  # reading never creates files


def test_new_blank_record_gets_an_id_and_shows_what_is_missing(client):
    body = post(client, "criteria").json()
    assert body["record"] == {"id": "C-01"}
    messages = {(p["id"], p["message"]) for p in body["problems"]}
    assert ("C-01", "source: Field required") in messages
    assert ("C-01", "rule: Field required") in messages


def test_completed_records_validate_and_the_cli_loader_reads_them(client, work):
    post(
        client,
        "evidence",
        {"date": "2026-03-02", "source": "export", "type": "system", "shows": "x"},
    )
    post(client, "criteria", {"source": "Policy 1", "rule": "Do it", "evidence": ["E-01"],
                              "result": "gap"})  # fmt: skip
    data = client.get("/api/records", headers=AUTH).json()
    assert data["problems"] == []
    loaded = load(work)  # the same loader `grc validate` uses
    assert loaded.criteria[0].evidence == ["E-01"]
    assert "date: 2026-03-02" in (work / "evidence.yaml").read_text()  # a real date, not a string


def test_update_replaces_fields_and_drops_empty_ones(client, work):
    post(client, "criteria", {"source": "a", "rule": "b", "evidence_needed": "c"})
    put(client, "criteria", "C-01", {"source": "a", "rule": "b2", "evidence_needed": ""})
    assert yaml.safe_load((work / "criteria.yaml").read_text()) == [
        {"id": "C-01", "source": "a", "rule": "b2"}
    ]


def test_ids_are_never_reused_after_delete(client):
    for _ in range(3):
        post(client, "criteria")
    for gone in ("C-03", "C-02"):
        assert client.delete(f"/api/records/criteria/{gone}", headers=JSON).status_code == 200
    left = client.get("/api/records", headers=AUTH).json()["criteria"]
    assert [r["id"] for r in left] == ["C-01"]  # the deletes really happened
    assert post(client, "criteria").json()["record"]["id"] == "C-04"  # C-03 stays retired


def test_counter_survives_a_hand_edited_file(client, work):
    post(client, "criteria")
    (work / "criteria.yaml").write_text("- {id: C-09, source: s, rule: r}\n")
    assert post(client, "criteria").json()["record"]["id"] == "C-10"


def test_selected_finding_needs_its_full_write_up(client):
    post(client, "findings", {"title": "t", "status": "selected", "strength": "weak",
                              "strength_reason": "r"})  # fmt: skip
    problems = client.get("/api/records", headers=AUTH).json()["problems"]
    assert any(
        "selected finding is missing" in p["message"] and p["id"] == "F-01" for p in problems
    )


def test_scores_are_checked_against_the_scale_and_lowering_it_clamps_them(client):
    risk = {"title": "t", "owner": "o", "likelihood": 5, "likelihood_reason": "l", "impact": 4,
            "impact_reason": "i", "treatment": "accept"}  # fmt: skip
    post(client, "risks", risk)
    scale3 = client.get("/api/records", headers=AUTH).json()["problems"]
    assert any("outside the 1-3 scale" in p["message"] for p in scale3)
    meta = {"name": "Demo", "scale": 5, "slots": 8}
    assert client.put("/api/meta", json=meta, headers=JSON).json()["problems"] == []
    meta["scale"] = 3
    data = client.put("/api/meta", json=meta, headers=JSON).json()
    assert (data["risks"][0]["likelihood"], data["risks"][0]["impact"]) == (3, 3)
    assert data["meta"]["counters"] == {"K": 1}  # counters survive a meta change


def test_bad_meta_is_refused(client):
    assert (
        client.put(
            "/api/meta", json={"name": "x", "scale": 4, "slots": 8}, headers=JSON
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/meta", json={"name": "x", "scale": 3, "slots": 0}, headers=JSON
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"bogus": "x"},  # unknown field
        {"rule": "x" * 20_001},  # too long
        {"evidence": "E-01"},  # should be a list
        {"rule": {"nested": "no"}},  # wrong shape
        {"rule": True},
    ],
)
def test_bad_fields_are_refused_and_nothing_is_written(client, work, fields):
    assert post(client, "criteria", fields).status_code == 422
    assert not (work / "criteria.yaml").exists()


def test_unknown_record_type_and_id(client, work):
    assert post(client, "../etc/passwd").status_code == 404
    assert post(client, "secrets").status_code == 404
    assert put(client, "criteria", "C-99", {}).status_code == 404
    assert client.delete("/api/records/criteria/C-99", headers=JSON).status_code == 404
    assert not work.exists()


def test_record_endpoints_need_the_token_and_json(client):
    assert client.get("/api/records").status_code == 401
    assert client.post("/api/records/criteria", json={"fields": {}}).status_code == 401
    wrong = {"X-Grc-Token": TOKEN, "Content-Type": "text/plain"}
    assert client.post("/api/records/criteria", content="{}", headers=wrong).status_code == 415


def test_text_is_stored_exactly_as_typed_not_interpreted(client, work):
    nasty = '<img src=x onerror="alert(1)"> {{7*7}} $(id) ; DROP TABLE'
    post(
        client, "evidence", {"date": "2026-03-02", "source": "s", "type": "system", "shows": nasty}
    )
    assert yaml.safe_load((work / "evidence.yaml").read_text())[0]["shows"] == nasty


def test_report_waits_for_a_valid_assessment(client):
    assert client.get("/api/report", headers=AUTH).json() == {"markdown": None, "problems": []}
    post(client, "criteria")  # blank, so invalid
    blocked = client.get("/api/report", headers=AUTH).json()
    assert blocked["markdown"] is None and blocked["problems"]
    put(client, "criteria", "C-01", {"source": "Policy", "rule": "Do it"})
    done = client.get("/api/report", headers=AUTH).json()
    assert done["problems"] == [] and "| C-01 | Policy | Do it |" in done["markdown"]


def test_concurrent_creates_get_distinct_ids(client):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda _: post(client, "criteria").json()["record"]["id"], range(16)))
    assert len(set(ids)) == 16
