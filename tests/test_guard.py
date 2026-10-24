import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from grc_lite.cli import app

runner = CliRunner()
NAME = "Zanzibar Holdings"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}  # fmt: skip


def git(repo, *args, env=None, check=True):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env or ENV,
                          capture_output=True, text=True, check=check)  # fmt: skip


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def denylist(tmp_path):
    path = tmp_path / "private" / "denylist.txt"
    path.parent.mkdir()
    path.write_text(f"# real clients, never commit this file\n\nAcme Real Client\n{NAME}\n")
    return path


def guard(*args, denylist=None):
    extra = ["--denylist", str(denylist)] if denylist else []
    return runner.invoke(app, ["guard-names", *args, *extra])


def test_a_clean_file_passes(repo, denylist):
    (repo / "a.md").write_text("Fictional Corp reviewed its policies.\n")
    result = guard(str(repo / "a.md"), denylist=denylist)
    assert result.exit_code == 0 and "No deny-listed names found (2 entries)" in result.output


def test_a_match_is_reported_by_file_line_and_entry_but_never_by_name(repo, denylist):
    (repo / "a.md").write_text(f"clean line\nWe tested {NAME.upper()} last week.\n")
    result = guard(str(repo / "a.md"), denylist=denylist)
    assert result.exit_code == 1
    assert "a.md:2: matches deny-list entry 2" in result.output
    assert NAME.lower() not in result.output.lower() and "zanzibar" not in result.output.lower()


def test_a_file_name_that_contains_a_name_is_caught(repo, denylist):
    (repo / "notes-acme-real-client.md").write_text("harmless text\n")
    result = guard(str(repo), denylist=denylist)
    assert result.exit_code == 1 and "(file name)" in result.output


def test_folders_are_scanned_but_git_internals_and_collected_are_not(repo, denylist):
    (repo / "docs").mkdir()
    (repo / "docs" / "x.md").write_text(f"{NAME}\n")
    (repo / "collected").mkdir()
    (repo / "collected" / "y.json").write_text(f"{NAME}\n")
    result = guard(str(repo), denylist=denylist)
    assert result.exit_code == 1
    assert "docs/x.md:1" in result.output and "collected" not in result.output


def test_entries_are_plain_text_not_patterns(repo, tmp_path):
    path = tmp_path / "private" / "d.txt"
    path.parent.mkdir()
    path.write_text(".*\n")
    (repo / "a.md").write_text("nothing special here\n")
    assert guard(str(repo / "a.md"), denylist=path).exit_code == 0
    (repo / "b.md").write_text("literally .* in the text\n")
    assert guard(str(repo / "b.md"), denylist=path).exit_code == 1


def test_binary_and_huge_files_are_skipped_with_a_note(repo, denylist):
    (repo / "bin.dat").write_bytes(b"\0\0" + NAME.encode())
    (repo / "big.txt").write_text(NAME + " " + "x" * 2_100_000)
    result = guard(str(repo / "bin.dat"), str(repo / "big.txt"), denylist=denylist)
    assert (
        result.exit_code == 0 and "2 binary or very large file(s) were not scanned" in result.output
    )


def test_links_are_not_followed(repo, denylist, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text(f"{NAME}\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "link.md").symlink_to(outside)
    assert guard(str(repo / "docs"), denylist=denylist).exit_code == 0


@pytest.mark.parametrize("content", [None, "", "# only a comment\n\n   \n"])
def test_a_missing_or_empty_list_fails_closed_never_clean(repo, tmp_path, content):
    path = tmp_path / "private" / "d.txt"
    path.parent.mkdir()
    if content is not None:
        path.write_text(content)
    (repo / "a.md").write_text("anything\n")
    result = guard(str(repo / "a.md"), denylist=path)
    assert result.exit_code == 2 and "No deny-listed names" not in result.output


def test_a_list_inside_the_repository_is_refused(repo):
    inside = repo / "denylist.txt"
    inside.write_text(f"{NAME}\n")
    (repo / "a.md").write_text("anything\n")
    result = guard(str(repo / "a.md"), denylist=inside)
    assert result.exit_code == 2 and "inside the repository" in result.output


def test_the_default_list_comes_from_the_environment(repo, denylist, monkeypatch):
    monkeypatch.setenv("GRC_DENYLIST", str(denylist))
    (repo / "a.md").write_text(f"{NAME}\n")
    assert guard(str(repo / "a.md")).exit_code == 1


def test_asking_for_nothing_to_scan_is_an_error(repo, denylist):
    assert guard(denylist=denylist).exit_code == 2


def test_staged_scan_reads_the_index_not_the_working_tree(repo, denylist):
    (repo / "a.md").write_text("clean\n")
    git(repo, "add", "a.md")
    (repo / "a.md").write_text(f"{NAME}\n")  # dirty in the working tree only
    assert guard("--staged", denylist=denylist).exit_code == 0
    git(repo, "add", "a.md")
    assert guard("--staged", denylist=denylist).exit_code == 1


def test_the_installed_hook_blocks_a_commit_with_a_name_and_allows_a_clean_one(repo, denylist):
    install = runner.invoke(app, ["guard-names", "--install-hook"])
    assert install.exit_code == 0 and (repo / ".git" / "hooks" / "pre-commit").exists()
    env = {**ENV, "GRC_DENYLIST": str(denylist)}
    (repo / "a.md").write_text(f"Report for {NAME}\n")
    git(repo, "add", "a.md")
    blocked = git(repo, "commit", "-q", "-m", "add", env=env, check=False)
    assert blocked.returncode != 0 and "matches deny-list entry 2" in blocked.stderr
    assert NAME.lower() not in (blocked.stdout + blocked.stderr).lower()
    (repo / "a.md").write_text("Report for Fictional Corp\n")
    git(repo, "add", "a.md")
    assert git(repo, "commit", "-q", "-m", "add", env=env, check=False).returncode == 0


def test_installing_never_overwrites_an_existing_hook(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho mine\n")
    result = runner.invoke(app, ["guard-names", "--install-hook"])
    assert result.exit_code == 2 and "already exists" in result.output
    assert hook.read_text() == "#!/bin/sh\necho mine\n"


def test_installing_outside_a_repository_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["guard-names", "--install-hook"]).exit_code == 2


def test_this_repository_contains_no_deny_listed_example_names():
    """The guard's own tests use an obviously fictional name, and the repo carries no real list."""
    assert not list(Path(__file__).parent.parent.glob("**/denylist*.txt"))
