from pathlib import Path

import pytest

from grc_lite.loader import AssessmentError, load

CRITERIA = "- {id: C-01, source: Policy 1, rule: Do the thing, evidence: [E-01]}\n"
EVIDENCE = "- {id: E-01, date: 2026-01-05, source: Export, type: system, shows: it works}\n"
SELECTED = """
- id: F-01
  title: Thing missing
  status: selected
  strength: strong
  strength_reason: System export
  criteria: [C-01]
  condition: c
  consequence: q
  action: a
  owner: IT
  due: 2026-06-30
  likelihood: 2
  likelihood_reason: l
  impact: 3
  impact_reason: i
"""


def write(folder: Path, **files: str) -> Path:
    for name, text in files.items():
        (folder / f"{name}.yaml").write_text(text)
    return folder


def errors_for(folder: Path) -> list[str]:
    with pytest.raises(AssessmentError) as exc:
        load(folder)
    return exc.value.errors


def test_valid_assessment_loads(tmp_path):
    a = load(write(tmp_path, criteria=CRITERIA, evidence=EVIDENCE, findings=SELECTED))
    assert (len(a.criteria), len(a.evidence), len(a.findings)) == (1, 1, 1)


def test_empty_folder_is_an_error(tmp_path):
    assert "no assessment files" in errors_for(tmp_path)[0]


def test_missing_file_counts_as_empty(tmp_path):
    assert load(write(tmp_path, criteria="[]")).findings == []


def test_unknown_evidence_reference(tmp_path):
    errs = errors_for(write(tmp_path, criteria=CRITERIA))
    assert errs == ["criteria.yaml: C-01: unknown evidence E-01"]


def test_unknown_criterion_reference(tmp_path):
    errs = errors_for(write(tmp_path, evidence=EVIDENCE, findings=SELECTED))
    assert errs == ["findings.yaml: F-01: unknown criterion C-01"]


def test_duplicate_ids(tmp_path):
    errs = errors_for(write(tmp_path, evidence=EVIDENCE + EVIDENCE))
    assert errs == ["evidence.yaml: duplicate id E-01"]


def test_score_outside_scale(tmp_path):
    bad = SELECTED.replace("impact: 3", "impact: 5")
    errs = errors_for(write(tmp_path, criteria=CRITERIA, evidence=EVIDENCE, findings=bad))
    assert "impact 5 is outside the 1-3 scale" in errs[0]


def test_scale_5_allows_higher_scores(tmp_path):
    bad = SELECTED.replace("impact: 3", "impact: 5")
    folder = write(
        tmp_path, assessment="scale: 5", criteria=CRITERIA, evidence=EVIDENCE, findings=bad
    )
    assert load(folder).meta.scale == 5


def test_all_errors_reported_with_file_and_id(tmp_path):
    bad = "- {id: C-01, source: s, rule: r, result: maybe}\n- {id: nope, source: s, rule: r}\n"
    errs = errors_for(write(tmp_path, criteria=bad))
    assert len(errs) == 2
    assert errs[0].startswith("criteria.yaml: C-01: result")
    assert errs[1].startswith("criteria.yaml: nope: id")


def test_invalid_yaml(tmp_path):
    assert "invalid YAML" in errors_for(write(tmp_path, criteria="- [unclosed"))[0]


REQUESTS = "- {id: R-01, asked: 2026-01-05, what: Access review, asked_who: CISO}\n"


def test_requests_load_and_unknown_evidence_is_flagged(tmp_path):
    assert load(write(tmp_path, requests=REQUESTS)).requests[0].outstanding
    bad = REQUESTS.replace("}", ", evidence: E-09}")
    assert errors_for(write(tmp_path, requests=bad)) == [
        "requests.yaml: R-01: unknown evidence E-09"
    ]


def test_request_received_before_asked_is_rejected(tmp_path):
    bad = REQUESTS.replace("}", ", received: 2026-01-01}")
    assert "received is before asked" in errors_for(write(tmp_path, requests=bad))[0]
