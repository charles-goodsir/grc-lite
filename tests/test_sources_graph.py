import io
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from grc_lite.collectors import graph
from grc_lite.collectors.errors import CollectError
from grc_lite.collectors.sources import (
    read_hr_leavers,
    read_registrations,
    read_users,
)

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "eyJ0eXAi.FAKE-TOKEN-FOR-TESTS.sig"


def test_fixtures_load():
    assert len(read_users(FIXTURES / "entra-users.json")) == 7
    assert len(read_registrations(FIXTURES / "mfa-registrations.json")) == 5
    leavers = read_hr_leavers(FIXTURES / "hr-leavers.csv")
    assert leavers[0] == {"upn": "amy.reed@acme.example", "leave_date": date(2026, 1, 15)}


def test_users_csv_and_bad_flag(tmp_path):
    good = tmp_path / "u.csv"
    good.write_text("userPrincipalName,accountEnabled\na@acme.example,Yes\nb@acme.example,false\n")
    assert [u["accountEnabled"] for u in read_users(good)] == [True, False]
    bad = tmp_path / "bad.csv"
    bad.write_text("userPrincipalName,accountEnabled\na@acme.example,maybe\n")
    with pytest.raises(CollectError, match="line 2: accountEnabled"):
        read_users(bad)


@pytest.mark.parametrize(
    ("name", "text", "message"),
    [
        ("l.csv", "upn,leave_date\na@acme.example,10/03/2026\n", "line 2: leave_date"),
        ("l.csv", "upn\na@acme.example\n", "missing column"),
        ("r.json", '{"value": "nope"}', "expected a Graph response"),
        ("r.json", "{not json", "cannot read as JSON"),
        (
            "r.json",
            '{"value": [{"userPrincipalName": "a@acme.example"}]}',
            "missing isMfaRegistered",
        ),
    ],
)
def test_bad_input_gives_clear_errors(tmp_path, name, text, message):
    path = tmp_path / name
    path.write_text(text)
    reader = read_hr_leavers if name.endswith(".csv") else read_registrations
    with pytest.raises(CollectError, match=message):
        reader(path)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(pages, seen):
    pages = iter(pages)

    def urlopen(request, timeout=None):
        seen.append(request)
        return FakeResponse(json.dumps(next(pages)).encode())

    return urlopen


def test_paging_follows_next_link_and_only_uses_get():
    seen = []
    next_link = graph.GRAPH + "v1.0/users?$skiptoken=abc"
    pages = [{"value": [{"n": 1}], "@odata.nextLink": next_link}, {"value": [{"n": 2}]}]
    items = graph.get_all("v1.0/users", TOKEN, urlopen=fake_urlopen(pages, seen))
    assert items == [{"n": 1}, {"n": 2}]
    assert [r.get_method() for r in seen] == ["GET", "GET"]
    assert seen[1].full_url == next_link


def test_paging_link_to_another_host_is_refused_and_token_not_sent():
    seen = []
    evil = {"value": [{"n": 1}], "@odata.nextLink": "https://evil.example/steal"}
    with pytest.raises(CollectError, match="outside graph.microsoft.com"):
        graph.get_all("v1.0/users", TOKEN, urlopen=fake_urlopen([evil], seen))
    assert [r.full_url for r in seen] == [graph.GRAPH + "v1.0/users"]  # evil.example never called


def test_http_error_message_has_code_but_never_the_token():
    def urlopen(request, timeout=None):
        body = io.BytesIO(json.dumps({"error": {"code": "Authorization_RequestDenied"}}).encode())
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, body)

    with pytest.raises(CollectError) as exc:
        graph.get_all("v1.0/users", TOKEN, urlopen=urlopen)
    assert str(exc.value) == "Graph returned HTTP 403 (Authorization_RequestDenied)"
    assert TOKEN not in str(exc.value) and TOKEN not in repr(exc.value)


def test_network_failure_hides_details():
    def urlopen(request, timeout=None):
        raise urllib.error.URLError(f"failed with {TOKEN}")

    with pytest.raises(CollectError) as exc:
        graph.get_all("v1.0/users", TOKEN, urlopen=urlopen)
    assert TOKEN not in str(exc.value)


def test_redirects_are_refused_so_the_token_cannot_follow_them():
    handler = graph._NoRedirect()
    request = urllib.request.Request(graph.GRAPH + "v1.0/users")
    assert (
        handler.redirect_request(request, None, 302, "Found", {}, "https://evil.example/") is None
    )


def test_az_token_failure_message_is_generic(monkeypatch):
    class Done:
        returncode = 1
        stdout = TOKEN
        stderr = f"error with {TOKEN}"

    monkeypatch.setattr(graph.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(CollectError) as exc:
        graph.az_token()
    assert TOKEN not in str(exc.value)
