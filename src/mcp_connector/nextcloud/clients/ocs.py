"""OCS requests and the two response formats Nextcloud actually uses.

Two headers go out with every OCS request, always (D-18): ``OCS-APIRequest: true`` marks
the call as an API call, and ``Accept: application/json`` asks for JSON instead of XML.
Without the first one Nextcloud answers a browser login page with status 200, which is the
single most confusing failure in this whole API family, so :func:`_json_payload` names it
explicitly instead of dying in ``response.json()``.

Two parsers, not one, and that is the point of this module (pitfall 9):

``parse_ocs``
    for everything under ``/ocs/v2.php``: the payload sits in ``ocs.data`` and the real
    status in ``ocs.meta.statuscode``.
``parse_app_json``
    for Notes, Deck and the generation 1 row route of Tables, which are ordinary app routes
    and answer with the bare object, or with ``{"status": 4xx, "message": "..."}`` on
    failure. Letting an ``ocs.meta`` parser loose on that produces a ``KeyError`` where an
    actionable message belongs.

Status handling is the same everywhere in this project: never repeat a failed
authentication (Nextcloud counts failures per source IP and then throttles every user of
this server), never follow a redirect, and turn a 5xx into a degraded answer rather than a
stack trace.
"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from ... import config
from ...errors import REASON_PERMISSION_DENIED, REASON_UNKNOWN_ID, ToolError
from ..credentials import Credentials

#: OCS v2 lives under this prefix; v1 is not used anywhere in this project.
OCS_PREFIX = "/ocs/v2.php"

#: The two mandatory headers of D-18. Copied per request, never mutated in place.
OCS_HEADERS: Mapping[str, str] = {
    "OCS-APIRequest": "true",
    "Accept": "application/json",
}

#: Unified search: the provider list, and one search route per provider below it.
SEARCH_PROVIDERS_PATH = "/search/providers"

#: ``100`` is the OCS v1 success code, ``200`` the v2 one. Instances answer with either.
#: ``201`` belongs here too, and not because a POST usually answers with it: in OCS v2 the
#: raw HTTP status is written into ``ocs.meta.statuscode`` (``V2Response::render``), and
#: ``POST /apps/spreed/api/v1/chat/{token}`` documents 201 as its only success. Without it a
#: sent Talk message would reach the model as "an unexpected status", and the model would
#: very likely send it a second time. No route in use today answers 201, so widening the set
#: cannot turn an existing check around, and the alternative would be a second envelope
#: evaluation inside the Talk client, which is the duplication this project avoids.
_OK_STATUS = frozenset({100, 200, 201})

_HTML_HINT = (
    "That is the Nextcloud login page. Check the app password and that the configured URL "
    "points at the Nextcloud root, not at a portal or a proxy error page."
)


def ocs_url(creds: Credentials, path: str) -> str:
    """Build ``<base>/ocs/v2.php<path>``; ``path`` always starts with a slash."""
    if not path.startswith("/"):
        raise ValueError(f"an OCS path must start with a slash (got {path!r})")
    return f"{creds.base_url}{OCS_PREFIX}{path}"


async def ocs_get(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    params: Mapping[str, Any] | None = None,
) -> httpx.Response:
    """GET an OCS endpoint with both mandatory headers and per request authentication.

    Authentication is passed per request and not on the client, because the passthrough
    and the ExApp mode both change credentials from call to call. Which scheme it is, is
    the credential object's decision and not this module's (see ``Credentials.auth``).
    Redirects are not followed: the client is built that way, and a redirecting base URL
    is a configuration error.
    """
    return await client.get(
        ocs_url(creds, path),
        params=dict(params) if params else None,
        headers=dict(OCS_HEADERS),
        auth=creds.auth(),
    )


async def ocs_post(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    json_body: Mapping[str, Any],
) -> httpx.Response:
    """POST to an OCS endpoint. This is the first write this project makes over OCS (K9).

    Same rules as :func:`ocs_get`, plus one header and one prohibition. Authentication is
    passed per request, and redirects are never followed: the client is built that way, and
    a redirecting base URL is a configuration error, not something to chase.

    No ``Origin`` header, ever. With one present Nextcloud's CORS middleware demands a basic
    reauthentication, and under AppAPI impersonation there is no password to reauthenticate
    with, so the request would fail for a reason that has nothing to do with the payload.
    """
    return await client.post(
        ocs_url(creds, path),
        json=dict(json_body),
        headers={**OCS_HEADERS, "Content-Type": "application/json"},
        auth=creds.auth(),
    )


async def list_search_providers(
    client: httpx.AsyncClient, creds: Credentials
) -> list[dict[str, Any]]:
    """Return the search providers this instance offers right now.

    Read on every call and never cached: the list follows the installed apps, and an app
    enabled a minute ago has to show up without restarting this server. A provider that an
    administrator removed can still linger here until the next Nextcloud restart, which is
    exactly why the caller treats a failing provider as a degradation, not as a bug.
    """
    response = await ocs_get(client, creds, SEARCH_PROVIDERS_PATH)
    data = parse_ocs(response, what="the list of search providers")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


async def provider_search(
    client: httpx.AsyncClient,
    creds: Credentials,
    provider_id: str,
    term: str,
    limit: int,
    cursor: str | int | None = None,
) -> dict[str, Any]:
    """Ask one search provider and return its ``{name, isPaginated, entries, cursor}``.

    ``limit`` is a wish: Nextcloud caps it at ``unified-search.max-results-per-request``.
    The provider id is quoted because it comes off the wire, not out of our own code.
    """
    params: dict[str, Any] = {"term": term, "limit": limit}
    if cursor is not None and str(cursor) != "":
        params["cursor"] = cursor

    path = f"{SEARCH_PROVIDERS_PATH}/{quote(provider_id, safe='')}/search"
    response = await ocs_get(client, creds, path, params=params)
    data = parse_ocs(response, what=f"the search results of the provider {provider_id}")
    return data if isinstance(data, dict) else {}


def parse_ocs(response: httpx.Response, what: str) -> Any:
    """Return ``ocs.data`` of an OCS envelope, or raise with message plus hint."""
    _check_transport(response, what)
    payload = _json_payload(response, what)

    envelope = payload.get("ocs") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict):
        raise ToolError(
            message=f"Nextcloud answered {what} without an OCS envelope.",
            hint=(
                "Check that the configured URL points at a Nextcloud; an OCS answer always "
                "carries an ocs.meta section."
            ),
        )

    meta = envelope.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    raw_status = meta.get("statuscode")
    status = raw_status if isinstance(raw_status, int) else response.status_code
    if status not in _OK_STATUS:
        raise _status_error(status, str(meta.get("message") or ""), what)
    return envelope.get("data")


def parse_app_json(response: httpx.Response, what: str) -> Any:
    """Return the payload of a Notes or Deck answer, or raise with message plus hint.

    Both apps report failures as ``{"status": 4xx, "message": "..."}`` with the matching
    HTTP status, so the body is inspected as well as the status line: an instance behind a
    proxy that rewrites the status still gets read correctly.
    """
    _check_transport(response, what)
    payload = _json_payload(response, what)

    if isinstance(payload, dict):
        embedded = payload.get("status")
        if isinstance(embedded, int) and embedded >= 400:
            raise _status_error(embedded, str(payload.get("message") or ""), what)

    if response.status_code >= 400:
        detail = payload.get("message") if isinstance(payload, dict) else None
        raise _status_error(response.status_code, str(detail or ""), what)
    return payload


def _check_transport(response: httpx.Response, what: str) -> None:
    """Handle the statuses whose body never carries a better explanation."""
    status = response.status_code
    if 300 <= status < 400:
        raise ToolError(
            message=f"Nextcloud answered the request for {what} with a redirect ({status}).",
            hint=config.REDIRECT_HINT,
        )
    if status == 401:
        raise ToolError(
            message="Nextcloud rejected the app password.",
            hint=(
                "Generate a new app password in Nextcloud under Settings, Security, "
                "Devices and sessions, then restart the MCP server."
            ),
        )
    if status == 429:
        raise ToolError(
            message="Nextcloud is rate limiting this server.",
            hint="Wait about a minute before the next call; do not repeat it immediately.",
        )
    if status >= 500 and status != 507:
        # 507 is not a server fault but a full account, and its body carries the app's own
        # wording, so it belongs to the status mapping below and not into this branch.
        raise ToolError(
            message=f"Nextcloud reported a server error ({status}) while reading {what}.",
            hint="This is a problem on the Nextcloud side. Retry later or check its log.",
        )
    if status >= 400 and not _looks_like_json(response):
        # A 4xx whose body is not JSON is explained by its status and by nothing else.
        # Measured against Tables 2.2.2: an unknown table id answers 404 with an empty body
        # and ``Content-Type: text/html``, and the HTML branch of :func:`_json_payload`
        # would call that the login page and send the model to check its app password. That
        # is the wrong next step for the most common mistake of all, a guessed id.
        raise _status_error(status, "", what)


def _looks_like_json(response: httpx.Response) -> bool:
    """Whether this body can still carry the app's own wording of the failure."""
    if "json" in response.headers.get("content-type", "").lower():
        return True
    body = response.text.lstrip()
    return body.startswith(("{", "["))


