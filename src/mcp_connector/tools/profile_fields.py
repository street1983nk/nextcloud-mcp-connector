"""Profile Fields OCS access using the Nextcloud caller's permissions."""

import re
from typing import Any
from urllib.parse import quote

import httpx

from ..errors import AppMissingError, ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import ocs

_PREFIX = "/apps/profile_fields/api/v1"
_KEY = re.compile(r"^[a-z0-9_]{1,100}$")

#: The OCS status Nextcloud core writes for a route that no enabled app registered.
_ROUTE_UNKNOWN = 998
#: The fixed, untranslated text of the core ``AppNotEnabledException`` (HTTP 412).
_NOT_ENABLED_FOR_ACCOUNT = "App is not enabled"


def _parse(response: httpx.Response, what: str) -> Any:
    """``ocs.parse_ocs`` with two cases of its own: the app Profile Fields is not there.

    Measured on 2026-11-20 (raw/35-12-pf-fehlt.txt): with the app missing (Nextcloud 35.0.0)
    or disabled (Nextcloud 34.0.3) every route of this module answers HTTP 404 with
    ``ocs.meta.statuscode`` 998, the core answer for a route nobody registered. The app's
    own failures never carry 998: Profile Fields 4.0.0 answers them through
    ``DataResponse`` with 400, 401, 403, 404 or 409 as the status, and an unknown UID is an
    empty 200. Only both halves together mean "missing app".

    With the app enabled for some groups only, an account outside all of them gets HTTP 412
    and the bare JSON ``{"message": "App is not enabled"}`` from the core security
    middleware, without an OCS envelope. The other 412 answers of that middleware carry other
    texts, so status, missing envelope and the exact text are required together.

    Everything else keeps the shared wording of ``_status_error``, which stays the same for
    every other app.
    """
    if response.status_code in (404, 412):
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if (
            response.status_code == 412
            and isinstance(payload, dict)
            and "ocs" not in payload
            and payload.get("message") == _NOT_ENABLED_FOR_ACCOUNT
        ):
            raise AppMissingError(
                message="Profile Fields is not enabled for this account.",
                hint=(
                    "Ask an administrator to enable the app Profile Fields for one of your "
                    "groups or to switch off profile_fields_read."
                ),
            )
        envelope = payload.get("ocs") if isinstance(payload, dict) else None
        meta = envelope.get("meta") if isinstance(envelope, dict) else None
        if (
            response.status_code == 404
            and isinstance(meta, dict)
            and meta.get("statuscode") == _ROUTE_UNKNOWN
        ):
            raise AppMissingError(
                message="Profile Fields is not installed or not enabled on this Nextcloud.",
                hint=(
                    "Ask an administrator to install the app Profile Fields or to switch off "
                    "profile_fields_read."
                ),
            )
    return ocs.parse_ocs(response, what=what)


