"""Check that an ID is never reused after it was deleted, by reading the Git history.

Every commit that touched a records file is read back, plus the working tree, so an ID that
vanished and later came back is found even when the deletion was committed long ago.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS = ("criteria", "evidence", "findings", "requests", "risks")
MAX_COMMITS = 5000


class GitError(Exception):
    pass


@dataclass
class Reuse:
    kind: str
    id: str
    first_seen: str
    deleted_in: str
    returned_in: str


def _git(folder: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=folder, capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GitError("could not run git") from None
    if done.returncode != 0:
        raise GitError(done.stderr.strip().splitlines()[0] if done.stderr.strip() else "git failed")
    return done.stdout


def _ids(text: str) -> set[str] | None:
    """The record IDs in one version of a records file, or None if it cannot be read."""
    try:
        items = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if items is None:
        return set()
    if not isinstance(items, list):
        return None
    return {str(i["id"]) for i in items if isinstance(i, dict) and "id" in i}


def find_reuse(folder: Path) -> tuple[list[Reuse], list[str], int]:
    """Return (reused IDs, warnings, number of commits read). Raises GitError outside a repository."""
    folder = folder.resolve()
    _git(folder, "rev-parse", "--show-toplevel")  # fails with a clear message outside a repository
    warnings = []
    if _git(folder, "rev-parse", "--is-shallow-repository").strip() == "true":
        warnings.append(
            "this repository is a shallow clone, so older history is missing and some reuse may go unseen"
        )
    reused: list[Reuse] = []
    commits_read = 0
    for kind in KINDS:
        name = f"{kind}.yaml"  # paths are relative to the assessment folder, which is git's working directory
        try:
            log = _git(
                folder, "log", "--reverse", f"--max-count={MAX_COMMITS}", "--format=%H", "--", name
            ).split()
        except GitError as e:
            if "does not have any commits" not in str(e):
                raise
            log = []  # nothing committed yet, so only the working tree exists
        snapshots: list[tuple[str, set[str] | None]] = []
        for sha in log:
            try:
                snapshots.append((sha[:8], _ids(_git(folder, "show", f"{sha}:./{name}"))))
            except GitError:
                snapshots.append((sha[:8], set()))  # the file did not exist in that commit
        commits_read += len(log)
        current = folder / f"{kind}.yaml"
        snapshots.append(("working tree", _ids(current.read_text()) if current.exists() else set()))

        previous: set[str] = set()
        first_seen: dict[str, str] = {}
        deleted_in: dict[str, str] = {}
        for label, ids in snapshots:
            if ids is None:
                warnings.append(f"{kind}.yaml in {label} could not be read, so it was skipped")
                continue
            for ident in sorted(ids & deleted_in.keys()):
                reused.append(Reuse(kind, ident, first_seen[ident], deleted_in.pop(ident), label))
            for ident in previous - ids:
                deleted_in[ident] = label
            for ident in ids:
                first_seen.setdefault(ident, label)
            previous = ids
    return reused, warnings, commits_read
