import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from grc_lite.cli import app

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
runner = CliRunner()


@pytest.fixture
def folder(tmp_path):
    target = tmp_path / "assessment"
    shutil.copytree(ROOT / "data" / "example", target)
    return target


def collect(folder):
    args = ["collect", "leavers", str(folder), "--hr", str(FIXTURES / "hr-leavers.csv"),
            "--users", str(FIXTURES / "entra-users.json"), "--as-of", "2026-03-10"]  # fmt: skip
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


def recorded(folder):
    """(file name, recorded hash) for every evidence entry that records one."""
    found = []
    for entry in yaml.safe_load((folder / "evidence.yaml").read_text()):
        m = re.search(
            r"collected/(\S+\.json) \(SHA-256 ([0-9a-f]{64})\)", entry.get("reliability", "")
        )
        if m:
            found.append(m.groups())
    return found


def verify(folder, *extra):
    return runner.invoke(app, ["collect", "verify", str(folder), *extra])


def test_the_evidence_entry_records_the_hash_of_the_detail_file(folder):
    collect(folder)
    [(name, digest)] = recorded(folder)
    assert digest == hashlib.sha256((folder / "collected" / name).read_bytes()).hexdigest()


def test_the_detail_file_has_a_random_salt_and_stays_private(folder):
    collect(folder)
    path = folder / "collected" / "leavers-2026-03-10.json"
    assert len(json.loads(path.read_text())["salt"]) == 32
    assert path.stat().st_mode & 0o777 == 0o600


def test_identical_data_gives_different_hashes_so_names_cannot_be_confirmed(folder):
    collect(folder)
    collect(folder)
    (_, first), (_, second) = recorded(folder)
    assert first != second


def test_a_second_run_on_the_same_day_does_not_overwrite_the_first(folder):
    collect(folder)
    collect(folder)
    assert sorted(p.name for p in (folder / "collected").glob("*.json")) == [
        "leavers-2026-03-10-2.json",
        "leavers-2026-03-10.json",
    ]
    result = verify(folder)
    assert result.exit_code == 0 and result.output.count(" ok ") == 2


def test_verify_passes_for_untouched_files(folder):
    collect(folder)
    result = verify(folder)
    assert result.exit_code == 0
    assert "E-04  ok" in result.output and "All present detail files match" in result.output


def test_verify_catches_an_edited_detail_file(folder):
    collect(folder)
    path = folder / "collected" / "leavers-2026-03-10.json"
    detail = json.loads(path.read_text())
    detail["offenders"] = detail["offenders"][:-1]  # someone removes a name
    path.write_text(json.dumps(detail, indent=2))
    result = verify(folder)
    assert result.exit_code == 1 and "changed" in result.output


def test_a_missing_detail_file_is_noted_and_only_fails_when_strict(folder):
    collect(folder)
    (folder / "collected" / "leavers-2026-03-10.json").unlink()
    ok = verify(folder)
    assert ok.exit_code == 0 and "not on this machine" in ok.output
    assert verify(folder, "--strict").exit_code == 1


def test_a_detail_file_replaced_by_a_link_is_not_followed(folder, tmp_path):
    collect(folder)
    path = folder / "collected" / "leavers-2026-03-10.json"
    outside = tmp_path / "other.json"
    outside.write_bytes(path.read_bytes())  # same bytes, so following the link would pass
    path.unlink()
    path.symlink_to(outside)
    result = verify(folder)
    assert result.exit_code == 1 and "unreadable" in result.output


def test_an_entry_cannot_point_outside_the_collected_folder(folder, tmp_path):
    (tmp_path / "secret.json").write_text("{}")
    digest = hashlib.sha256(b"{}").hexdigest()
    (folder / "evidence.yaml").write_text(
        yaml.safe_dump([{"id": "E-01", "date": "2026-03-10", "source": "s", "type": "system", "shows": "x",
                         "reliability": f"Detail file collected/../secret.json (SHA-256 {digest}) holds names."}])
    )  # fmt: skip
    result = verify(folder)
    assert result.exit_code == 0 and "No evidence entries with a detail-file hash." in result.output


def test_evidence_without_a_hash_is_ignored(folder):
    result = verify(folder)
    assert result.exit_code == 0 and "No evidence entries" in result.output
