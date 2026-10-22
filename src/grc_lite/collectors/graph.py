"""Read-only Microsoft Graph client built on the standard library.

Safety rules: GET only; the token goes only to graph.microsoft.com (a paging link pointing
anywhere else is refused, and so is any redirect); the token and request headers never appear in an error message.
"""

import json
import subprocess
import urllib.error
import urllib.request

from grc_lite.collectors.errors import CollectError

GRAPH = "https://graph.microsoft.com/"
USERS = "v1.0/users?$select=userPrincipalName,accountEnabled&$top=999"
REGISTRATIONS = "v1.0/reports/authenticationMethods/userRegistrationDetails?$top=999"
MAX_PAGES = 100


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib keeps the Authorization header across redirects; refuse them instead."""

    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def az_token() -> str:
    """Ask the signed-in Azure CLI for a Graph token. Nothing is stored or printed."""
    try:
        done = subprocess.run(
            ["az", "account", "get-access-token", "--resource", GRAPH, "--query", "accessToken",
             "-o", "tsv"],
            capture_output=True, text=True, check=False, timeout=60,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        raise CollectError("could not run the Azure CLI; install it and run `az login`") from None
    token = done.stdout.strip()
    if done.returncode != 0 or not token:
        raise CollectError("could not get a Graph token from the Azure CLI; run `az login`")
    return token


def get_all(path: str, token: str, urlopen=_opener.open) -> list[dict]:
    """GET a Graph collection, following paging links, and return every item."""
    url = GRAPH + path
    items: list[dict] = []
    for _ in range(MAX_PAGES):
        request = urllib.request.Request(
            url, method="GET", headers={"Authorization": f"Bearer {token}"}
        )
        try:
            with urlopen(request, timeout=30) as response:
                page = json.load(response)
        except urllib.error.HTTPError as e:
            raise CollectError(f"Graph returned HTTP {e.code}{_graph_code(e)}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise CollectError(f"Graph request failed ({type(e).__name__})") from None
        items += page.get("value", [])
        url = page.get("@odata.nextLink")
        if not url:
            return items
        if not url.startswith(GRAPH):
            raise CollectError("Graph paging link points outside graph.microsoft.com; refused")
    raise CollectError(f"more than {MAX_PAGES} pages; stopping")


def _graph_code(error: urllib.error.HTTPError) -> str:
    """The short error code from a Graph error body, if there is one."""
    try:
        return f" ({json.load(error)['error']['code']})"
    except (ValueError, KeyError, TypeError):
        return ""


def fetch_users(token: str, **kw) -> list[dict]:
    return get_all(USERS, token, **kw)


def fetch_registrations(token: str, **kw) -> list[dict]:
    return get_all(REGISTRATIONS, token, **kw)