async def browse(
    clients: NcClients,
    level: str = "me",
    user_uid: str = "",
    field_keys: str = "",
    field_key: str = "",
    value: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return the admin catalog, selected fields of one UID, or an exact search."""
    if level == "search":
        key = field_key.strip()
        match = value.strip()
        if not _KEY.fullmatch(key) or not match or len(match) > 256:
            raise ToolError(
                message="Invalid search filter.", hint="Provide field key and exact value."
            )
        if not 1 <= limit <= 100 or offset < 0:
            raise ToolError(message="Invalid pagination.", hint="Use limit 1..100 and offset >= 0.")
        response = await ocs.ocs_get(
            clients.client,
            clients.creds,
            _PREFIX + "/users/search",
            params={
                "fieldKey": key,
                "operator": "eq",
                "value": match,
                "limit": limit,
                "offset": offset,
            },
        )
        result = _parse(response, what="the Profile Fields exact search")
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise ToolError(message="Invalid search result.", hint="Check Profile Fields API.")
        users = []
        for item in result["items"]:
            if not isinstance(item, dict):
                continue
            matched_fields = item.get("fields")
            record = matched_fields.get(key) if isinstance(matched_fields, dict) else None
            current = record.get("value") if isinstance(record, dict) else None
            users.append(
                {
                    "user_uid": item.get("user_uid"),
                    "value": (
                        current.get("value", {}).get("value")
                        if isinstance(current, dict) and isinstance(current.get("value"), dict)
                        else None
                    ),
                }
            )
        paging = result.get("pagination")
        return {
            "level": level,
            "field_key": key,
            "results": users,
            "count": len(users),
            "offset": offset,
            "total": paging.get("total") if isinstance(paging, dict) else len(users),
        }

    if level == "me":
        response = await ocs.ocs_get(clients.client, clients.creds, _PREFIX + "/me/values")
        data = _parse(response, what="the current user's Profile Fields values")
        if not isinstance(data, list):
            raise ToolError(message="Invalid own values.", hint="Check Profile Fields API.")
        return {"level": level, "count": len(data), "results": data}

    if level not in ("definitions", "values"):
        raise ToolError(message="Unknown level.", hint="Use definitions, me, values or search.")
    uid = ""
    keys: list[str] = []
    if level == "values":
        uid = user_uid.strip()
        keys = [key.strip() for key in field_keys.split(",")]
        # "." and ".." pass quote() unchanged and httpx resolves them, so the request would
        # leave users/{uid}; Nextcloud refuses exactly these two ids as well (T-35-PF-02).
        if (
            not uid
            or uid in (".", "..")
            or len(uid) > 256
            or any(char in uid for char in ("/", "\\", "\x00"))
        ):
            raise ToolError(message="Invalid user UID.", hint="Provide one exact Nextcloud UID.")
        if not 1 <= len(keys) <= 12 or any(not _KEY.fullmatch(key) for key in keys):
            raise ToolError(message="Invalid field keys.", hint="Provide up to 12 exact keys.")
        if len(keys) != len(set(keys)):
            raise ToolError(message="Duplicate field keys.", hint="List each key once.")

    response = await ocs.ocs_get(clients.client, clients.creds, _PREFIX + "/definitions")
    data = _parse(response, what="the Profile Fields admin catalog")
    if not isinstance(data, list):
        raise ToolError(message="Invalid field catalog.", hint="Check Profile Fields API.")
    definitions = [entry for entry in data if isinstance(entry, dict)]
    if level == "definitions":
        return {
            "level": level,
            "count": len(definitions),
            "results": [
                {
                    key: entry[key]
                    for key in (
                        "id",
                        "field_key",
                        "type",
                        "edit_policy",
                        "exposure_policy",
                        "active",
                    )
                    if key in entry
                }
                for entry in definitions
            ],
        }
    by_key = {
        entry["field_key"]: entry["id"]
        for entry in definitions
        if isinstance(entry.get("field_key"), str) and isinstance(entry.get("id"), int)
    }
    if not set(keys) <= by_key.keys():
        raise ToolError(message="Unknown field key.", hint="List definitions first.")
    selected = {by_key[key]: key for key in keys}
    response = await ocs.ocs_get(
        clients.client, clients.creds, f"{_PREFIX}/users/{quote(uid, safe='')}/values"
    )
    values = _parse(response, what="the selected user's Profile Fields values")
    if not isinstance(values, list):
        raise ToolError(message="Invalid user values.", hint="Check Profile Fields API.")
    fields: dict[str, Any] = {}
    for entry in values:
        if not isinstance(entry, dict) or entry.get("field_definition_id") not in selected:
            continue
        current = entry.get("value")
        fields[selected[entry["field_definition_id"]]] = {
            "value": current.get("value") if isinstance(current, dict) else None,
            "current_visibility": entry.get("current_visibility"),
        }
    return {"level": level, "user_uid": uid, "fields": fields}
