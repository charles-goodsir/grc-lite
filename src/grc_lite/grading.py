"""Read a grading file: the Markdown a grader returns after reviewing a submitted level.

Layout (the one notes_to_xlsx.py reads): tables under "Grader notes", "Planted items",
"Grading summary", "Done well" and "For next time", and "### F-10: title" blocks under "Findings"
for gaps the assessor missed. Anything that does not fit is reported, never guessed.
"""

import re

from pydantic import BaseModel

from grc_lite.importer import read_table, split_sections

TAGS = [
    "missed gap",
    "wrong rating",
    "miscounted",
    "conditional rule not tested",
    "cause missing",
    "weak evidence selected",
    "unverified claim",
    "other",
]
MAX_ROWS = 300
MAX_TEXT = 5_000

# "for next time" points that name a recognisable kind of mistake; anything else is left for the
# learner to tag. These are suggestions, shown as such, and can be changed.
KEYWORD_TAGS = [
    ("cause", "cause missing"),
    ("conditional", "conditional rule not tested"),
    ("claim", "unverified claim"),
    ("count", "miscounted"),
    ("rate", "wrong rating"),
    ("rating", "wrong rating"),
]


class GraderNote(BaseModel):
    sheet: str
    id: str
    key_rating: str = ""
    note: str


class Planted(BaseModel):
    number: str
    gap: str
    result: str
    outcome: str  # caught, rated_low, rated_high, missed or other
    your_rating: str = ""
    key_rating: str = ""
    finding: str = ""


class Point(BaseModel):
    point: str
    detail: str


class Added(BaseModel):
    id: str
    title: str
    text: str


class Mistake(BaseModel):
    id: str
    source: str
    text: str
    tag: str


class Grading(BaseModel):
    title: str
    notes: list[GraderNote] = []
    planted: list[Planted] = []
    summary: list[Point] = []
    done_well: list[Point] = []
    next_time: list[Point] = []
    added: list[Added] = []
    mistakes: list[Mistake] = []
    warnings: list[str] = []


def outcome(result: str) -> str:
    lowered = result.replace("*", "").strip().lower()  # tolerate **bold** in the table
    if lowered.startswith("missed"):
        return "missed"
    if lowered.startswith("caught"):
        if "too low" in lowered:
            return "rated_low"
        if "too high" in lowered:
            return "rated_high"
        return "caught"
    return "other"


def _clip(text: str) -> str:
    return text.strip()[:MAX_TEXT]


def _rows(sections: dict, name: str, width: int, warnings: list[str]) -> list[list[str]]:
    if name not in sections:
        warnings.append(f"no '{name}' section found")
        return []
    rows = read_table(sections[name])[:MAX_ROWS]
    return [([_clip(c) for c in r] + [""] * width)[:width] for r in rows]


def _suggest_tag(text: str) -> str:
    lowered = text.lower()
    return next((tag for word, tag in KEYWORD_TAGS if word in lowered), "other")


def _blocks(lines: list[str]) -> list[Added]:
    out: list[Added] = []
    for line in lines:
        head = re.match(r"### ([A-Z]-\d+): ?(.*)", line)
        if head:
            out.append(Added(id=head.group(1), title=_clip(head.group(2)), text=""))
        elif out:
            out[-1].text += line + "\n"
    return [Added(id=a.id, title=a.title, text=_clip(a.text)) for a in out[:MAX_ROWS]]


def parse_grading(text: str) -> Grading:
    """Parse a grading file. Raises ValueError if it has none of the expected sections."""
    sections = split_sections(text)
    known = {"Grader notes", "Planted items", "Grading summary", "Done well", "For next time"}
    if not known & set(sections):
        raise ValueError("this does not look like a grading file: none of its sections were found")
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "Grading")
    warnings: list[str] = []
    grading = Grading(title=_clip(title))
    for sheet, ident, key, note in _rows(sections, "Grader notes", 4, warnings):
        grading.notes.append(GraderNote(sheet=sheet, id=ident, key_rating=key, note=note))
    for number, gap, result, yours, key, finding in _rows(sections, "Planted items", 6, warnings):
        grading.planted.append(
            Planted(number=number, gap=gap, result=result, outcome=outcome(result),
                    your_rating=yours, key_rating=key, finding=finding)
        )  # fmt: skip
    for target, name in (("summary", "Grading summary"), ("done_well", "Done well"),
                         ("next_time", "For next time")):  # fmt: skip
        getattr(grading, target).extend(
            Point(point=a, detail=b) for a, b in _rows(sections, name, 2, warnings)
        )
    grading.added = _blocks(sections.get("Findings", []))
    for planted in grading.planted:
        if planted.outcome != "caught":
            tag = {
                "missed": "missed gap",
                "rated_low": "wrong rating",
                "rated_high": "wrong rating",
            }.get(planted.outcome, "other")
            grading.mistakes.append(Mistake(id="", source=f"planted item {planted.number}",
                                            text=planted.gap, tag=tag))  # fmt: skip
    for point in grading.next_time:
        grading.mistakes.append(Mistake(id="", source=f"for next time {point.point}",
                                        text=point.detail, tag=_suggest_tag(point.detail)))  # fmt: skip
    for n, mistake in enumerate(grading.mistakes, 1):
        mistake.id = f"M-{n:02d}"
    grading.warnings = warnings
    return grading
