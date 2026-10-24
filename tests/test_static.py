"""The page runs under a strict CSP and draws untrusted text, so a few patterns are banned in its
own code: anything that parses HTML from a string, and inline styles or scripts."""

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "src" / "grc_lite" / "web" / "static"
JS = sorted(STATIC.glob("*.js"))
BANNED = {
    "innerHTML": r"\.innerHTML\b",
    "outerHTML": r"\.outerHTML\b",
    "insertAdjacentHTML": r"insertAdjacentHTML",
    "document.write": r"document\.write\(",
    "eval": r"\beval\(",
    "Function constructor": r"new Function\(",
    "style attribute (blocked by the CSP, so it silently does nothing)": r"""setAttribute\(\s*["']style["']|\bstyle:\s*[`"']""",
    "javascript: URL": r"javascript:",
}


def test_there_are_modules_to_check():
    assert {p.name for p in JS} >= {"app.js", "records.js", "md.js", "csv.js", "ui.js", "layout.js"}


@pytest.mark.parametrize("path", JS, ids=lambda p: p.name)
@pytest.mark.parametrize(("name", "pattern"), BANNED.items(), ids=list(BANNED))
def test_banned_patterns_are_absent(path, name, pattern):
    hits = [
        n for n, line in enumerate(path.read_text().splitlines(), 1) if re.search(pattern, line)
    ]
    assert not hits, f"{path.name} lines {hits} use {name}"


def test_the_page_shell_has_no_inline_script_style_or_handlers():
    page = (STATIC / "index.html").read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)", page)
    assert not re.search(r"<style|\sstyle=|\son\w+=", page)
    assert page.count('type="module"') == 1


PANELS = {"side": 1, "split1": 2, "view": 3, "split2": 4, "right": 5}


def test_every_panel_keeps_its_own_grid_column():
    """Hiding a panel with display:none drops it from the grid, so the others would slide into the
    wrong columns (a 56px reading pane and a huge right panel). Each panel must name its column."""
    css = (STATIC / "style.css").read_text()
    for panel, column in PANELS.items():
        assert re.search(rf"#{panel}\s*\{{[^}}]*grid-column:\s*{column}\b", css), (
            f"#{panel} is not pinned to column {column}"
        )


def test_the_panels_appear_in_the_page_in_column_order():
    page = (STATIC / "index.html").read_text()
    positions = [page.index(f'id="{panel}"') for panel in PANELS]
    assert positions == sorted(positions)
