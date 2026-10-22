import pytest
from pydantic import ValidationError

from grc_lite.models import Criterion, Finding, rating

FINDING = {
    "id": "F-01",
    "title": "t",
    "status": "candidate",
    "strength": "weak",
    "strength_reason": "r",
}


def test_criterion_defaults_to_not_tested():
    assert Criterion(id="C-01", source="s", rule="r").result.value == "not tested"


def test_bad_id_rejected():
    with pytest.raises(ValidationError):
        Criterion(id="X-1", source="s", rule="r")


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Criterion(id="C-01", source="s", rule="r", reslt="gap")


def test_candidate_needs_no_extras():
    Finding(**FINDING)


def test_selected_requires_full_detail():
    with pytest.raises(ValidationError, match="missing: .*owner"):
        Finding(**{**FINDING, "status": "selected"})


@pytest.mark.parametrize(
    ("l", "i", "scale", "expected"),
    [
        (1, 3, 3, "Low"),
        (2, 2, 3, "Medium"),
        (3, 3, 3, "High"),
        (2, 3, 3, "Medium"),
        (5, 5, 5, "Critical"),
        (4, 5, 5, "Critical"),
        (4, 4, 5, "High"),
        (3, 4, 5, "Medium"),
        (1, 5, 5, "Low"),
        (2, 3, 5, "Medium"),
    ],
)
def test_rating_bands(l, i, scale, expected):
    assert rating(l, i, scale) == expected
