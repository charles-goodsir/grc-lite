from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from grc_lite.cli import app
from grc_lite.loader import load
from grc_lite.report import build_report

ROOT = Path(__file__).parent.parent
TODAY = date(2026, 3, 10)


def test_example_matches_golden_file():
    expected = (ROOT / "tests" / "golden" / "example-report.md").read_text()
    assert build_report(load(ROOT / "data" / "example"), TODAY) == expected


def test_empty_assessment_still_renders(tmp_path):
    (tmp_path / "criteria.yaml").write_text("[]")
    text = build_report(load(tmp_path), TODAY)
    assert "None selected." in text
    assert "| none | 0 |" in text


def test_selected_findings_sorted_by_score_then_id(tmp_path):
    def finding(id, likelihood, impact):
        return f"""
- {{id: {id}, title: T{id}, status: selected, strength: strong, strength_reason: r,
   criteria: [C-01], condition: c, consequence: q, action: a, owner: o, due: 2026-06-30,
   likelihood: {likelihood}, likelihood_reason: l, impact: {impact}, impact_reason: i}}
"""

    (tmp_path / "criteria.yaml").write_text("- {id: C-01, source: s, rule: r}\n")
    (tmp_path / "findings.yaml").write_text(
        finding("F-01", 1, 1) + finding("F-02", 3, 3) + finding("F-03", 3, 3)
    )
    text = build_report(load(tmp_path), TODAY)
    order = [text.index(f"### {i}:") for i in ("F-02", "F-03", "F-01")]
    assert order == sorted(order)


def test_pipes_in_text_do_not_break_tables(tmp_path):
    (tmp_path / "criteria.yaml").write_text("- {id: C-01, source: 'a|b', rule: r}\n")
    assert "a\\|b" in build_report(load(tmp_path), TODAY)


def test_cli_report_to_file(tmp_path):
    out = tmp_path / "r.md"
    result = CliRunner().invoke(app, ["report", str(ROOT / "data" / "example"), "-o", str(out)])
    assert result.exit_code == 0
    assert out.read_text().startswith("# Acme Cloud Ltd")


def test_cli_report_refuses_invalid_assessment(tmp_path):
    (tmp_path / "criteria.yaml").write_text("- {id: bad, source: s, rule: r}\n")
    result = CliRunner().invoke(app, ["report", str(tmp_path)])
    assert result.exit_code == 1
    assert "# " not in result.stdout
