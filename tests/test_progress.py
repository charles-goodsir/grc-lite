from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from grc_lite.web.app import create_app
from grc_lite.web.progress import level_dirs, progress

TOKEN = "test-token-123"
AUTH = {"X-Grc-Token": TOKEN}


def grading(outcomes, tags=()):
    planted = [
        {"number": str(i), "gap": f"gap {i}", "result": o, "outcome": o}
        for i, o in enumerate(outcomes, 1)
    ]
    mistakes = [
        {"id": f"M-{i:02d}", "source": "s", "text": "t", "tag": t} for i, t in enumerate(tags, 1)
    ]
    return {"title": "g", "planted": planted, "mistakes": mistakes}


def make_level(root: Path, name: str, scope=True) -> Path:
    level = root / name
    level.mkdir()
    if scope:
        (level / "01-scope.md").write_text("# scope")
    (level / "answer-key.md").write_text("SEALED KEY")
    return level


def assessment(level: Path) -> Path:
    path = level / "my-work" / "assessment"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def levels(tmp_path):
    root = tmp_path / "levels"
    root.mkdir()
    make_level(root, "01-not-started")
    assessment(make_level(root, "02-working")).joinpath("criteria.yaml").write_text("[]")
    assessment(make_level(root, "03-submitted")).joinpath("submitted.yaml").write_text("sha256: x")
    graded = assessment(make_level(root, "04-graded"))
    (graded / "submitted.yaml").write_text("sha256: x")
    (graded / "grading.yaml").write_text(
        yaml.safe_dump(
            grading(
                ["caught", "rated_low", "missed", "caught"],
                ["missed gap", "wrong rating", "wrong rating"],
            )
        )
    )
    also = assessment(make_level(root, "05-graded"))
    (also / "grading.yaml").write_text(
        yaml.safe_dump(grading(["caught", "caught"], ["wrong rating"]))
    )
    make_level(root, "_archive", scope=False)
    (root / ".git").mkdir()
    return root


def by_name(result):
    return {lv["name"]: lv for lv in result["levels"]}


def test_statuses_and_scores(levels):
    result = progress(
        levels, levels / "01-not-started", levels / "01-not-started" / "my-work" / "assessment"
    )
    got = by_name(result)
    assert sorted(got) == ["01-not-started", "02-working", "03-submitted", "04-graded", "05-graded"]
    assert [got[n]["status"] for n in sorted(got)] == [
        "not started",
        "in progress",
        "submitted",
        "graded",
        "graded",
    ]
    assert got["04-graded"]["planted"] == {"total": 4, "caught": 3, "missed": 1, "rated_off": 1}
    assert got["04-graded"]["mistakes"] == {"missed gap": 1, "wrong rating": 2}
    assert got["01-not-started"]["current"] is True and got["02-working"]["current"] is False


def test_totals_add_up_across_graded_levels(levels):
    totals = progress(
        levels, levels / "02-working", levels / "02-working" / "my-work" / "assessment"
    )["totals"]
    assert totals == {
        "graded": 2,
        "planted": 6,
        "caught": 5,
        "mistakes": {"wrong rating": 3, "missed gap": 1},
    }


def test_the_served_level_uses_its_own_assessment_folder(levels, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "grading.yaml").write_text(yaml.safe_dump(grading(["caught"])))
    result = progress(levels, levels / "01-not-started", elsewhere)
    assert by_name(result)["01-not-started"]["status"] == "graded"


def test_a_level_outside_the_root_is_still_listed(levels, tmp_path):
    outside = make_level(tmp_path, "99-elsewhere")
    result = progress(levels, outside, outside / "my-work" / "assessment")
    assert by_name(result)["99-elsewhere"]["current"] is True


def test_only_real_level_folders_are_listed(levels, tmp_path):
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "01-scope.md").write_text("x")
    (levels / "linked").symlink_to(tmp_path / "outside")
    assert "linked" not in [p.name for p in level_dirs(levels)]
    assert "_archive" not in [p.name for p in level_dirs(levels)] and ".git" not in [
        p.name for p in level_dirs(levels)
    ]
    assert level_dirs(tmp_path / "missing") == []


def test_a_grading_file_that_is_a_link_is_not_followed(levels, tmp_path):
    secret = tmp_path / "secret.yaml"
    secret.write_text(
        yaml.safe_dump(grading(["caught"] * 5))
    )  # valid, so following the link would show as graded
    target = levels / "01-not-started" / "my-work" / "assessment"
    target.mkdir(parents=True)
    (target / "grading.yaml").symlink_to(secret)
    got = by_name(
        progress(levels, levels / "02-working", levels / "02-working" / "my-work" / "assessment")
    )
    assert got["01-not-started"]["status"] == "unreadable"
    assert "planted" not in got["01-not-started"]


@pytest.mark.parametrize(
    "content", ["{not: valid: yaml", "- just\n- a list\n", "title: x\nplanted: oops\n", "\xff\xfe"]
)
def test_unreadable_grading_is_reported_not_fatal(levels, content):
    path = levels / "01-not-started" / "my-work" / "assessment"
    path.mkdir(parents=True)
    (path / "grading.yaml").write_bytes(content.encode("latin-1"))
    got = by_name(
        progress(levels, levels / "02-working", levels / "02-working" / "my-work" / "assessment")
    )
    assert got["01-not-started"]["status"] == "unreadable" and got["01-not-started"]["error"]
    assert got["04-graded"]["status"] == "graded"  # one bad file does not hide the others


def test_an_oversized_grading_file_is_skipped(levels):
    path = levels / "01-not-started" / "my-work" / "assessment"
    path.mkdir(parents=True)
    (path / "grading.yaml").write_text("title: " + "x" * 1_000_001)
    got = by_name(
        progress(levels, levels / "02-working", levels / "02-working" / "my-work" / "assessment")
    )
    assert got["01-not-started"]["error"] == "grading.yaml is too large"


def test_other_files_are_never_read(levels, monkeypatch):
    opened = []
    real_read_text = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **k: (opened.append(self.name), real_read_text(self, *a, **k))[1],
    )
    progress(
        levels, levels / "01-not-started", levels / "01-not-started" / "my-work" / "assessment"
    )
    assert set(opened) <= {"grading.yaml"}  # no answer key, scope, data room or records


@pytest.fixture
def client(levels):
    level = levels / "04-graded"
    return TestClient(
        create_app(level, level / "my-work" / "assessment", token=TOKEN),
        base_url="http://127.0.0.1:8765",
    )


def test_endpoint_uses_the_parent_folder_by_default_and_needs_the_token(client, tmp_path):
    assert client.get("/api/progress").status_code == 401
    body = client.get("/api/progress", headers=AUTH).json()
    assert len(body["levels"]) == 5 and body["totals"]["graded"] == 2
    assert str(tmp_path) not in str(body)  # no absolute paths leak to the page


def test_levels_option_points_at_another_folder(levels, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    make_level(other, "10-only")
    level = levels / "04-graded"
    app = create_app(level, level / "my-work" / "assessment", token=TOKEN, levels=other)
    names = [
        lv["name"]
        for lv in TestClient(app, base_url="http://127.0.0.1:8765")
        .get("/api/progress", headers=AUTH)
        .json()["levels"]
    ]
    assert sorted(names) == ["04-graded", "10-only"]
