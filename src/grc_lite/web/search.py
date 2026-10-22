"""Search across the files you can see, your notes and your records."""

from pathlib import Path

from grc_lite.web import files, grades, records

MIN_QUERY = 2
MAX_QUERY = 100
MAX_HITS = 100
SNIPPET = 140


def _snippet(line: str, at: int, length: int) -> str:
    start = max(0, at - SNIPPET // 3)
    text = line[start : start + SNIPPET].strip()
    return ("..." if start else "") + text + ("..." if start + SNIPPET < len(line) else "")


def _scan(text: str, needle: str):
    """Yield (line number, snippet) for each line containing the needle, ignoring case."""
    for number, line in enumerate(text.splitlines(), 1):
        at = line.lower().find(needle)
        if at >= 0:
            yield number, _snippet(line, at, len(needle))


def search(level: Path, assessment: Path, query: str) -> dict:
    """Case-insensitive substring search. Only files the app is allowed to show are read, so a
    sealed answer key can never turn up in a result."""
    needle = query.strip().lower()
    if not MIN_QUERY <= len(needle) <= MAX_QUERY:
        raise records.RecordError(f"search needs {MIN_QUERY} to {MAX_QUERY} characters")
    hits: list[dict] = []
    reveal = grades.revealed(assessment)

    def add(hit: dict) -> bool:
        hits.append(hit)
        return len(hits) >= MAX_HITS

    done = False
    for path in files.list_files(level, reveal):
        if done:
            break
        found = files.resolve_visible(level, path, reveal)
        if found and found.stat().st_size <= files.MAX_BYTES:
            for number, snippet in _scan(found.read_text(errors="replace"), needle):
                if add({"kind": "file", "path": path, "line": number, "snippet": snippet}):
                    done = True
                    break
        note = files.notes_path(assessment, path)
        if not done and note.exists():
            for number, snippet in _scan(note.read_text(errors="replace"), needle):
                if add({"kind": "note", "path": path, "line": number, "snippet": snippet}):
                    done = True
                    break
    for kind in records.KINDS:
        for record in records.read_records(assessment, kind):
            if done:
                break
            for field, value in record.items():
                text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                at = text.lower().find(needle)
                if at >= 0:
                    hit = {"kind": "record", "record": kind, "id": record.get("id"),
                           "field": field, "snippet": _snippet(text, at, len(needle))}  # fmt: skip
                    if add(hit):
                        done = True
                    break
    return {"hits": hits, "truncated": len(hits) >= MAX_HITS}
