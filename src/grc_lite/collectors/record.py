"""Write a collector result into an assessment folder without putting account names in Git."""

import json
import os
from datetime import date
from pathlib import Path

import yaml

from grc_lite.collectors.compare import Result


def next_evidence_id(folder: Path) -> str:
    text = (folder / "evidence.yaml").read_text() if (folder / "evidence.yaml").exists() else ""
    numbers = [
        int(e["id"][2:])
        for e in yaml.safe_load(text) or []
        if str(e.get("id", "")).startswith("E-")
    ]
    return f"E-{max(numbers, default=0) + 1:02d}"


def append_evidence(folder: Path, entry: dict) -> None:
    """Append one entry as text, so comments already in evidence.yaml survive."""
    path = folder / "evidence.yaml"
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.strip() != "[]"]  # the empty-list placeholder
    block = yaml.safe_dump([entry], sort_keys=False, allow_unicode=True, width=100)
    path.write_text("\n".join(lines + [block.rstrip()]) + "\n")


def write_detail(folder: Path, kind: str, as_of: date, result: Result, rule: dict) -> Path:
    """Save account names to collected/, which ignores itself and is readable only by the owner."""
    directory = folder / "collected"
    directory.mkdir(exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n")
    path = directory / f"{kind}-{as_of.isoformat()}.json"
    detail = {"kind": kind, "as_of": as_of.isoformat(), "rule": rule, "checked": result.checked,
              "offenders": result.offenders}  # fmt: skip
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(detail, f, indent=2)
    return path


def record(
    folder: Path, kind: str, result: Result, as_of: date, source: str, rule: dict
) -> tuple[str, Path]:
    """Add an evidence entry (counts only) and a detail file (names). Return the ID and file."""
    detail = write_detail(folder, kind, as_of, result, rule)
    evidence_id = next_evidence_id(folder)
    append_evidence(
        folder,
        {
            "id": evidence_id,
            "date": as_of,
            "source": source,
            "type": "system",
            "shows": result.summary,
            "reliability": (
                f"Collected read-only by grc-lite ({kind}) on {as_of.isoformat()}; point-in-time. "
                f"Account names are in collected/{detail.name}, which is not tracked by Git."
            ),
        },
    )
    return evidence_id, detail
