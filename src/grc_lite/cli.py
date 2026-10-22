"""Command line interface: `grc init`, `grc validate`, `grc report` and `grc import-notes`."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
import yaml

from grc_lite.importer import import_notes
from grc_lite.loader import AssessmentError, load
from grc_lite.report import build_report

app = typer.Typer(help="Compliance-as-code for gap assessments.", no_args_is_help=True)

TEMPLATES = {
    "assessment.yaml": "name: My assessment\nscale: 3  # risk scale: 3 (1-3) or 5 (1-5)\n",
    "criteria.yaml": """\
# What you test against. source can be any framework, policy or contract clause.
# result: not tested | meets | gap | can't test
# - id: C-01
#   source: Access Control Policy 4.1
#   rule: Leavers lose access within 24 hours
#   evidence_needed: HR leavers list and account disable log
#   evidence: [E-01]
#   result: not tested
[]
""",
    "evidence.yaml": """\
# What you looked at. type: system | document | observation | interview
# - id: E-01
#   date: 2026-01-05
#   source: HR leavers export
#   type: system
#   shows: Three leavers still enabled after 30 days
#   reliability: Exported by the assessor, not the system owner
[]
""",
    "findings.yaml": """\
# status: candidate | selected | dropped. Selected findings need every field below.
# - id: F-01
#   title: Leavers keep access
#   status: selected
#   strength: strong        # strong | medium | weak
#   strength_reason: System export matches the HR list
#   criteria: [C-01]
#   condition: What you found
#   cause: Why it happened (optional)
#   consequence: Why it matters
#   action: What should change
#   owner: IT Operations
#   due: 2026-06-30
#   likelihood: 2
#   likelihood_reason: One sentence
#   impact: 3
#   impact_reason: One sentence
#   control_ref: optional
[]
""",
    "requests.yaml": """\
# Evidence you asked the client for. No received date means still outstanding.
# - id: R-01
#   asked: 2026-01-05
#   what: Q3 access review record
#   asked_who: CISO
#   received: 2026-01-12   # optional
#   evidence: E-04         # optional: the evidence item it became
#   notes: optional
[]
""",
    "risks.yaml": """\
# Risks you want tracked beyond the findings. Rating = likelihood x impact.
# treatment: mitigate | accept | transfer | avoid    status: open | accepted | closed
# - id: K-01
#   title: Former staff keep access
#   owner: IT Operations Manager
#   likelihood: 2
#   likelihood_reason: One sentence
#   impact: 3
#   impact_reason: One sentence
#   treatment: mitigate
#   status: open
#   findings: [F-01]
#   criteria: [C-01]
[]
""",
}


def _load_or_exit(folder: Path):
    try:
        return load(folder)
    except AssessmentError as e:
        for line in e.errors:
            typer.echo(f"error: {line}", err=True)
        typer.echo(f"{len(e.errors)} error(s)", err=True)
        raise typer.Exit(1)


@app.command()
def validate(folder: Annotated[Path, typer.Argument(help="Assessment folder")]):
    """Check an assessment folder; exit 1 and list every problem if it is invalid."""
    a = _load_or_exit(folder)
    typer.echo(
        f"OK: {len(a.criteria)} criteria, {len(a.evidence)} evidence, {len(a.findings)} findings, "
        f"{len(a.requests)} requests, {len(a.risks)} risks"
    )


@app.command()
def init(folder: Annotated[Path, typer.Argument(help="Folder to create")]):
    """Create a blank assessment folder with commented templates."""
    if folder.exists() and any(folder.iterdir()):
        typer.echo(f"error: {folder} is not empty", err=True)
        raise typer.Exit(1)
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in TEMPLATES.items():
        (folder / name).write_text(text)
    typer.echo(f"Created {folder}. Edit the files, then run: grc validate {folder}")


@app.command()
def report(
    folder: Annotated[Path, typer.Argument(help="Assessment folder")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write to a file")] = None,
):
    """Generate a Markdown report. Refuses to report on an invalid assessment."""
    text = build_report(_load_or_exit(folder), date.today())
    if output:
        output.write_text(text)
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(text, nl=False)


def _dump(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


@app.command("import-notes")
def import_notes_command(
    notes: Annotated[Path, typer.Argument(help="notes.md downloaded from the notes tool")],
    folder: Annotated[Path, typer.Argument(help="New assessment folder to create")],
    name: Annotated[str, typer.Option(help="Assessment name")] = "Imported assessment",
):
    """Convert a notes.md export into an assessment folder, then validate it."""
    if folder.exists() and any(folder.iterdir()):
        typer.echo(f"error: {folder} is not empty", err=True)
        raise typer.Exit(1)
    files, scale, warnings = import_notes(notes.read_text())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "assessment.yaml").write_text(_dump({"name": name, "scale": scale}))
    for filename, items in files.items():
        (folder / f"{filename}.yaml").write_text(_dump(items))
    for warning in warnings:
        typer.echo(f"warning: {warning}", err=True)
    typer.echo(
        f"Imported {len(files['criteria'])} criteria, {len(files['evidence'])} evidence, "
        f"{len(files['findings'])} findings into {folder}"
    )
    _load_or_exit(folder)
    typer.echo("Validation passed.")