def _json_payload(response: httpx.Response, what: str) -> Any:
    """Decode the body as JSON, naming an HTML login page for what it is."""
    content_type = response.headers.get("content-type", "").lower()
    body = response.text.lstrip()
    if "html" in content_type or body.startswith("<"):
        raise ToolError(
            message=f"Nextcloud answered {what} with an HTML page instead of JSON.",
            hint=_HTML_HINT,
        )
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError:
        raise ToolError(
            message=f"Nextcloud answered {what} with a body that is not JSON.",
            hint="Check the Nextcloud log for that request; the answer was not an API answer.",
        ) from None


def _status_error(status: int, detail: str, what: str) -> ToolError:
    """One place that turns a Nextcloud status into a sentence the model can act on.

    The reason identifiers sit here and not at the roughly 223 other raise sites of this
    package: this phase puts an audit module next to the error handling, it does not tidy the
    error handling up (D-17). Everything without a reason reads as "unspecified", which is
    honest. Only ``reason`` may ever reach a log; ``message`` and ``hint`` name paths, ids and
    calendar names and stay in the tool answer (T-18-01).
    """
    suffix = f' Nextcloud says: "{detail}".' if detail else ""
    if status == 400:
        return ToolError(
            message=f"Nextcloud rejected the request for {what} as invalid.{suffix}",
            hint="Correct the arguments and call the tool again.",
        )
    if status == 401:
        return ToolError(
            message="Nextcloud rejected the app password.",
            hint=(
                "Generate a new app password in Nextcloud under Settings, Security, "
                "Devices and sessions, then restart the MCP server."
            ),
        )
    if status == 403:
        return ToolError(
            message=f"No permission for {what}.{suffix}",
            hint=(
                "Ask the owner of the item or an administrator in Nextcloud for the missing "
                "permission."
            ),
            reason=REASON_PERMISSION_DENIED,
        )
    if status in (404, 998):
        return ToolError(
            message=f"Nextcloud did not find {what}.{suffix}",
            hint="Search for it first; the id or the name is unknown to this instance.",
            reason=REASON_UNKNOWN_ID,
        )
    if status == 429:
        return ToolError(
            message="Nextcloud is rate limiting this server.",
            hint="Wait about a minute before the next call; do not repeat it immediately.",
        )
    if status == 507:
        return ToolError(
            message=f"Nextcloud has no storage space left for {what}.{suffix}",
            hint="Free up quota in Nextcloud, then try again.",
        )
    if status >= 500:
        return ToolError(
            message=f"Nextcloud reported a server error ({status}) for {what}.{suffix}",
            hint="This is a problem on the Nextcloud side. Retry later or check its log.",
        )
    return ToolError(
        message=f"Nextcloud answered {what} with an unexpected status {status}.{suffix}",
        hint="Retry once; if it persists, check the Nextcloud log for that request.",
    )
