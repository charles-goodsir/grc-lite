"""Rule-based checks that catch the mistakes graders keep naming, before a level is submitted.

They look at completeness and consistency, never at whether a conclusion is right. Everything
works on raw records, so it runs on drafts.
"""

import re
from datetime import date

from grc_lite.coverage import coverage

EVIDENCE_REF = re.compile(r"\bEv?-?\s*0*(\d+)\b", re.IGNORECASE)
ALREADY_HAPPENING = re.compile(
    r"\b(already (happen|occur|exist)\w*|is happening|has happened|happened already|is already)\b",
    re.IGNORECASE,
)
UNLIKELY = re.compile(
    r"\b(unlikely|rarely|never happened|has not happened|hasn't happened)\b", re.IGNORECASE
)

# a plain-words reminder for each kind of mistake in the mistake log
REMINDERS = {
    "missed gap": "Before you submit, go back through the rules marked meets and test them again.",
    "wrong rating": "Check each rating matches its own wording, using the scale.",
    "miscounted": "Re-count every number in your findings against the source file.",
    "conditional rule not tested": "For a conditional rule, test the condition for every item, then check the outcome. Do not count entries.",
    "cause missing": "Give every selected finding a Cause line.",
    "weak evidence selected": "Prefer stronger evidence when choosing which findings to select.",
    "unverified claim": "Check every claim in your notes against the source before it goes into a finding.",
}


def _issue(rule: str, message: str, tag: str = "other", level: str = "fix") -> dict:
    return {"rule": rule, "message": message, "tag": tag, "level": level}


def _has(record: dict, field: str) -> bool:
    return bool(str(record.get(field) or "").strip())


def check_finding(
    finding: dict, criteria: dict[str, dict], evidence_ids: set[str], scale: int
) -> list[dict]:
    """Issues for one finding. Candidates and dropped findings are not held to the full standard."""
    issues: list[dict] = []
    title = str(finding.get("title") or "")
    if re.search(r"\band\b", title, re.IGNORECASE):
        issues.append(
            _issue(
                "title_two_issues", "The title has 'and'. A finding is one issue only.", level="tip"
            )
        )
    if finding.get("status") != "selected":
        return issues

    if not _has(finding, "cause"):
        issues.append(
            _issue(
                "cause_missing",
                "No Cause line. The model treats it as optional, but graders have asked for one.",
                "cause missing",
            )
        )
    condition = str(finding.get("condition") or "")
    if condition and not re.search(r"\d", EVIDENCE_REF.sub("", condition)):  # E-01 is not a count
        issues.append(
            _issue(
                "condition_no_number",
                "The condition has no number. Give counts, like 5 of 30.",
                "miscounted",
            )
        )
    cited = {f"E-{int(n):02d}" for n in EVIDENCE_REF.findall(condition)}
    if condition and not cited:
        issues.append(
            _issue(
                "condition_no_evidence",
                "The condition cites no evidence ID, like E-01.",
                "unverified claim",
            )
        )
    for missing in sorted(cited - evidence_ids):
        issues.append(
            _issue(
                "unknown_evidence",
                f"The condition cites {missing}, which is not in your evidence log.",
                "unverified claim",
            )
        )
    if finding.get("strength") in (None, "", "weak", "medium"):
        issues.append(
            _issue(
                "weak_selected",
                f"Selected on {finding.get('strength') or 'unrated'} evidence. Is there stronger evidence, or should this stay a candidate?",
                "weak evidence selected",
                "tip",
            )
        )
    for cid in finding.get("criteria") or []:
        result = (criteria.get(cid) or {}).get("result", "not tested")
        if cid in criteria and result != "gap":
            issues.append(
                _issue(
                    "criterion_not_gap",
                    f"It links {cid}, which is marked '{result}', not gap.",
                    level="tip",
                )
            )
    likelihood = finding.get("likelihood")
    if isinstance(likelihood, int):
        reason = str(finding.get("likelihood_reason") or "")
        if ALREADY_HAPPENING.search(reason) and likelihood < scale:
            issues.append(
                _issue(
                    "likelihood_wording",
                    f"The likelihood reason says it is already happening, which is the top likelihood ({scale}), but you gave {likelihood}.",
                    "wrong rating",
                )
            )
        if UNLIKELY.search(reason) and likelihood > 1:
            issues.append(
                _issue(
                    "likelihood_wording",
                    f"The likelihood reason says it is unlikely, but you gave {likelihood}.",
                    "wrong rating",
                    "tip",
                )
            )
    return issues


