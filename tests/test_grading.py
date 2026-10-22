from pathlib import Path

import pytest

from grc_lite.grading import TAGS, outcome, parse_grading

FIXTURE = Path(__file__).parent / "fixtures" / "grading.md"


def test_fixture_parses_every_section():
    g = parse_grading(FIXTURE.read_text())
    assert g.warnings == []
    assert g.title == "Northwind Traders (fictional): grading"
    assert [(n.sheet, n.id) for n in g.notes] == [
        ("Criteria", "C-02"), ("Evidence", "E-02"), ("Candidates", "F-02"), ("Findings", "F-01")
    ]  # fmt: skip
    assert g.notes[3].key_rating == "6 Medium"
    assert [p.outcome for p in g.planted] == ["caught", "rated_low", "rated_high", "missed"]
    assert g.planted[1].your_rating == "2" and g.planted[1].key_rating == "6"
    assert g.summary[0].point == "Planted gaps caught"
    assert g.done_well[0].detail.startswith("Dropped the weak")
    assert [a.id for a in g.added] == ["F-10"]
    assert "Likelihood 3" in g.added[0].text


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("Caught", "caught"),
        ("Caught, rated too low", "rated_low"),
        ("caught, **rated too high**", "rated_high"),
        ("**Missed**", "missed"),
        ("Missed", "missed"),
        ("Partly", "other"),
    ],
)
def test_outcomes(result, expected):
    assert outcome(result) == expected


def test_mistake_log_covers_every_miss_and_every_next_time_point():
    g = parse_grading(FIXTURE.read_text())
    assert [m.id for m in g.mistakes] == [f"M-{n:02d}" for n in range(1, 8)]
    by_source = {m.source: m.tag for m in g.mistakes}
    assert by_source["planted item 2"] == "wrong rating"
    assert by_source["planted item 3"] == "wrong rating"
    assert by_source["planted item 4"] == "missed gap"
    assert by_source["for next time 1"] == "conditional rule not tested"
    assert by_source["for next time 2"] == "cause missing"
    assert by_source["for next time 3"] == "unverified claim"
    assert by_source["for next time 4"] == "other"  # nothing recognisable, so left to the learner
    assert all(m.tag in TAGS for m in g.mistakes)


def test_missing_sections_are_reported_not_guessed():
    g = parse_grading(
        "# Grading\n\n## Planted items\n\n| # | Gap | Result | Y | K | F |\n| - | - | - | - | - | - |\n| 1 | x | Caught | 1 | 1 | F-01 |\n"
    )
    assert "no 'Grader notes' section found" in g.warnings
    assert "no 'For next time' section found" in g.warnings
    assert len(g.planted) == 1


def test_a_file_with_none_of_the_sections_is_refused():
    with pytest.raises(ValueError, match="does not look like a grading file"):
        parse_grading("# Just notes\n\nSome text\n")


def test_short_rows_are_padded_and_long_text_is_clipped():
    text = "# G\n\n## Grader notes\n\n| Sheet | ID | Key rating | Grader note |\n| - | - | - | - |\n| Criteria | C-01 |\n"
    g = parse_grading(text)
    assert g.notes[0].note == "" and g.notes[0].id == "C-01"
    long = "## Done well\n\n| Point | Detail |\n| - | - |\n| a | " + "x" * 9000 + " |\n"
    assert len(parse_grading("# G\n\n" + long).done_well[0].detail) == 5000


def test_row_count_is_capped():
    rows = "\n".join(f"| P{n} | d |" for n in range(500))
    g = parse_grading("# G\n\n## Done well\n\n| Point | Detail |\n| - | - |\n" + rows + "\n")
    assert len(g.done_well) == 300
