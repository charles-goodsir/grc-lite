"""Check each collected detail file against the SHA-256 recorded in its evidence entry."""

import hashlib
import re
from pathlib import Path

import yaml

# the file name allows no slash, so an entry cannot point outside collected/
RECORDED = re.compile(r"collected/([A-Za-z0-9_.-]+\.json) \(SHA-256 ([0-9a-f]{64})\)")


def verify(folder: Path) -> list[dict]:
    """One result per evidence entry that records a hash: ok, changed, missing or unreadable."""
    path = folder / "evidence.yaml"
    entries = yaml.safe_load(path.read_text()) if path.exists() else None
    results = []
    for entry in entries or []:
        found = (
            RECORDED.search(str(entry.get("reliability", ""))) if isinstance(entry, dict) else None
        )
        if not found:
            continue
        name, expected = found.groups()
        detail = folder / "collected" / name
        if detail.is_symlink() or (detail.exists() and not detail.is_file()):
            status = "unreadable"
        elif not detail.exists():
            status = "missing"
        else:
            status = (
                "ok" if hashlib.sha256(detail.read_bytes()).hexdigest() == expected else "changed"
            )
        results.append({"id": entry.get("id", "?"), "file": name, "status": status})
    return results
