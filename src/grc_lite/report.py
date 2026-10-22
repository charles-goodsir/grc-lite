"""Render a loaded assessment as a Markdown report."""

from collections import Counter
from datetime import date

from grc_lite.loader import Assessment
from grc_lite.models import Finding, FindingStatus, Result, rating


def _cell(text: object) -> str:
    """Make a value safe inside a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ").strip() or "-"


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines + [""]


def _rating(f: Finding, scale: int) -> str:
    if f.likelihood is None or f.impact is None:
        return "-"
    return rating(f.likelihood, f.impact, scale)


def _score(f: Finding) -> int:
    return (f.likelihood or 0) * (f.impact or 0)


def build_report(a: Assessment, today: date) -> str:
    scale = a.meta.scale
    selected = sorted(
        (f for f in a.findings if f.status is FindingStatus.SELECTED),
        key=lambda f: (-_score(f), f.id),
    )
    out = [f"# {a.meta.name}", "", f"Generated {today.isoformat()} | risk scale 1-{scale}", ""]

    out += ["## Summary", "", "**Criteria by result**", ""]
    results = Counter(c.result for c in a.criteria)
    out += _table(["Result", "Count"], [[r.value, results[r]] for r in Result])
    out += ["**Findings by status**", ""]
    statuses = Counter(f.status for f in a.findings)
    out += _table(["Status", "Count"], [[s.value, statuses[s]] for s in FindingStatus])
    out += ["**Selected findings by rating**", ""]
    ratings = Counter(_rating(f, scale) for f in selected)
    out += _table(["Rating", "Count"], [[r, ratings[r]] for r in ratings] or [["none", 0]])

    out += ["## Candidate versus selected findings", ""]
    out += _table(
        ["ID", "Title", "Status", "Evidence strength", "Rating", "Why this strength"],
        [
            [f.id, f.title, f.status.value, f.strength.value, _rating(f, scale), f.strength_reason]
            for f in a.findings
        ],
    )

    out += ["## Findings", ""]
    if not selected:
        out += ["None selected.", ""]
    for f in selected:
        out += [f"### {f.id}: {f.title}", ""]
        out += [
            f"**Rating: {_rating(f, scale)}** (likelihood {f.likelihood} x impact {f.impact})",
            "",
        ]
        out += _table(
            ["Field", "Detail"],
            [
                ["Criteria", ", ".join(f.criteria)],
                ["Condition", f.condition],
                ["Cause", f.cause],
                ["Consequence", f.consequence],
                ["Action", f.action],
                ["Owner", f.owner],
                ["Due", f.due],
                ["Likelihood", f"{f.likelihood}: {f.likelihood_reason}"],
                ["Impact", f"{f.impact}: {f.impact_reason}"],
                ["Evidence strength", f"{f.strength.value}: {f.strength_reason}"],
                ["Control reference", f.control_ref],
            ],
        )

    out += ["## Criteria", ""]
    out += _table(
        ["ID", "Source", "Rule", "Result", "Evidence"],
        [[c.id, c.source, c.rule, c.result.value, ", ".join(c.evidence)] for c in a.criteria],
    )
    out += ["## Evidence", ""]
    out += _table(
        ["ID", "Date", "Source", "Type", "Shows", "Reliability"],
        [[e.id, e.date, e.source, e.type.value, e.shows, e.reliability] for e in a.evidence],
    )

    out += ["## Risk register", ""]
    if a.risks:
        ranked = sorted(a.risks, key=lambda k: (-k.likelihood * k.impact, k.id))
        out += _table(
            [
                "ID",
                "Risk",
                "Rating",
                "Likelihood",
                "Impact",
                "Treatment",
                "Status",
                "Owner",
                "Links",
            ],
            [
                [
                    k.id,
                    k.title,
                    rating(k.likelihood, k.impact, scale),
                    k.likelihood,
                    k.impact,
                    k.treatment.value,
                    k.status.value,
                    k.owner,
                    ", ".join([*k.findings, *k.criteria]),
                ]
                for k in ranked
            ],
        )
    else:
        out += ["None.", ""]

    out += ["## Outstanding requests", ""]
    waiting = [r for r in a.requests if r.outstanding]
    if waiting:
        out += _table(
            ["ID", "Asked", "What", "Asked who", "Notes"],
            [[r.id, r.asked, r.what, r.asked_who, r.notes] for r in waiting],
        )
    else:
        out += ["None.", ""]

    open_items = [c for c in a.criteria if c.result in (Result.NOT_TESTED, Result.CANT_TEST)]
    out += ["## Open items", "", "Criteria not yet tested or that could not be tested.", ""]
    out += _table(
        ["ID", "Rule", "Result", "Evidence needed"],
        [[c.id, c.rule, c.result.value, c.evidence_needed] for c in open_items],
    )
    return "\n".join(out).rstrip() + "\n"
