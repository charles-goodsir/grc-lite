"""Keep real client names out of commits.

The list of names lives outside the repository (a list inside it would publish the names), is
matched case-insensitively as plain text, and is never printed back: a hit reports the file and
line and which entry matched, not the name or the line.
"""

import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 2_000_000
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "collected"}


class GuardError(Exception):
    """The guard cannot do its job, which must never be mistaken for a clean result."""


@dataclass
class Hit:
    path: str
    line: int  # 0 means the file name itself
    entry: int  # 1-based position in the deny-list


def default_list() -> Path:
    return Path(
        os.environ.get("GRC_DENYLIST") or Path.home() / ".config" / "grc-lite" / "denylist.txt"
    )


def _repo_root(cwd: Path) -> Path | None:
    done = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(done.stdout.strip()).resolve() if done.returncode == 0 else None


def load_list(path: Path, cwd: Path) -> list[str]:
    """The names to reject. Fails closed: a missing, empty or in-repo list is an error."""
    path = path.expanduser()
    if not path.is_file():
        raise GuardError(
            f"no deny-list at {path}. Create one outside the repository, one name per line."
        )
    root = _repo_root(cwd)
    if root and path.resolve().is_relative_to(root):
        raise GuardError(
            "the deny-list is inside the repository, which would publish the names. Move it outside."
        )
    terms = [
        t.strip().lower()
        for t in path.read_text().splitlines()
        if t.strip() and not t.lstrip().startswith("#")
    ]
    if not terms:
        raise GuardError("the deny-list is empty, so nothing would be checked.")
    return terms


def scan_text(path: str, text: str, terms: list[str]) -> list[Hit]:
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        lowered = line.lower()
        hits += [Hit(path, number, n) for n, term in enumerate(terms, 1) if term in lowered]
    # file names write spaces as - or _, so compare the name with those turned back into spaces too
    plain = re.sub(r"[-_./\\]+", " ", path.lower())
    hits += [
        Hit(path, 0, n) for n, term in enumerate(terms, 1) if term in path.lower() or term in plain
    ]
    return hits


def _readable(data: bytes) -> str | None:
    if b"\0" in data[:8000] or len(data) > MAX_BYTES:
        return None  # binary or too big: skipped
    return data.decode("utf-8", errors="replace")


def scan_paths(paths: list[Path], terms: list[str]) -> tuple[list[Hit], int]:
    """Scan files and folders (not following links). Returns the hits and how many files were skipped."""
    hits, skipped = [], 0
    for top in paths:
        walk = (
            [top]
            if top.is_file() or top.is_symlink()
            else sorted(p for p in top.rglob("*") if not SKIP_DIRS & set(p.parts))
        )
        for path in walk:
            if path.is_symlink() or not path.is_file():
                continue
            text = _readable(path.read_bytes())
            if text is None:
                skipped += 1
                continue
            hits += scan_text(str(path), text, terms)
    return hits, skipped


def scan_staged(cwd: Path, terms: list[str]) -> tuple[list[Hit], int]:
    """Scan what is about to be committed (the index), not the working tree."""
    names = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], cwd=cwd,
                           capture_output=True, text=True, check=False)  # fmt: skip
    if names.returncode != 0:
        raise GuardError("could not list the staged files; is this a Git repository?")
    hits, skipped = [], 0
    for name in filter(None, names.stdout.split("\0")):
        shown = subprocess.run(
            ["git", "show", f":{name}"], cwd=cwd, capture_output=True, check=False
        )
        text = _readable(shown.stdout) if shown.returncode == 0 else None
        if text is None:
            skipped += 1
            continue
        hits += scan_text(name, text, terms)
    return hits, skipped


def install_hook(cwd: Path) -> Path:
    """Write a pre-commit hook that runs the staged scan. Never overwrites an existing hook."""
    done = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise GuardError("not a Git repository")
    hook = (cwd / done.stdout.strip()).resolve() / "pre-commit"
    if hook.exists():
        raise GuardError(
            f"{hook} already exists. Add the guard to it by hand: {sys.executable} -m grc_lite guard-names --staged"
        )
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m grc_lite guard-names --staged\n')
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return hook
