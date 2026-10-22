from datetime import date

import pytest
from fastapi.testclient import TestClient

from grc_lite.coverage import coverage
from grc_lite.web.app import create_app

TOKEN = "test-token-123"
AUTH = {"X-Grc-Token": TOKEN}
JSON = {"X-Grc-Token": TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def client(tmp_path):
    level = tmp_path / "level"
    (level / "data-room").mkdir(parents=True)
    (level / "data-room" / "policy.md").write_text(
        "# Policy\n\nLeavers must be disabled within 24 hours.\n"
    )
    (level / "answer-key.md").write_text("The planted gap is LEAVERS-SECRET.\n")
    (level / "graded").mkdir()
    (level / "graded" / "grades.md").write_text("LEAVERS-GRADED\n")
    (tmp_path / "outside.md").write_text("LEAVERS-OUTSIDE\n")
    (level / "data-room" / "link.md").symlink_to(tmp_path / "outside.md")
    return TestClient(
        create_app(level, tmp_path / "work", token=TOKEN), base_url="http://127.0.0.1:8765"
    )


def search(client, q):
    return client.get("/api/search", params={"q": q}, headers=AUTH)


def test_search_finds_files_notes_and_records_ignoring_case(client):
    client.put(
        "/api/notes",
        json={"path": "data-room/policy.md", "text": "ask about LEAVERS list"},
        headers=JSON,
    )
    client.post(
        "/api/records/evidence",
        json={"fields": {"shows": "Three leavers still enabled"}},
        headers=JSON,
    )
    hits = search(client, "leavers").json()["hits"]
    kinds = sorted(h["kind"] for h in hits)
    assert kinds == ["file", "note", "record"]
    file_hit = next(h for h in hits if h["kind"] == "file")
    assert file_hit["path"] == "data-room/policy.md" and file_hit["line"] == 3
    record_hit = next(h for h in hits if h["kind"] == "record")
    assert (record_hit["record"], record_hit["id"], record_hit["field"]) == (
        "evidence",
        "E-01",
        "shows",
    )


def test_search_never_reaches_sealed_or_outside_files(client):
    for query in ("LEAVERS-SECRET", "LEAVERS-GRADED", "LEAVERS-OUTSIDE", "planted gap"):
        assert search(client, query).json()["hits"] == []


def test_search_query_limits_and_token(client):
    assert search(client, "a").status_code == 422
    assert search(client, "x" * 101).status_code == 422
    assert client.get("/api/search", params={"q": "leavers"}).status_code == 401


def test_search_treats_the_query_as_plain_text(client):
    assert search(client, ".*").json()["hits"] == []
    assert search(client, "((").status_code == 200  # would be a regex error if it were a pattern


def test_search_results_are_capped(client, tmp_path):
    (tmp_path / "level" / "many.txt").write_text("\n".join(f"match {n}" for n in range(300)))
    body = search(client, "match").json()
    assert len(body["hits"]) == 100 and body["truncated"] is True


def test_snippets_are_short_and_plain_text(client, tmp_path):
    (tmp_path / "level" / "long.txt").write_text(
        "x" * 500 + " NEEDLE <img src=x onerror=1> " + "y" * 500
    )
    hit = search(client, "needle").json()["hits"][0]
    assert len(hit["snippet"]) < 200 and "NEEDLE" in hit["snippet"]


TODAY = date(2026, 3, 10)


def test_coverage_finds_the_thin_spots():
    data = {
        "criteria": [
            {"id": "C-01", "result": "gap", "evidence": ["E-01"]},
            {"id": "C-02", "result": "gap"},
            {"id": "C-03"},
        ],
        "evidence": [{"id": "E-01"}, {"id": "E-02"}, {"id": "E-03"}],
        "findings": [
            {"id": "F-01", "status": "selected", "strength": "weak", "criteria": ["C-01"]},
            {"id": "F-02", "status": "dropped", "criteria": ["C-02"]},
            {"id": "F-03", "status": "candidate"},
            {"id": "F-04", "status": "selected", "strength": "strong", "criteria": ["C-01"]},
        ],
        "requests": [
            {"id": "R-01", "asked": date(2026, 3, 1), "what": "reviews"},
            {"id": "R-02", "asked": "2026-03-02", "received": "2026-03-05", "evidence": "E-02"},
        ],
    }
    result = coverage(data, TODAY)
    assert result["criteria_without_evidence"] == ["C-02", "C-03"]
    assert result["not_tested"] == ["C-03"]
    assert result["evidence_unlinked"] == ["E-03"]  # E-02 is linked through a request
    assert result["gaps_without_finding"] == ["C-02"]  # its only finding was dropped
    assert result["weak_selected"] == ["F-01"]
    assert result["undecided"] == ["F-03"]
    assert result["outstanding_requests"] == [
        {"id": "R-01", "what": "reviews", "asked": "2026-03-01", "days": 9}
    ]
    assert result["matrix"]["links"] == [["C-01", "E-01"]]


def test_coverage_of_nothing_is_empty():
    result = coverage({}, TODAY)
    assert all(
        result[k] == [] for k in ("criteria_without_evidence", "not_tested", "weak_selected")
    )


def test_coverage_endpoint(client):
    client.post(
        "/api/records/criteria", json={"fields": {"source": "s", "rule": "r"}}, headers=JSON
    )
    body = client.get("/api/coverage", headers=AUTH).json()
    assert body["criteria_without_evidence"] == ["C-01"] and body["not_tested"] == ["C-01"]
    assert client.get("/api/coverage").status_code == 401
