"""Read and write the assessment's records for the web app.

The page edits drafts, so a record may be incomplete. Records are written as given (cleaned and
size-limited), and the loader's validation is reported as a list of problems, never as a refusal.
"""

import re
import threading
import types
import typing
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from grc_lite.loader import AssessmentError, load
from grc_lite.models import (
    Criterion,
    Evidence,
    Finding,
    Meta,
    Request,
    Risk,
)

KINDS = {
    "criteria": (Criterion, "C"),
    "evidence": (Evidence, "E"),
    "findings": (Finding, "F"),
    "requests": (Request, "R"),
    "risks": (Risk, "K"),
}
MAX_TEXT = 20_000
MAX_LIST = 200
MAX_RECORDS = 2_000
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROBLEM = re.compile(r"^([\w.]+): (?:([A-Z]-\d+|entry \d+): )?(.*)$", re.DOTALL)
LOCK = threading.Lock()


class RecordError(ValueError):
    """The request itself is wrong (unknown field, too long), as opposed to incomplete data."""


def _dump(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(_dump(data))
    temp.replace(path)  # never leave a half-written file


def read_meta(assessment: Path) -> Meta:
    path = assessment / "assessment.yaml"
    try:
        return Meta.model_validate(
            (yaml.safe_load(path.read_text()) if path.exists() else None) or {}
        )
    except Exception as e:
        raise RecordError("assessment.yaml is not valid; fix it in the file") from e


def write_meta(assessment: Path, meta: Meta) -> None:
    _write(assessment / "assessment.yaml", meta.model_dump(mode="json"))


def read_records(assessment: Path, kind: str) -> list[dict]:
    path = assessment / f"{kind}.yaml"
    items = yaml.safe_load(path.read_text()) if path.exists() else None
    if items is None:
        return []
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise RecordError(f"{kind}.yaml is not a list of records; fix it in the file")
    return items


def _field_type(model, name: str):
    annotation = model.model_fields[name].annotation
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else annotation
    return annotation


def clean(kind: str, fields: dict) -> dict:
    """Keep only known fields, in the model's order, coerced to the right shape.

    Empty values are left out so the validator reports them as missing.
    """
    model, _ = KINDS[kind]
    unknown = set(fields) - set(model.model_fields)
    if unknown:
        raise RecordError(f"unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    for name in model.model_fields:
        if name == "id":
            continue
        value = fields.get(name)
        if value is None or value == "" or value == []:
            continue
        kind_of = _field_type(model, name)
        if typing.get_origin(kind_of) is list:
            if not isinstance(value, list) or len(value) > MAX_LIST:
                raise RecordError(f"{name} must be a short list")
            value = [str(v)[:40] for v in value if str(v).strip()]
        elif isinstance(value, bool) or not isinstance(value, (str, int)):
            raise RecordError(f"{name} must be text or a number")
        elif isinstance(value, str):
            value = value.strip()
            if len(value) > MAX_TEXT:
                raise RecordError(f"{name} is too long")
            if kind_of is int and value.isdigit():
                value = int(value)
            elif kind_of is date and ISO_DATE.match(value):
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    pass  # left as text; the validator reports it
        if value not in ("", []):
            out[name] = value
    return out


def new_id(prefix: str, items: list[dict], meta: Meta) -> str:
    numbers = [int(i["id"][2:]) for i in items if re.fullmatch(rf"{prefix}-\d+", str(i.get("id")))]
    number = max([meta.counters.get(prefix, 0), *numbers]) + 1
    meta.counters[prefix] = number
    return f"{prefix}-{number:02d}"


def problems(assessment: Path) -> list[dict]:
    """What `grc validate` would say, as {file, id, message} so the page can link to records."""
    try:
        load(assessment)
    except AssessmentError as e:
        if "no assessment files found" in e.errors[0] or "not a directory" in e.errors[0]:
            return []
        found = []
        for line in e.errors:
            m = PROBLEM.match(line)
            file, ident, message = m.groups() if m else ("", None, line)
            found.append({"file": file, "id": ident if ident and "-" in ident else None,
                          "message": message})  # fmt: skip
        return found
    return []


def snapshot(assessment: Path) -> dict:
    data: dict[str, Any] = {"meta": read_meta(assessment).model_dump(mode="json")}
    for kind in KINDS:
        data[kind] = read_records(assessment, kind)
    data["problems"] = problems(assessment)
    return data


def create(assessment: Path, kind: str, fields: dict) -> dict:
    with LOCK:
        items, meta = read_records(assessment, kind), read_meta(assessment)
        if len(items) >= MAX_RECORDS:
            raise RecordError("too many records")
        record = {"id": new_id(KINDS[kind][1], items, meta), **clean(kind, fields)}
        write_meta(assessment, meta)  # the counter is saved first: an ID is never issued twice
        _write(assessment / f"{kind}.yaml", [*items, record])
    return {"record": record, "problems": problems(assessment)}


def update(assessment: Path, kind: str, ident: str, fields: dict) -> dict | None:
    with LOCK:
        items = read_records(assessment, kind)
        for n, item in enumerate(items):
            if item.get("id") == ident:
                items[n] = {"id": ident, **clean(kind, fields)}
                _write(assessment / f"{kind}.yaml", items)
                return {"record": items[n], "problems": problems(assessment)}
    return None


def delete(assessment: Path, kind: str, ident: str) -> dict | None:
    with LOCK:
        items = read_records(assessment, kind)
        kept = [i for i in items if i.get("id") != ident]
        if len(kept) == len(items):
            return None
        _write(assessment / f"{kind}.yaml", kept)  # the counter is untouched: the ID stays retired
    return {"problems": problems(assessment)}


def set_meta(assessment: Path, name: str, scale: int, slots: int) -> dict:
    with LOCK:
        meta = read_meta(assessment)
        try:
            meta = Meta(
                name=name[:200] or meta.name, scale=scale, slots=slots, counters=meta.counters
            )
        except Exception as e:
            raise RecordError("scale must be 3 or 5") from e
        if not 1 <= slots <= 50:
            raise RecordError("slots must be between 1 and 50")
        write_meta(assessment, meta)
        for kind in (
            "findings",
            "risks",
        ):  # a lower scale pulls existing scores down to its maximum
            items = read_records(assessment, kind)
            changed = False
            for item in items:
                for score in ("likelihood", "impact"):
                    if isinstance(item.get(score), int) and item[score] > scale:
                        item[score], changed = scale, True
            if changed:
                _write(assessment / f"{kind}.yaml", items)
    return snapshot(assessment)
