from datetime import date

import pytest

from grc_lite.coach import check_finding, coach, presubmit

TODAY = date(2026, 3, 10)
CRITERIA = {"C-01": {"id": "C-01", "result": "gap"}, "C-02": {"id": "C-02", "result": "meets"}}
EVIDENCE = {"E-01", "E-02"}


def good(**changes):
    finding = {
        "id": "F-01", "title": "Leavers keep access", "status": "selected", "strength": "strong",
        "criteria": ["C-01"], "condition": "5 of 30 leavers are enabled (E-01).",
        "cause": "Leavers are reported by email only.", "likelihood": 3, "impact": 3,
        "likelihood_reason": "It is already happening.",
    }  # fmt: skip
    return {**finding, **changes}


def rules(finding, scale=3):
    return [i["rule"] for i in check_finding(finding, CRITERIA, EVIDENCE, scale)]


def test_a_complete_finding_has_no_issues():
    assert rules(good()) == []


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"cause": ""}, "cause_missing"),
        ({"cause": "   "}, "cause_missing"),
        ({"condition": "Many leavers are still enabled (E-01)."}, "condition_no_number"),
        ({"condition": "5 of 30 leavers are enabled."}, "condition_no_evidence"),
        ({"condition": "5 of 30 leavers are enabled (E-09)."}, "unknown_evidence"),
        ({"strength": "weak"}, "weak_selected"),
        ({"strength": ""}, "weak_selected"),
        ({"criteria": ["C-02"]}, "criterion_not_gap"),
        ({"likelihood": 2}, "likelihood_wording"),
        ({"likelihood_reason": "It has happened already.", "likelihood": 1}, "likelihood_wording"),
        ({"title": "MFA off and leavers enabled"}, "title_two_issues"),
    ],
)
def test_each_rule_fires_when_it_should(changes, rule):
    assert rule in rules(good(**changes))


def test_evidence_references_accept_the_notes_tool_style():
    assert rules(good(condition="5 of 30 leavers are enabled (Ev-1).")) == []
    assert "unknown_evidence" in rules(good(condition="5 of 30 enabled (Ev-7)."))


def test_wording_rule_follows_the_scale():
    five = good(likelihood=5)
    assert "likelihood_wording" not in rules(five, scale=5)
    assert "likelihood_wording" in rules(good(likelihood=4), scale=5)


def test_unlikely_wording_with_a_high_score_is_a_tip():
    found = check_finding(
        good(likelihood_reason="This is unlikely to recur.", likelihood=3), CRITERIA, EVIDENCE, 3
    )
    assert [(i["rule"], i["level"]) for i in found] == [("likelihood_wording", "tip")]


def test_candidates_and_dropped_findings_are_not_held_to_the_full_standard():
    for status in ("candidate", "dropped"):
        assert rules({"id": "F-02", "title": "Weak", "status": status}) == []


def test_issues_carry_a_mistake_tag_and_a_level():
    found = {
        i["rule"]: i for i in check_finding(good(cause="", strength="weak"), CRITERIA, EVIDENCE, 3)
    }
    assert (
        found["cause_missing"]["tag"] == "cause missing"
        and found["cause_missing"]["level"] == "fix"
    )
    assert (
        found["weak_selected"]["tag"] == "weak evidence selected"
        and found["weak_selected"]["level"] == "tip"
    )


def test_coach_reports_only_findings_with_issues():
    data = {
        "criteria": list(CRITERIA.values()),
        "evidence": [{"id": "E-01"}],
        "findings": [good(), good(id="F-02", cause="")],
    }
    assert list(coach(data, 3)) == ["F-02"]


def data(**extra):
    base = {
        "criteria": [
            {"id": "C-01", "result": "gap", "evidence": ["E-01"]},
            {"id": "C-02", "result": "meets", "evidence": ["E-01"]},
        ],
        "evidence": [{"id": "E-01", "reliability": "Exported by the client."}],
        "findings": [good()],
        "requests": [],
    }
    return {**base, **extra}


def by_key(result):
    return {c["key"]: c for c in result["checks"]}


def test_a_ready_level_passes_every_check():
    result = presubmit(data(), scale=3, slots=1, problems=0, history={}, today=TODAY)
    assert {c["key"]: c["status"] for c in result["checks"]} == {
        "problems": "ok", "results": "ok", "candidates": "ok", "gaps": "ok", "coach": "ok", "slots": "ok", "reliability": "ok"
    }  # fmt: skip


def test_each_check_flags_its_own_problem():
    thin = data(
        criteria=[
            {"id": "C-01", "result": "gap"},
            {"id": "C-02"},
            {"id": "C-03", "result": "can't test"},
        ],
        evidence=[{"id": "E-01"}],
        findings=[good(cause=""), {"id": "F-02", "title": "x", "status": "candidate"}],
    )
    got = by_key(presubmit(thin, scale=3, slots=3, problems=2, history={}, today=TODAY))
    assert got["problems"]["status"] == "fix"
    assert got["results"]["ids"] == ["C-02"]
    assert got["candidates"]["ids"] == ["F-02"]
    assert got["coach"]["ids"] == ["F-01"] and got["coach"]["status"] == "fix"
    assert got["slots"]["status"] == "warn" and "1 of 3" in got["slots"]["detail"]
    assert got["requests"]["status"] == "warn"
    assert got["reliability"]["ids"] == ["E-01"] and got["reliability"]["status"] == "warn"


def test_a_gap_with_no_finding_is_flagged():
    got = by_key(
        presubmit(data(findings=[]), scale=3, slots=0, problems=0, history={}, today=TODAY)
    )
    assert got["gaps"]["ids"] == ["C-01"]


def test_too_many_selected_is_a_fix_not_a_warning():
    over = data(findings=[good(), good(id="F-02")])
    assert (
        by_key(presubmit(over, scale=3, slots=1, problems=0, history={}, today=TODAY))["slots"][
            "status"
        ]
        == "fix"
    )


def test_a_request_per_cant_test_rule_satisfies_the_check():
    ready = data(criteria=[{"id": "C-03", "result": "can't test"}], requests=[{"id": "R-01"}])
    assert (
        by_key(presubmit(ready, scale=3, slots=1, problems=0, history={}, today=TODAY))["requests"][
            "status"
        ]
        == "ok"
    )


def test_reminders_come_from_your_history_most_frequent_first():
    history = {"wrong rating": 5, "cause missing": 2, "other": 9, "miscounted": 0}
    reminders = presubmit(data(), 3, 1, 0, history, TODAY)["reminders"]
    assert [r["tag"] for r in reminders] == [
        "wrong rating",
        "cause missing",
    ]  # 'other' has no reminder, 0 is skipped
    assert "scale" in reminders[0]["reminder"]
    assert presubmit(data(), 3, 1, 0, {}, TODAY)["reminders"] == []
