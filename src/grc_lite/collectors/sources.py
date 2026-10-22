"""Read collector input from files: Graph JSON responses or simple CSVs."""

import csv
import json
from datetime import date
from pathlib import Path

from grc_lite.collectors.errors import CollectError

TRUE = {"true", "yes", "1"}
FALSE = {"false", "no", "0"}


def _json_items(path: Path) -> list[dict]:
    """Accept a Graph response ({"value": [...]}) or a bare list."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise CollectError(f"{path.name}: cannot read as JSON ({type(e).__name__})") from None
    items = data.get("value") if isinstance(data, dict) else data
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise CollectError(f'{path.name}: expected a Graph response with a "value" list')
    return items


def _csv_rows(path: Path, required: list[str]) -> list[dict]:
    try:
        rows = list(csv.DictReader(path.read_text().splitlines()))
    except OSError as e:
        raise CollectError(f"{path.name}: cannot read ({type(e).__name__})") from None
    if not rows:
        raise CollectError(f"{path.name}: no rows")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise CollectError(f"{path.name}: missing column(s): {', '.join(missing)}")
    return rows


def _flag(value: str, path: Path, line: int) -> bool:
    lowered = value.strip().lower()
    if lowered in TRUE:
        return True
    if lowered in FALSE:
        return False
    raise CollectError(f"{path.name}: line {line}: accountEnabled must be true or false")


def read_users(path: Path) -> list[dict]:
    """Entra users as Graph JSON, or a CSV with userPrincipalName and accountEnabled columns."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = _csv_rows(path, ["userPrincipalName", "accountEnabled"])
        return [
            {
                "userPrincipalName": r["userPrincipalName"],
                "accountEnabled": _flag(r["accountEnabled"], path, n),
            }
            for n, r in enumerate(rows, 2)
        ]
    items = _json_items(path)
    _require_keys(items, ["userPrincipalName"], path)
    return items


def read_registrations(path: Path) -> list[dict]:
    """The Graph userRegistrationDetails report as JSON."""
    items = _json_items(Path(path))
    _require_keys(items, ["userPrincipalName", "isMfaRegistered"], Path(path))
    return items


def read_hr_leavers(path: Path) -> list[dict]:
    """HR leavers CSV with upn and leave_date (YYYY-MM-DD) columns."""
    path = Path(path)
    out = []
    for n, row in enumerate(_csv_rows(path, ["upn", "leave_date"]), 2):
        try:
            out.append({"upn": row["upn"], "leave_date": date.fromisoformat(row["leave_date"])})
        except ValueError:
            raise CollectError(f"{path.name}: line {n}: leave_date must be YYYY-MM-DD") from None
    return out


def _require_keys(items: list[dict], keys: list[str], path: Path) -> None:
    for n, item in enumerate(items, 1):
        missing = [k for k in keys if k not in item]
        if missing:
            raise CollectError(f"{path.name}: entry {n} is missing {', '.join(missing)}")
