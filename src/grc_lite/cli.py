"""Command line interface: `grc init`, `grc validate`, `grc report`, `grc import-notes` and `grc collect`."""

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml

from grc_lite.collectors import graph, sources
from grc_lite.collectors.compare import check_leavers, check_mfa
from grc_lite.collectors.errors import CollectError
from grc_lite.collectors.record import record
from grc_lite.importer import import_notes
from grc_lite.loader import AssessmentError, load
from grc_lite.report import build_report

app = typer.Typer(help="Compliance-as-code for gap assessments.", no_args_is_help=True)

collect_app = typer.Typer(
    help="Collect evidence from Entra ID and compare it to a rule.", no_args_is_help=True
)
app.add_typer(collect_app, name="collect")

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


def _finish(folder, result, kind, as_of, source, rule, criterion):
    """Check the target, record the result and print what happened."""
    assessment = _load_or_exit(folder)
    if criterion and criterion not in {c.id for c in assessment.criteria}:
        typer.echo(f"error: unknown criterion {criterion}", err=True)
        raise typer.Exit(1)
    evidence_id, detail = record(folder, kind, result, as_of, source, rule)
    typer.echo(f"Result: {result.verdict}. {result.summary}")
    typer.echo(f"Evidence {evidence_id} added to {folder / 'evidence.yaml'}")
    typer.echo(f"Account names saved to {detail} (not tracked by Git)")
    if criterion:
        typer.echo(
            f"Suggested for {criterion}: result '{result.verdict}', evidence {evidence_id}. "
            "Update criteria.yaml yourself once you agree."
        )


def _as_of(value: datetime | None) -> date:
    return value.date() if value else date.today()


@collect_app.command("leavers")
def collect_leavers(
    folder: Annotated[Path, typer.Argument(help="Assessment folder")],
    hr: Annotated[Path, typer.Option(help="HR leavers CSV with upn and leave_date columns")],
    users: Annotated[Path | None, typer.Option(help="Entra users export (JSON or CSV)")] = None,
    live: Annotated[bool, typer.Option(help="Read users from Microsoft Graph via `az`")] = False,
    max_days: Annotated[int, typer.Option(help="Days allowed after the leave date")] = 1,
    as_of: Annotated[
        datetime | None, typer.Option(help="Date to measure from (YYYY-MM-DD)")
    ] = None,
    criterion: Annotated[str | None, typer.Option(help="Criterion this is evidence for")] = None,
):
    """Leavers must be disabled within --max-days of their leave date."""
    if bool(users) == live:
        typer.echo("error: give either --users FILE or --live", err=True)
        raise typer.Exit(1)
    try:
        leavers = sources.read_hr_leavers(hr)
        entra = graph.fetch_users(graph.az_token()) if live else sources.read_users(users)
    except CollectError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    when = _as_of(as_of)
    result = check_leavers(entra, leavers, when, max_days)
    source = (
        "Entra ID users, live Microsoft Graph" if live else f"Entra ID users export ({users.name})"
    )
    _finish(folder, result, "leavers", when, source, {"max_days": max_days}, criterion)


@collect_app.command("mfa")
def collect_mfa(
    folder: Annotated[Path, typer.Argument(help="Assessment folder")],
    registrations: Annotated[Path | None, typer.Option(help="userRegistrationDetails JSON")] = None,
    users: Annotated[
        Path | None, typer.Option(help="Entra users export, to skip disabled accounts")
    ] = None,
    live: Annotated[bool, typer.Option(help="Read from Microsoft Graph via `az`")] = False,
    scope: Annotated[str, typer.Option(help="admins or all")] = "admins",
    as_of: Annotated[datetime | None, typer.Option(help="Date recorded (YYYY-MM-DD)")] = None,
    criterion: Annotated[str | None, typer.Option(help="Criterion this is evidence for")] = None,
):
    """Every enabled account in scope has MFA registered."""
    if bool(registrations) == live:
        typer.echo("error: give either --registrations FILE or --live", err=True)
        raise typer.Exit(1)
    if scope not in ("admins", "all"):
        typer.echo("error: --scope must be admins or all", err=True)
        raise typer.Exit(1)
    try:
        if live:
            token = graph.az_token()
            regs, entra = graph.fetch_registrations(token), graph.fetch_users(token)
        else:
            regs = sources.read_registrations(registrations)
            entra = sources.read_users(users) if users else None
    except CollectError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    when = _as_of(as_of)
    result = check_mfa(regs, entra, scope)
    source = (
        "Entra ID MFA registration report, live Microsoft Graph"
        if live
        else f"Entra ID MFA registration report ({registrations.name})"
    )
    _finish(folder, result, "mfa", when, source, {"scope": scope}, criterion)
