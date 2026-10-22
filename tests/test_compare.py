from datetime import date

import pytest

from grc_lite.collectors.compare import check_leavers, check_mfa

AS_OF = date(2026, 3, 10)


def user(upn, enabled=True):
    return {"userPrincipalName": upn, "accountEnabled": enabled}


def leaver(upn, leave_date):
    return {"upn": upn, "leave_date": leave_date}


def test_leaver_still_enabled_past_the_limit_is_a_gap():
    result = check_leavers(
        [user("a@acme.example")], [leaver("a@acme.example", date(2026, 1, 15))], AS_OF
    )
    assert result.verdict == "gap"
    assert result.offenders == ["a@acme.example"]
    assert result.summary.startswith("1 of 1 leavers")


def test_disabled_or_missing_leavers_meet_the_rule():
    users = [user("b@acme.example", enabled=False)]
    leavers = [
        leaver("b@acme.example", date(2026, 2, 1)),
        leaver("gone@acme.example", date(2026, 2, 1)),
    ]
    assert check_leavers(users, leavers, AS_OF).verdict == "meets"


@pytest.mark.parametrize(
    ("leave_date", "verdict"), [(date(2026, 3, 9), "meets"), (date(2026, 3, 8), "gap")]
)
def test_boundary_is_strictly_more_than_max_days(leave_date, verdict):
    result = check_leavers([user("a@acme.example")], [leaver("a@acme.example", leave_date)], AS_OF)
    assert result.verdict == verdict


def test_upn_match_ignores_case_and_spaces():
    result = check_leavers(
        [user("A@Acme.Example")], [leaver(" a@acme.example ", date(2026, 1, 1))], AS_OF
    )
    assert result.verdict == "gap"


REGS = [
    {"userPrincipalName": "admin1@acme.example", "isAdmin": True, "isMfaRegistered": True},
    {"userPrincipalName": "admin2@acme.example", "isAdmin": True, "isMfaRegistered": False},
    {"userPrincipalName": "old@acme.example", "isAdmin": True, "isMfaRegistered": False},
    {"userPrincipalName": "user2@acme.example", "isAdmin": False, "isMfaRegistered": False},
]
USERS = [user("old@acme.example", enabled=False)]


def test_mfa_admin_scope_excludes_disabled_accounts():
    result = check_mfa(REGS, USERS, "admins")
    assert result.offenders == ["admin2@acme.example"]
    assert result.summary == "1 of 2 administrator accounts have no MFA registered."


def test_mfa_all_scope_includes_ordinary_users():
    assert check_mfa(REGS, USERS, "all").offenders == ["admin2@acme.example", "user2@acme.example"]


def test_mfa_without_user_list_counts_disabled_accounts():
    assert "old@acme.example" in check_mfa(REGS, None, "admins").offenders


def test_mfa_all_registered_meets():
    assert check_mfa(REGS[:1], USERS).verdict == "meets"


def test_mfa_rejects_unknown_scope():
    with pytest.raises(ValueError):
        check_mfa(REGS, USERS, "everyone")
