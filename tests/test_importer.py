from pathlib import Path

from typer.testing import CliRunner

from grc_lite.cli import app
from grc_lite.importer import import_notes
from grc_lite.loader import load

FIXTURE = Path(__file__).parent / "fixtures" / "notes.md"
runner = CliRunner()


def test_fixture_maps_every_field():
    files, scale, warnings = import_notes(FIXTURE.read_text())
    assert warnings == []
    assert scale == 3
    c1, c2, c3 = files["criteria"]
    assert (c1["evidence"], c1["result"]) == (["E-01"], "meets")
    assert c2["evidence"] == ["E-02", "E-03"]  # Ev-02 and Ev-3 both normalised
    assert c2["result"] == "gap"
    assert c3["rule"].endswith("6 months | signed.")  # escaped pipe restored
    assert c3["result"] == "can't test"
    f1 = files["findings"][0]
    assert f1["criteria"] == ["C-02"]  # matched from "Rule 3, access-policy.md"
    assert (f1["owner"], f1["due"]) == ("Ops Manager", "2026-06-30")
    assert (f1["likelihood"], f1["impact"]) == (2, 3)
    assert f1["impact_reason"] == "Could reach customer data (names)"
    assert "control_ref" not in f1  # "N/A" is not a reference


def test_scale_is_read_from_the_rating_line():
    text = FIXTURE.read_text().replace("[scale 1–3]", "[scale 1–5]")
    assert import_notes(text)[1] == 5


def test_unmatched_criteria_is_a_warning_not_a_guess():
    text = FIXTURE.read_text().replace(
        "Rule 3, access-policy.md, leavers", "the leaver rule, staff who left"
    )
    files, _, warnings = import_notes(text)
    assert "criteria" not in files["findings"][0]
    assert warnings == ["F-01: could not match its criteria to a criterion ID"]


def test_cli_round_trip_loads(tmp_path):
    target = tmp_path / "imp"
    result = runner.invoke(app, ["import-notes", str(FIXTURE), str(target)])
    assert result.exit_code == 0, result.output
    assert "Validation passed." in result.output
    assert len(load(target).findings) == 3


def test_cli_keeps_files_but_fails_when_import_is_incomplete(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text(
        FIXTURE.read_text().replace(
            "Rule 3, access-policy.md, leavers", "the leaver rule, staff who left"
        )
    )
    result = runner.invoke(app, ["import-notes", str(notes), str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "warning: F-01: could not match" in result.output
    assert "selected finding is missing: criteria" in result.output
    assert (tmp_path / "out" / "findings.yaml").exists()


def test_cli_refuses_a_non_empty_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    result = runner.invoke(app, ["import-notes", str(FIXTURE), str(tmp_path)])
    assert result.exit_code == 1
    assert (tmp_path / "keep.txt").read_text() == "x"


def test_criteria_matched_by_quoted_rule_text():
    text = FIXTURE.read_text().replace(
        "Rule 3, access-policy.md, leavers",
        '"Leavers are disabled by the end of their last day." Rule 9, typo.md,',
    )
    assert import_notes(text)[0]["findings"][0]["criteria"] == ["C-02"]


def test_missing_sections_are_reported():
    _, _, warnings = import_notes("## scratch.md\n\njust notes\n")
    assert warnings == [
        "no 'Criteria sheet' section found",
        "no 'Evidence log' section found",
        "no 'Candidate findings' section found",
    ]
