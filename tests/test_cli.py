from typer.testing import CliRunner

from grc_lite.cli import app

runner = CliRunner()


def test_init_then_validate_passes(tmp_path):
    target = tmp_path / "a"
    assert runner.invoke(app, ["init", str(target)]).exit_code == 0
    result = runner.invoke(app, ["validate", str(target)])
    assert result.exit_code == 0
    assert "OK: 0 criteria, 0 evidence, 0 findings" in result.output


def test_init_refuses_non_empty_folder(tmp_path):
    (tmp_path / "x").write_text("keep me")
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 1


def test_validate_fails_with_errors(tmp_path):
    (tmp_path / "criteria.yaml").write_text("- {id: C-01, source: s, rule: r, evidence: [E-9]}\n")
    result = runner.invoke(app, ["validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "unknown evidence E-9" in result.output
