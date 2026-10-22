import pytest
from fastapi.testclient import TestClient

from grc_lite.web.app import create_app

TOKEN = "test-token-123"
AUTH = {"X-Grc-Token": TOKEN}
JSON = {"X-Grc-Token": TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def level(tmp_path):
    root = tmp_path / "level"
    (root / "data-room").mkdir(parents=True)
    (root / "data-room" / "policy.md").write_text("# Policy\n\nRule 1.\n")
    (root / "data-room" / "users.csv").write_text("name,mfa\nann,yes\nbob,\n")
    (root / "01-scope.md").write_text("# Scope\n")
    (root / "answer-key.md").write_text("SECRET KEY")
    (root / "data-room" / "answer-key-notes.txt").write_text("SECRET KEY")
    (root / "graded").mkdir()
    (root / "graded" / "feedback.md").write_text("SECRET GRADES")
    (root / "CLAUDE.md").write_text("grader instructions")
    (root / "my-work").mkdir()
    (root / "my-work" / "notes.md").write_text("my own notes")
    (root / "data-room" / ".hidden.md").write_text("dotfile")
    (root / "data-room" / "image.png").write_bytes(b"png")
    (tmp_path / "outside.md").write_text("OUTSIDE SECRET")
    return root


@pytest.fixture
def client(level, tmp_path):
    app = create_app(level, tmp_path / "assessment", token=TOKEN)
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_lists_only_study_files(client):
    files = client.get("/api/files", headers=AUTH).json()["files"]
    assert files == ["01-scope.md", "data-room/policy.md", "data-room/users.csv"]


def test_reads_a_file(client):
    body = client.get("/api/file", params={"path": "data-room/users.csv"}, headers=AUTH).json()
    assert body["kind"] == "csv"
    assert body["text"].startswith("name,mfa")


@pytest.mark.parametrize(
    "path",
    [
        "answer-key.md",
        "data-room/answer-key-notes.txt",
        "graded/feedback.md",
        "my-work/notes.md",
        "CLAUDE.md",
        "data-room/.hidden.md",
        "data-room/image.png",
        "data-room",
    ],
)
def test_hidden_and_unsupported_files_are_404(client, path):
    assert client.get("/api/file", params={"path": path}, headers=AUTH).status_code == 404


@pytest.mark.parametrize(
    "path",
    ["../outside.md", "data-room/../../outside.md", "/etc/passwd", "..\\outside.md", "a\0b.md", ""],
)
def test_paths_cannot_leave_the_level_folder(client, path):
    assert client.get("/api/file", params={"path": path}, headers=AUTH).status_code == 404


def test_symlinks_cannot_reach_outside_or_hidden_files(client, level, tmp_path):
    (level / "data-room" / "escape.md").symlink_to(tmp_path / "outside.md")
    (level / "data-room" / "key-link.md").symlink_to(level / "answer-key.md")
    assert "data-room/escape.md" not in client.get("/api/files", headers=AUTH).json()["files"]
    for path in ("data-room/escape.md", "data-room/key-link.md"):
        assert client.get("/api/file", params={"path": path}, headers=AUTH).status_code == 404


def test_every_api_call_needs_the_token(client):
    assert client.get("/api/files").status_code == 401
    assert client.get("/api/files", headers={"X-Grc-Token": "wrong"}).status_code == 401
    assert client.put("/api/notes", json={"path": "01-scope.md", "text": "x"}).status_code == 401


def test_non_ascii_token_is_rejected_not_a_crash(client):
    # compare_digest raises on non-ASCII str; we compare bytes, so this is a clean 401
    assert client.get("/api/files", headers={"X-Grc-Token": "tökén".encode()}).status_code == 401


def test_requests_for_another_host_are_refused(level, tmp_path):
    app = create_app(level, tmp_path / "a", token=TOKEN)
    evil = TestClient(app, base_url="http://evil.example")  # what DNS rebinding looks like
    assert evil.get("/", headers=AUTH).status_code == 400
    assert evil.get("/api/files", headers=AUTH).status_code == 400


def test_writes_must_be_json(client):
    wrong = {"X-Grc-Token": TOKEN, "Content-Type": "text/plain"}  # a cross-site form can send this
    result = client.put("/api/notes", content='{"path":"01-scope.md","text":"x"}', headers=wrong)
    assert result.status_code == 415


def test_notes_round_trip_and_stay_inside_the_assessment_folder(client, level, tmp_path):
    body = {"path": "data-room/policy.md", "text": "my note"}
    assert client.put("/api/notes", json=body, headers=JSON).status_code == 200
    assert client.get("/api/notes", params={"path": body["path"]}, headers=AUTH).json() == {
        "text": "my note"
    }
    saved = tmp_path / "assessment" / "notes" / "data-room__policy.md.md"
    assert saved.read_text() == "my note"
    assert client.get("/api/notes-index", headers=AUTH).json() == {"paths": [body["path"]]}
    assert not list(level.rglob("*.tmp")) and not list(level.rglob("*policy.md.md"))


def test_clearing_a_note_removes_the_file(client, tmp_path):
    body = {"path": "01-scope.md", "text": "x"}
    client.put("/api/notes", json=body, headers=JSON)
    client.put("/api/notes", json={**body, "text": "  "}, headers=JSON)
    assert not (tmp_path / "assessment" / "notes" / "01-scope.md.md").exists()


@pytest.mark.parametrize("path", ["answer-key.md", "../outside.md", "graded/feedback.md"])
def test_cannot_write_notes_for_hidden_or_outside_files(client, tmp_path, path):
    result = client.put("/api/notes", json={"path": path, "text": "x"}, headers=JSON)
    assert result.status_code == 404
    assert not (tmp_path / "assessment").exists()


def test_note_size_is_limited(client):
    body = {"path": "01-scope.md", "text": "x" * 200_001}
    assert client.put("/api/notes", json=body, headers=JSON).status_code == 422


def test_security_headers_and_no_cors(client):
    response = client.get("/")
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers
    preflight = client.options(
        "/api/notes",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_page_embeds_the_token_and_no_inline_script(client):
    page = client.get("/").text
    assert f'content="{TOKEN}"' in page
    assert "__TOKEN__" not in page
    assert "<script>" not in page and "onclick=" not in page


def test_no_api_docs_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