def coach(data: dict[str, list[dict]], scale: int) -> dict[str, list[dict]]:
    criteria = {c["id"]: c for c in data.get("criteria", []) if "id" in c}
    evidence_ids = {e["id"] for e in data.get("evidence", []) if "id" in e}
    return {
        f["id"]: found
        for f in data.get("findings", [])
        if "id" in f and (found := check_finding(f, criteria, evidence_ids, scale))
    }


def _check(
    key: str,
    label: str,
    ids: list[str],
    ok_text: str,
    fix_text: str,
    tag: str = "",
    level: str = "fix",
) -> dict:
    return {"key": key, "label": label, "ids": ids, "tag": tag,
            "status": "ok" if not ids else level, "detail": ok_text if not ids else fix_text}  # fmt: skip


def presubmit(
    data: dict[str, list[dict]],
    scale: int,
    slots: int,
    problems: int,
    history: dict[str, int],
    today: date,
) -> dict:
    """The checklist to run before locking a level, plus reminders from your own mistake history."""
    criteria, findings = data.get("criteria", []), data.get("findings", [])
    cov = coverage(data, today)
    selected = [f for f in findings if f.get("status") == "selected"]
    issues = coach(data, scale)
    fixes = sorted(i for i, found in issues.items() if any(x["level"] == "fix" for x in found))
    cant = [c["id"] for c in criteria if c.get("result") == "can't test"]
    requests = data.get("requests", [])
    no_reliability = [
        e["id"] for e in data.get("evidence", []) if "id" in e and not _has(e, "reliability")
    ]
    checks = [
        _check(
            "problems",
            "No validation problems",
            [f"{problems} problem(s)"] if problems else [],
            "Everything passes the same checks as grc validate.",
            f"{problems} problem(s) still open. See the Problems tab.",
        ),
        _check(
            "results",
            "Every rule has a result",
            cov["not_tested"],
            "Every rule is marked meets, gap or can't test.",
            "These rules are still 'not tested'.",
            "missed gap",
        ),
        _check(
            "candidates",
            "Every candidate is decided",
            cov["undecided"],
            "No undecided candidates.",
            "These findings are still candidates: select or drop them.",
        ),
        _check(
            "gaps",
            "Every gap has a finding",
            cov["gaps_without_finding"],
            "Every rule marked gap has a live finding.",
            "These rules are marked gap but no live finding covers them.",
            "missed gap",
        ),
        _check(
            "coach",
            "Selected findings pass the coach",
            fixes,
            "No fixes suggested on selected findings.",
            "The finding coach has fixes for these. See below.",
            "other",
        ),
    ]
    if slots and len(selected) != slots:
        checks.append(
            _check(
                "slots",
                "All slots used",
                [f"{len(selected)} of {slots}"],
                "",
                f"{len(selected)} of {slots} slots used. Use them all, or go back through the rules marked meets.",
                "missed gap",
                "fix" if len(selected) > slots else "warn",
            )
        )
    else:
        checks.append(
            _check("slots", "All slots used", [], f"{len(selected)} of {slots} slots used.", "")
        )
    if cant:
        short = max(0, len(cant) - len(requests))
        checks.append(
            _check(
                "requests",
                "Can't-test rules have requests",
                [f"{short} short"] if short else [],
                f"{len(cant)} can't-test rule(s) and {len(requests)} request(s) logged.",
                f"{len(cant)} can't-test rule(s) but only {len(requests)} request(s). Log one for each.",
                "",
                "warn",
            )
        )
    checks.append(
        _check(
            "reliability",
            "Evidence has a reliability note",
            no_reliability,
            "Every evidence item says how far it can be trusted.",
            "These evidence items have no reliability note.",
            "",
            "warn",
        )
    )
    reminders = [
        {"tag": tag, "count": count, "reminder": REMINDERS[tag]}
        for tag, count in sorted(history.items(), key=lambda kv: -kv[1])
        if tag in REMINDERS and count > 0
    ]
    return {"checks": checks, "reminders": reminders, "findings": issues}
