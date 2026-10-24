"""Every example assessment shipped in data/ must be valid, reportable and free of coach fixes."""

import re
from datetime import date
from pathlib import Path

import pytest

from grc_lite.coach import coach
from grc_lite.loader import load
from grc_lite.report import build_report
from grc_lite.web import records

DATA = Path(__file__).parent.parent / "data"
EXAMPLES = sorted(p for p in DATA.iterdir() if p.is_dir())


def raw(folder):
    return {kind: records.read_records(folder, kind) for kind in records.KINDS}


def test_the_examples_are_found():
    assert {p.name for p in EXAMPLES} >= {"example", "essential-eight"}


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda p: p.name)
def test_example_validates_and_reports(folder):
    assessment = load(folder)
    assert assessment.criteria and "## Findings" in build_report(assessment, date(2026, 10, 24))


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda p: p.name)
def test_selected_findings_pass_the_coach(folder):
    fixes = {
        fid: [i["rule"] for i in issues if i["level"] == "fix"]
        for fid, issues in coach(raw(folder), records.read_meta(folder).scale).items()
    }
    assert {k: v for k, v in fixes.items() if v} == {}


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda p: p.name)
def test_example_ids_were_never_reused(folder):
    from grc_lite.idcheck import GitError, find_reuse

    try:
        reused, _, _ = find_reuse(folder)
    except GitError:
        pytest.skip("no Git history available")
    assert reused == []


ESSENTIAL_EIGHT = ["application control", "patch applications", "patch operating systems", "multi-factor authentication",
                   "restrict administrative privileges", "restrict microsoft office macros", "user application hardening",
                   "regular backups"]  # fmt: skip


def test_essential_eight_example_covers_all_eight_strategies_and_cites_its_source():
    criteria = records.read_records(DATA / "essential-eight", "criteria")
    sources = " ".join(c["source"].lower() for c in criteria)
    assert all(name in sources for name in ESSENTIAL_EIGHT)
    assert all(
        "asd essential eight maturity model" in c["source"].lower()
        and "27 nov 2023" in c["source"].lower()
        for c in criteria
    )


def test_essential_eight_rules_are_short_paraphrases_not_pasted_passages():
    for c in records.read_records(DATA / "essential-eight", "criteria"):
        assert len(c["rule"]) <= 260, f"{c['id']} is long enough to be a quotation"
        assert not re.search(r"\bis used to\b.*\bis used to\b", c["rule"])
