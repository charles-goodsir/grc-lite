import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from grc_lite.cli import app
from grc_lite.collectors import graph
from grc_lite.collectors.errors import CollectError
from grc_lite.loader import load

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
runner = CliRunner()
TOKEN = "eyJ0eXAi.FAKE-TOKEN-FOR-TESTS.sig"


@pytest.fixture
def folder(tmp_path):
    target = tmp_path / "assessment"
    shutil.copytree(ROOT / "data" / "example", target)
    return target


def leavers_args(folder, *extra):
    return [
        "collect", "leavers", str(folder),
        "--hr", str(FIXTURES / "hr-leavers.csv"),
        "--users", str(FIXTURES / "entra-users.json"),
        "--as-of", "2026-03-10", *extra,
    ]  # fmt: skip


def test_leavers_adds_evidence_with_counts_only_and_still_validates(folder):
    result = runner.invoke(app, leavers_args(folder, "--criterion", "C-01"))
    assert result.exit_code == 0, result.output
    assert "Result: gap. 2 of 5 leavers" in result.output
    assert "Suggested for C-01: result 'gap', evidence E-04" in result.output
    evidence = (folder / "evidence.yaml").read_text()
    assert "id: E-04" in evidence
    assert "@" not in evidence.split("id: E-04")[1]  # no account name in the tracked file
    assert len(load(folder).evidence) == 4


def test_account_names_go_only_to_a_private_ignored_detail_file(folder):
    runner.invoke(app, leavers_args(folder))
    detail = folder / "collected" / "leavers-2026-03-10.json"
    assert "amy.reed@acme.example" in detail.read_text()
    assert detail.stat().st_mode & 0o777 == 0o600
    assert (folder / "collected" / ".gitignore").read_text() == "*\n"


def test_git_does_not_see_the_detail_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    runner.invoke(app, ["init", str(repo / "a")])
    runner.invoke(app, leavers_args(repo / "a"))
    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "a/evidence.yaml" in status
    assert "collected" not in status
    assert "amy.reed" not in status


def test_comments_in_evidence_yaml_survive_and_ids_increment(tmp_path):
    runner.invoke(app, ["init", str(tmp_path / "a")])
    runner.invoke(app, leavers_args(tmp_path / "a"))
    runner.invoke(app, leavers_args(tmp_path / "a"))
    text = (tmp_path / "a" / "evidence.yaml").read_text()
    assert text.startswith("# What you looked at.")
    assert [e.id for e in load(tmp_path / "a").evidence] == ["E-01", "E-02"]


def test_unknown_criterion_writes_nothing(folder):
    before = (folder / "evidence.yaml").read_text()
    result = runner.invoke(app, leavers_args(folder, "--criterion", "C-99"))
    assert result.exit_code == 1
    assert "unknown criterion C-99" in result.output
    assert (folder / "evidence.yaml").read_text() == before
    assert not (folder / "collected").exists()


def test_mfa_from_files(folder):
    result = runner.invoke(
        app,
        ["collect", "mfa", str(folder), "--registrations", str(FIXTURES / "mfa-registrations.json"),
         "--users", str(FIXTURES / "entra-users.json"), "--as-of", "2026-03-10"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Result: gap. 1 of 2 administrator accounts have no MFA registered." in result.output


def test_must_choose_exactly_one_source(folder):
    both = runner.invoke(app, leavers_args(folder, "--live"))
    neither = runner.invoke(
        app, ["collect", "leavers", str(folder), "--hr", str(FIXTURES / "hr-leavers.csv")]
    )
    assert both.exit_code == neither.exit_code == 1
    assert "either --users FILE or --live" in both.output + neither.output


def test_live_mode_uses_graph_and_never_echoes_the_token(folder, monkeypatch):
    users = [{"userPrincipalName": "amy.reed@acme.example", "accountEnabled": True}]
    monkeypatch.setattr(graph, "az_token", lambda: TOKEN)
    monkeypatch.setattr(graph, "fetch_users", lambda token: users if token == TOKEN else [])
    result = runner.invoke(
        app,
        ["collect", "leavers", str(folder), "--hr", str(FIXTURES / "hr-leavers.csv"), "--live",
         "--as-of", "2026-03-10"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "live Microsoft Graph" in (folder / "evidence.yaml").read_text()
    assert TOKEN not in result.output + (folder / "evidence.yaml").read_text()


def test_live_failure_is_reported_without_a_traceback_or_token(folder, monkeypatch):
    def boom():
        raise CollectError("could not get a Graph token from the Azure CLI; run `az login`")

    monkeypatch.setattr(graph, "az_token", boom)
    result = runner.invoke(app, ["collect", "mfa", str(folder), "--live", "--as-of", "2026-03-10"])
    assert result.exit_code == 1
    assert "az login" in result.output
    assert not (folder / "collected").exists()
