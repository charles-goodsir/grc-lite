import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from grc_lite.cli import app
from grc_lite.idcheck import GitError, find_reuse

runner = CliRunner()
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}  # fmt: skip


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=ENV,
                          capture_output=True, text=True, check=True)  # fmt: skip
    return done.stdout


def records(*ids: str, prefix="C") -> str:
    return "".join(f"- {{id: {prefix}-{i}, source: s, rule: r}}\n" for i in ids) or "[]\n"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    return root


def save(repo, text, name="criteria.yaml", message="change", sub=""):
    folder = repo / sub if sub else repo
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def test_adding_and_deleting_without_reuse_passes(repo):
    save(repo, records("01", "02"))
    save(repo, records("01"))
    save(repo, records("01", "03"))  # a new number, not the deleted one
    reused, warnings, commits = find_reuse(repo)
    assert reused == [] and warnings == [] and commits == 3


def test_a_deleted_id_that_comes_back_is_found(repo):
    save(repo, records("01", "02"))
    save(repo, records("01"))
    save(repo, records("01", "02"))
    [r] = find_reuse(repo)[0]
    assert (r.id, r.kind) == ("C-02", "criteria")
    assert len({r.first_seen, r.deleted_in, r.returned_in}) == 3  # three different commits


def test_reuse_in_the_uncommitted_working_tree_is_found(repo):
    save(repo, records("01", "02"))
    save(repo, records("01"))
    (repo / "criteria.yaml").write_text(records("01", "02"))  # not committed yet
    [r] = find_reuse(repo)[0]
    assert r.id == "C-02" and r.returned_in == "working tree"


def test_a_records_file_deleted_and_recreated_is_found(repo):
    save(repo, records("01"))
    git(repo, "rm", "-q", "criteria.yaml")
    git(repo, "commit", "-q", "-m", "remove")
    save(repo, records("01"), message="recreate")
    assert [r.id for r in find_reuse(repo)[0]] == ["C-01"]


def test_editing_a_record_is_not_reuse(repo):
    save(repo, records("01"))
    (repo / "criteria.yaml").write_text("- {id: C-01, source: changed, rule: changed too}\n")
    assert find_reuse(repo)[0] == []


def test_each_kind_is_checked_on_its_own(repo):
    save(repo, records("01", "02", prefix="E"), name="evidence.yaml")
    save(repo, records("01", prefix="E"), name="evidence.yaml")
    save(repo, records("02", prefix="E"), name="evidence.yaml")
    assert [(r.kind, r.id) for r in find_reuse(repo)[0]] == [("evidence", "E-02")]


def test_an_assessment_folder_inside_a_repository_with_spaces_in_the_path(repo):
    save(repo, records("01", "02"), sub="data/my assessment")
    save(repo, records("01"), sub="data/my assessment")
    save(repo, records("01", "02"), sub="data/my assessment")
    assert [r.id for r in find_reuse(repo / "data" / "my assessment")[0]] == ["C-02"]


def test_nothing_committed_yet_is_not_an_error(repo):
    (repo / "criteria.yaml").write_text(records("01"))
    assert find_reuse(repo) == ([], [], 0)


def test_an_unreadable_old_version_is_skipped_with_a_warning(repo):
    save(repo, "{not: valid: yaml")
    save(repo, records("01"))
    reused, warnings, _ = find_reuse(repo)
    assert reused == [] and len(warnings) == 1 and "could not be read" in warnings[0]


def test_outside_a_repository_is_an_error(tmp_path):
    with pytest.raises(GitError):
        find_reuse(tmp_path)


def test_a_shallow_clone_warns_that_history_is_missing(repo, tmp_path):
    save(repo, records("01"))
    save(repo, records("01", "02"))
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(clone)],
        check=True,
        env=ENV,
        capture_output=True,
    )
    _, warnings, _ = find_reuse(clone)
    assert any("shallow" in w for w in warnings)


def test_command_exit_codes_and_messages(repo, tmp_path):
    save(repo, records("01", "02"))
    save(repo, records("01"))
    clean = runner.invoke(app, ["check-ids", str(repo)])
    assert clean.exit_code == 0 and "No reused IDs" in clean.output
    save(repo, records("01", "02"))
    bad = runner.invoke(app, ["check-ids", str(repo)])
    assert (
        bad.exit_code == 1 and "C-02 (criteria)" in bad.output and "deliberate revert" in bad.output
    )
    nowhere = runner.invoke(app, ["check-ids", str(tmp_path)])
    assert nowhere.exit_code == 2


def test_the_example_assessment_in_this_repository_has_no_reuse():
    reused, _, _ = find_reuse(Path(__file__).parent.parent / "data" / "example")
    assert reused == []
