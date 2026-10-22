"""Store an imported grading file, and decide when the sealed files may be shown."""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from grc_lite.grading import TAGS, parse_grading
from grc_lite.web import export, records

GRADING = "grading.yaml"
GRADING_MD = "grading.md"
MISTAKE_ID = re.compile(r"M-\d{2,3}")


def has_grading(assessment: Path) -> bool:
    return (assessment / GRADING).exists()


def revealed(assessment: Path) -> bool:
    """Answer keys and graded/ open only after the level is submitted AND a grading is imported.
    Like the lock, this is self-discipline: creating grading.yaml by hand would also open them."""
    return export.is_locked(assessment) and has_grading(assessment)


def read(assessment: Path) -> dict | None:
    path = assessment / GRADING
    return yaml.safe_load(path.read_text()) if path.exists() else None


def import_grading(assessment: Path, text: str, name: str, replace: bool) -> dict:
    if not export.is_locked(assessment):
        raise records.ConflictError(
            "submit the level first; grading can only be imported after that"
        )
    try:
        grading = parse_grading(text)
    except ValueError as e:
        raise records.RecordError(str(e)) from None
    with records.LOCK:
        previous = read(assessment)
        if previous and not replace:
            raise records.ConflictError("this level already has a grading; confirm to replace it")
        data = grading.model_dump()
        if previous:  # keep the tags you chose for mistakes that appear again
            kept = {(m["source"], m["text"]): m["tag"] for m in previous.get("mistakes", [])}
            for mistake in data["mistakes"]:
                mistake["tag"] = kept.get((mistake["source"], mistake["text"]), mistake["tag"])
        data.update(
            imported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source=name[:200],
            sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        records._write(assessment / GRADING, data)
        (assessment / GRADING_MD).write_text(text)
    return data


def set_tag(assessment: Path, mistake_id: str, tag: str) -> dict | None:
    if not MISTAKE_ID.fullmatch(mistake_id):
        return None
    if tag not in TAGS:
        raise records.RecordError("unknown tag")
    with records.LOCK:
        data = read(assessment)
        for mistake in (data or {}).get("mistakes", []):
            if mistake["id"] == mistake_id:
                mistake["tag"] = tag
                records._write(assessment / GRADING, data)
                return data
    return None
