"""Load an assessment folder of YAML files and check it hangs together."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from grc_lite.models import Criterion, Evidence, Finding, Meta, Request

FILES = {
    "criteria": Criterion,
    "evidence": Evidence,
    "findings": Finding,
    "requests": Request,
}


class AssessmentError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Assessment:
    meta: Meta
    criteria: list[Criterion]
    evidence: list[Evidence]
    findings: list[Finding]
    requests: list[Request] = field(default_factory=list)


def _read(path: Path) -> object:
    """Parse one YAML file; a missing file is an empty one."""
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


def _parse(path: Path, model: type[BaseModel], errors: list[str]) -> list:
    try:
        raw = _read(path)
    except yaml.YAMLError as e:
        errors.append(f"{path.name}: invalid YAML: {e}")
        return []
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(f"{path.name}: expected a list of entries")
        return []
    items = []
    for n, entry in enumerate(raw, 1):
        label = entry.get("id", f"entry {n}") if isinstance(entry, dict) else f"entry {n}"
        try:
            items.append(model.model_validate(entry))
        except ValidationError as e:
            for err in e.errors():
                where = ".".join(str(p) for p in err["loc"])
                errors.append(f"{path.name}: {label}: {where + ': ' if where else ''}{err['msg']}")
    return items


def _duplicates(name: str, items: list, errors: list[str]) -> None:
    seen = set()
    for item in items:
        if item.id in seen:
            errors.append(f"{name}.yaml: duplicate id {item.id}")
        seen.add(item.id)


def load(folder: Path) -> Assessment:
    """Load and validate an assessment folder; raise AssessmentError listing every problem."""
    folder = Path(folder)
    if not folder.is_dir():
        raise AssessmentError([f"{folder}: not a directory"])
    names = [*FILES, "assessment"]
    if not any((folder / f"{n}.yaml").exists() for n in names):
        raise AssessmentError([f"{folder}: no assessment files found (run `grc init`)"])

    errors: list[str] = []
    meta_items = _parse_meta(folder / "assessment.yaml", errors)
    parsed = {n: _parse(folder / f"{n}.yaml", m, errors) for n, m in FILES.items()}
    a = Assessment(meta_items, **parsed)

    for name, items in parsed.items():
        _duplicates(name, items, errors)
    _check_references(a, errors)
    if errors:
        raise AssessmentError(errors)
    return a


def _parse_meta(path: Path, errors: list[str]) -> Meta:
    try:
        raw = _read(path) or {}
        return Meta.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as e:
        errors.append(f"{path.name}: {e}")
        return Meta()


def _check_references(a: Assessment, errors: list[str]) -> None:
    evidence_ids = {e.id for e in a.evidence}
    criteria_ids = {c.id for c in a.criteria}
    for c in a.criteria:
        for ref in c.evidence:
            if ref not in evidence_ids:
                errors.append(f"criteria.yaml: {c.id}: unknown evidence {ref}")
    for r in a.requests:
        if r.evidence and r.evidence not in evidence_ids:
            errors.append(f"requests.yaml: {r.id}: unknown evidence {r.evidence}")
    for f in a.findings:
        for ref in f.criteria:
            if ref not in criteria_ids:
                errors.append(f"findings.yaml: {f.id}: unknown criterion {ref}")
        for score in ("likelihood", "impact"):
            value = getattr(f, score)
            if value is not None and not 1 <= value <= a.meta.scale:
                errors.append(
                    f"findings.yaml: {f.id}: {score} {value} is outside the 1-{a.meta.scale} scale"
                )
