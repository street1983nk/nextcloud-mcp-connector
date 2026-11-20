"""A user id of "." or ".." never becomes a path segment (T-35-PF-02, phase 35).

``quote(uid, safe="")`` leaves dots alone, and httpx resolves the dot segments of a URL
before it sends it. Measured on 2026-11-20 (raw/35-06-sicherheit.txt, ``UIDPUNKT``):
``user_uid=".."`` sent ``GET .../apps/profile_fields/api/v1/values`` and ``user_uid="."``
sent ``GET .../api/v1/users/values``. Nextcloud itself refuses exactly these two ids
(``lib/private/User/Manager.php``: "Login must not consist of dots only"), and allows dots
anywhere else, so ``jane.doe``, ``a..b`` and ``...`` stay valid ids and must still be read.

The requests are recorded with an ``httpx.MockTransport``, which sees the URL after httpx
resolved it, so the test watches what would really go over the wire.
"""

import contextlib
from typing import Any

import httpx
import pytest

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import profile_fields

API = "/ocs/v2.php/apps/profile_fields/api/v1"
CATALOG = [{"id": 1, "field_key": "region", "type": "text", "active": True}]
DOT_ONLY = (".", "..", " .. ", "\t.\t")
DOTTED_BUT_VALID = ("jane.doe", "a..b", "...", ".x", "x.")


def _ocs(data: object) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


class Recorder:
    """A Nextcloud stand-in that answers the catalog and every values route."""

    def __init__(self) -> None:
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode().split("?", 1)[0]
        self.paths.append(path)
        if path == API + "/definitions":
            return httpx.Response(200, json=_ocs(CATALOG))
        return httpx.Response(200, json=_ocs([]))


def _clients(recorder: Recorder) -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(transport=httpx.MockTransport(recorder), follow_redirects=False),
        creds=Credentials("http://nc.test", "admin", "test-password"),
    )


async def _refusal(uid: str) -> ToolError:
    recorder = Recorder()
    with pytest.raises(ToolError) as caught:
        await profile_fields.browse(
            _clients(recorder), level="values", user_uid=uid, field_keys="region"
        )
    assert recorder.paths == [], f"{uid!r} sent {recorder.paths}"
    return caught.value


@pytest.mark.anyio
@pytest.mark.parametrize("uid", DOT_ONLY)
async def test_a_dot_only_uid_is_refused_before_any_request(uid: str) -> None:
    await _refusal(uid)


@pytest.mark.anyio
@pytest.mark.parametrize("uid", DOT_ONLY)
async def test_a_dot_only_uid_gets_the_existing_refusal(uid: str) -> None:
    """Same sentence, same hint and same reason as the refusal of a UID with a slash."""
    reference = await _refusal("../admin")
    refused = await _refusal(uid)
    assert refused.message == reference.message == "Invalid user UID."
    assert refused.hint == reference.hint
    assert getattr(refused, "reason", None) == getattr(reference, "reason", None)


@pytest.mark.anyio
@pytest.mark.parametrize("uid", DOT_ONLY)
async def test_no_request_leaves_the_users_segment(uid: str) -> None:
    recorder = Recorder()
    with contextlib.suppress(ToolError):
        await profile_fields.browse(
            _clients(recorder), level="values", user_uid=uid, field_keys="region"
        )
    assert API + "/values" not in recorder.paths
    assert API + "/users/values" not in recorder.paths
    assert all(path in (API + "/definitions",) for path in recorder.paths)


@pytest.mark.anyio
@pytest.mark.parametrize("uid", DOTTED_BUT_VALID)
async def test_a_uid_with_dots_is_still_read_positive_control(uid: str) -> None:
    recorder = Recorder()
    result = await profile_fields.browse(
        _clients(recorder), level="values", user_uid=uid, field_keys="region"
    )
    assert result == {"level": "values", "user_uid": uid, "fields": {}}
    assert recorder.paths == [API + "/definitions", f"{API}/users/{uid}/values"]


@pytest.mark.anyio
@pytest.mark.parametrize("level", ["me", "definitions"])
async def test_the_other_levels_never_put_the_uid_into_a_path(level: str) -> None:
    """Only ``values`` builds a path from ``user_uid``; ``search`` sends its value as a query."""
    recorder = Recorder()
    await profile_fields.browse(_clients(recorder), level=level, user_uid="..")
    assert recorder.paths == [API + ("/me/values" if level == "me" else "/definitions")]


@pytest.mark.anyio
async def test_a_dot_only_search_value_stays_in_the_query() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json=_ocs({"items": [], "pagination": {"total": 0}}))

    clients = NcClients(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        creds=Credentials("http://nc.test", "admin", "test-password"),
    )
    await profile_fields.browse(clients, level="search", field_key="region", value="..")
    assert [url.path for url in seen] == [API + "/users/search"]
    assert seen[0].params["value"] == ".."
