"""Pure comparisons between identity data and a rule. No I/O, so they are easy to test."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Result:
    verdict: str  # "meets" or "gap"
    summary: str  # counts only, safe to store in a tracked file
    checked: int
    offenders: list[str] = field(default_factory=list)  # account names, never stored in Git


def _key(upn: str) -> str:
    return upn.strip().lower()


def check_leavers(users: list[dict], leavers: list[dict], as_of: date, max_days: int = 1) -> Result:
    """Leavers must be disabled within max_days of their leave date.

    Only the current state is known, so a leaver who is disabled now counts as meeting the rule
    even if they were disabled late. A leaver with no account is treated as removed.
    """
    enabled = {_key(u["userPrincipalName"]): bool(u.get("accountEnabled")) for u in users}
    offenders = []
    for leaver in leavers:
        upn = _key(leaver["upn"])
        overdue = (as_of - leaver["leave_date"]).days > max_days
        if overdue and enabled.get(upn):
            offenders.append(upn)
    summary = (
        f"{len(offenders)} of {len(leavers)} leavers still have an enabled account "
        f"more than {max_days} day(s) after their leave date."
    )
    return Result("gap" if offenders else "meets", summary, len(leavers), sorted(offenders))


def check_mfa(
    registrations: list[dict], users: list[dict] | None = None, scope: str = "admins"
) -> Result:
    """Every enabled account in scope has MFA registered.

    Without a user list, disabled accounts cannot be excluded and are counted.
    """
    if scope not in ("admins", "all"):
        raise ValueError("scope must be 'admins' or 'all'")
    disabled = set()
    if users is not None:
        disabled = {_key(u["userPrincipalName"]) for u in users if not u.get("accountEnabled")}
    in_scope = [
        r
        for r in registrations
        if _key(r["userPrincipalName"]) not in disabled and (scope == "all" or r.get("isAdmin"))
    ]
    offenders = [_key(r["userPrincipalName"]) for r in in_scope if not r.get("isMfaRegistered")]
    who = "administrator" if scope == "admins" else "enabled"
    summary = f"{len(offenders)} of {len(in_scope)} {who} accounts have no MFA registered."
    return Result("gap" if offenders else "meets", summary, len(in_scope), sorted(offenders))
