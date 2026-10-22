"""Progress across levels. Reads exactly one file per level, my-work/assessment/grading.yaml,
and only checks that submitted.yaml exists. It never opens a level's data room or answer key."""

from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from grc_lite.grading import Grading

MAX_BYTES = 1_000_000
ASSESSMENT = Path("my-work") / "assessment"


def level_dirs(root: Path) -> list[Path]:
    """The level folders directly inside root: real folders (not links) holding 01-scope.md or
    a data-room folder. Nothing deeper is listed."""
    out = []
    if not root.is_dir():
        return out
    for path in sorted(root.resolve().iterdir()):
        try:
            if path.name.startswith(".") or path.is_symlink() or not path.is_dir():
                continue
            if (path / "01-scope.md").is_file() or (path / "data-room").is_dir():
                out.append(path)
        except OSError:
            continue  # a folder we may not read is skipped, not fatal
    return out


def _read_grading(path: Path) -> tuple[Grading | None, str]:
    """(grading, "") when readable, (None, reason) when the file is there but cannot be used."""
    if path.is_symlink() or not path.is_file():
        return None, "grading.yaml is not a regular file"
    if path.stat().st_size > MAX_BYTES:
        return None, "grading.yaml is too large"
    try:
        return Grading.model_validate(yaml.safe_load(path.read_text())), ""
    except (yaml.YAMLError, ValidationError, UnicodeDecodeError):
        return None, "grading.yaml could not be read"


def level_progress(level: Path, assessment: Path, current: bool) -> dict:
    grading_path, submitted_path = assessment / "grading.yaml", assessment / "submitted.yaml"
    info = {"name": level.name, "current": current, "status": "not started", "error": ""}
    if grading_path.exists() or grading_path.is_symlink():
        grading, error = _read_grading(grading_path)
        if grading is None:
            return {**info, "status": "unreadable", "error": error}
        outcomes = Counter(p.outcome for p in grading.planted)
        total = len(grading.planted)
        caught = outcomes["caught"] + outcomes["rated_low"] + outcomes["rated_high"]
        return {
            **info,
            "status": "graded",
            "planted": {"total": total, "caught": caught, "missed": total - caught,
                        "rated_off": outcomes["rated_low"] + outcomes["rated_high"]},
            "mistakes": dict(Counter(m.tag for m in grading.mistakes)),
        }  # fmt: skip
    if submitted_path.is_file():
        return {**info, "status": "submitted"}
    if assessment.is_dir() and any(assessment.glob("*.yaml")):
        return {**info, "status": "in progress"}
    return info


def progress(root: Path, current_level: Path, current_assessment: Path) -> dict:
    here = current_level.resolve()
    levels = []
    seen_current = False
    for level in level_dirs(root):
        is_current = level == here
        seen_current = seen_current or is_current
        assessment = current_assessment if is_current else level / ASSESSMENT
        levels.append(level_progress(level, assessment, is_current))
    if not seen_current:  # the level being served counts even if root is somewhere else
        levels.append(level_progress(here, current_assessment, True))
    graded = [lv for lv in levels if lv["status"] == "graded"]
    mistakes: Counter = Counter()
    for lv in graded:
        mistakes.update(lv["mistakes"])
    planted = sum(lv["planted"]["total"] for lv in graded)
    caught = sum(lv["planted"]["caught"] for lv in graded)
    return {
        "levels": levels,
        "totals": {"graded": len(graded), "planted": planted, "caught": caught,
                   "mistakes": dict(mistakes.most_common())},
    }  # fmt: skip
