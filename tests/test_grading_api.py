import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from grc_lite.web.app import create_app

ROOT = Path(__file__).parent.parent
GRADING = (ROOT / "tests" / "fixtures" / "grading.md").read_text()
TOKEN = "test-token-123"
AUTH = {"X-Grc-Token": TOKEN}
JSON = {"X-Grc-Token": TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def level(tmp_path):
    root = tmp_path / "level"
    (root / "data-room").mkdir(parents=True)
    (root / "data-room" / "policy.md").write_text("# Policy\n\nSEALED-WORD appears nowhere here.\n")
    (root / "answer-key.md").write_text("The planted gap is SEALED-WORD.\n")
    (root / "graded").mkdir()
    (root / "graded" / "report.md").write_text("Graded: SEALED-GRADED\n")
    (root / "CLAUDE.md").write_text("grader rules")
    (root / "my-work").mkdir()
    (root / "my-work" / "notes.md").write_text("my work")
    return root


@pytest.fixture
def work(tmp_path):
    target = tmp_path / "assessment"
    shutil.copytree(ROOT / "data" / "example", target)
    return target


@pytest.fixture
def client(level, work):
    return TestClient(create_app(level, work, token=TOKEN), base_url="http://127.0.0.1:8765")


def grade(client, **extra):
    return client.post(
        "/api/grading", json={"text": GRADING, "name": "grading.md", **extra}, headers=JSON
    )


def submit(client):
    assert client.post("/api/submit", json={}, headers=JSON).status_code == 200


def key(client, path="answer-key.md"):
    return client.get("/api/file", params={"path": path}, headers=AUTH).status_code


def test_grading_needs_a_submitted_level(client):
    result = grade(client)
    assert result.status_code == 409 and "submit the level first" in result.json()["detail"]
    assert client.get("/api/grading", headers=AUTH).json()["graded"] is False


def test_grading_is_the_one_write_allowed_while_locked(client):
    submit(client)
    assert grade(client).status_code == 200
    blocked = client.put(
        "/api/notes", json={"path": "data-room/policy.md", "text": "x"}, headers=JSON
    )
    assert blocked.status_code == 423
    assert (
        client.post("/api/records/criteria", json={"fields": {}}, headers=JSON).status_code == 423
    )


def test_import_stores_structured_grading_and_the_original(client, work):
    submit(client)
    done = grade(client).json()
    assert [p["outcome"] for p in done["planted"]] == [
        "caught",
        "rated_low",
        "rated_high",
        "missed",
    ]
    assert len(done["mistakes"]) == 7 and done["sha256"] and done["source"] == "grading.md"
    stored = yaml.safe_load((work / "grading.yaml").read_text())
    assert stored["title"].startswith("Northwind")
    assert (work / "grading.md").read_text() == GRADING
    body = client.get("/api/grading", headers=AUTH).json()
    assert body["graded"] and body["revealed"] and "missed gap" in body["tags"]


def test_replacing_a_grading_needs_confirmation_and_keeps_your_tags(client):
    submit(client)
    grade(client)
    client.put("/api/grading/mistakes/M-07", json={"tag": "weak evidence selected"}, headers=JSON)
    assert grade(client).status_code == 409
    again = grade(client, replace=True).json()
    assert (
        next(m for m in again["mistakes"] if m["id"] == "M-07")["tag"] == "weak evidence selected"
    )


def test_tags_are_validated(client):
    submit(client)
    grade(client)
    ok = client.put("/api/grading/mistakes/M-01", json={"tag": "miscounted"}, headers=JSON)
    assert ok.status_code == 200
    assert next(m for m in ok.json()["mistakes"] if m["id"] == "M-01")["tag"] == "miscounted"
    assert (
        client.put("/api/grading/mistakes/M-01", json={"tag": "<b>x</b>"}, headers=JSON).status_code
        == 422
    )
    assert (
        client.put("/api/grading/mistakes/M-99", json={"tag": "other"}, headers=JSON).status_code
        == 404
    )
    assert (
        client.put("/api/grading/mistakes/..%2Fx", json={"tag": "other"}, headers=JSON).status_code
        == 404
    )


def test_bad_grading_files_are_refused(client):
    submit(client)
    junk = client.post("/api/grading", json={"text": "# notes\n\nnothing"}, headers=JSON)
    assert junk.status_code == 422 and "does not look like a grading file" in junk.json()["detail"]
    huge = client.post("/api/grading", json={"text": "x" * 1_000_001}, headers=JSON)
    assert huge.status_code == 422
    assert client.get("/api/grading", headers=AUTH).json()["graded"] is False


def test_grading_endpoints_need_the_token(client):
    assert client.get("/api/grading").status_code == 401
    assert client.post("/api/grading", json={"text": GRADING}).status_code == 401


def test_hostile_text_is_stored_as_plain_text(client):
    submit(client)
    body = grade(client).json()
    assert (
        "<script>alert(1)</script>" in body["added"][0]["text"]
    )  # kept verbatim; the page draws text only


def test_answer_key_and_graded_stay_sealed_until_graded(client):
    for path in ("answer-key.md", "graded/report.md"):
        assert key(client, path) == 404
    submit(client)
    assert key(client) == 404  # locked but not graded: still sealed
    grade(client)
    assert key(client) == 200 and key(client, "graded/report.md") == 200
    files = client.get("/api/files", headers=AUTH).json()["files"]
    assert "answer-key.md" in files and "graded/report.md" in files


def test_a_grading_file_alone_does_not_open_the_key(client, work):
    (work / "grading.yaml").write_text("title: fake\n")  # graded, but never submitted
    assert key(client) == 404


def test_reveal_never_opens_other_hidden_files_or_paths(client, tmp_path):
    submit(client)
    grade(client)
    for path in (
        "CLAUDE.md",
        "my-work/notes.md",
        "../outside.md",
        "graded/../../outside.md",
        "/etc/passwd",
    ):
        assert key(client, path) == 404
    (tmp_path / "level" / "graded" / "link.md").symlink_to(tmp_path / "level" / "CLAUDE.md")
    assert key(client, "graded/link.md") == 404  # a link from an opened folder to a hidden file


def test_search_sees_the_key_only_after_grading(client):
    def hits():
        return client.get("/api/search", params={"q": "SEALED-WORD"}, headers=AUTH).json()["hits"]

    assert [h["path"] for h in hits()] == ["data-room/policy.md"]
    submit(client)
    assert [h["path"] for h in hits()] == ["data-room/policy.md"]
    grade(client)
    assert sorted(h["path"] for h in hits()) == ["answer-key.md", "data-room/policy.md"]


def test_deleting_grading_yaml_seals_the_key_again(client, work):
    submit(client)
    grade(client)
    (work / "grading.yaml").unlink()
    assert key(client) == 404
