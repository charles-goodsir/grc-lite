"""Which files the web app may show, and safe handling of the paths it is given."""

from pathlib import Path, PurePosixPath

SHOWN = {".md", ".csv", ".txt"}
MAX_BYTES = 2_000_000


def is_hidden(rel: Path, reveal: bool = False) -> bool:
    """Dotfiles, CLAUDE.md and my-work/ are never shown. Answer keys and graded/ are hidden until
    `reveal`, which the app sets only for a submitted level that has been graded."""
    parts = rel.parts
    if not parts:
        return True
    top = parts[0].lower()
    if top == "my-work" or (top == "graded" and not reveal):
        return True
    return any(
        p.startswith(".")
        or p.lower() == "claude.md"
        or (not reveal and p.lower().startswith("answer-key"))
        for p in parts
    )


def resolve_visible(root: Path, rel: str, reveal: bool = False) -> Path | None:
    """Return the file for a client-supplied relative path, or None if it must not be served.

    The path is checked as given and again after symlinks are resolved, so neither `..` nor a
    link inside the folder can reach a hidden file or anything outside the root.
    """
    pure = PurePosixPath(rel)
    if not rel or "\0" in rel or "\\" in rel or pure.is_absolute() or ".." in pure.parts:
        return None
    if is_hidden(Path(*pure.parts), reveal):
        return None
    base = root.resolve()
    candidate = (base / Path(*pure.parts)).resolve()
    if not candidate.is_relative_to(base) or candidate == base:
        return None
    if is_hidden(candidate.relative_to(base), reveal):
        return None
    if candidate.suffix.lower() not in SHOWN or not candidate.is_file():
        return None
    return candidate


def list_files(root: Path, reveal: bool = False) -> list[str]:
    """Every file the app may show, as sorted POSIX-style relative paths."""
    base = root.resolve()
    found = []
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if path.suffix.lower() in SHOWN and resolve_visible(base, rel.as_posix(), reveal):
            found.append(rel.as_posix())
    return found


def notes_path(assessment: Path, rel: str) -> Path:
    """Notes for a file live in one flat folder inside the assessment folder."""
    return assessment / "notes" / (rel.replace("/", "__") + ".md")
