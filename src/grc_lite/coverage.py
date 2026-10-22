"""Where an assessment is thin: rules with no evidence, gaps with no finding, weak findings that
were selected, requests still waiting. Pure functions over the raw records."""

from datetime import date


def _ids(items: list[dict]) -> list[str]:
    return [i["id"] for i in items if "id" in i]


def coverage(data: dict[str, list[dict]], today: date) -> dict:
    criteria, evidence = data.get("criteria", []), data.get("evidence", [])
    findings, requests = data.get("findings", []), data.get("requests", [])
    linked_evidence = {e for c in criteria for e in c.get("evidence") or []}
    linked_evidence |= {r["evidence"] for r in requests if r.get("evidence")}
    live = [f for f in findings if f.get("status") != "dropped"]
    findings_cover = {c for f in live for c in f.get("criteria") or []}

    waiting = []
    for r in requests:
        if r.get("received"):
            continue
        asked = r.get("asked")
        try:
            days = (
                today - (asked if isinstance(asked, date) else date.fromisoformat(str(asked)))
            ).days
        except ValueError:
            days = None
        waiting.append(
            {"id": r.get("id"), "what": r.get("what", ""), "asked": str(asked or ""), "days": days}
        )

    return {
        "criteria_without_evidence": [c["id"] for c in criteria if not c.get("evidence")],
        "not_tested": [c["id"] for c in criteria if c.get("result", "not tested") == "not tested"],
        "evidence_unlinked": [e for e in _ids(evidence) if e not in linked_evidence],
        "gaps_without_finding": [
            c["id"] for c in criteria if c.get("result") == "gap" and c["id"] not in findings_cover
        ],
        "weak_selected": [
            f["id"]
            for f in findings
            if f.get("status") == "selected" and f.get("strength") in (None, "", "weak", "medium")
        ],
        "undecided": [f["id"] for f in findings if f.get("status", "candidate") == "candidate"],
        "outstanding_requests": waiting,
        "matrix": {
            "criteria": _ids(criteria),
            "evidence": _ids(evidence),
            "links": [[c["id"], e] for c in criteria for e in c.get("evidence") or []],
        },
    }
