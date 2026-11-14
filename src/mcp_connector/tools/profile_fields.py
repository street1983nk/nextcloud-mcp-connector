"""Profile Fields OCS access using the Nextcloud caller's permissions."""

import json
import re
from typing import Any
from urllib.parse import quote

from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import ocs

_PREFIX = "/apps/profile_fields/api/v1"
_KEY = re.compile(r"^[a-z0-9_]{1,100}$")


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
        result = ocs.parse_ocs(response, what="Profile Fields exact search")
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise ToolError(message="Invalid search result.", hint="Check Profile Fields API.")
        users = []
        for item in result["items"]:
            if not isinstance(item, dict):
                continue
            fields = item.get("fields")
            record = fields.get(key) if isinstance(fields, dict) else None
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
        data = ocs.parse_ocs(response, what="current user Profile Fields values")
        if not isinstance(data, list):
            raise ToolError(message="Invalid own values.", hint="Check Profile Fields API.")
        return {"level": level, "count": len(data), "results": data}

    if level not in ("definitions", "values"):
        raise ToolError(message="Unknown level.", hint="Use definitions, me, values or search.")
    if level == "values":
        uid = user_uid.strip()
        keys = [key.strip() for key in field_keys.split(",")]
        if not uid or len(uid) > 256 or any(char in uid for char in ("/", "\\", "\x00")):
            raise ToolError(message="Invalid user UID.", hint="Provide one exact Nextcloud UID.")
        if not 1 <= len(keys) <= 12 or any(not _KEY.fullmatch(key) for key in keys):
            raise ToolError(message="Invalid field keys.", hint="Provide up to 12 exact keys.")
        if len(keys) != len(set(keys)):
            raise ToolError(message="Duplicate field keys.", hint="List each key once.")

    response = await ocs.ocs_get(clients.client, clients.creds, _PREFIX + "/definitions")
    data = ocs.parse_ocs(response, what="Profile Fields admin catalog")
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
    values = ocs.parse_ocs(response, what="Profile Fields selected user values")
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


async def _put(clients: NcClients, path: str, body: dict[str, Any]) -> Any:
    """A single native OCS PUT; never retry an ambiguous result automatically."""
    response = await clients.client.put(
        ocs.ocs_url(clients.creds, path),
        json=body,
        headers={**ocs.OCS_HEADERS, "Content-Type": "application/json"},
        auth=clients.creds.auth(),
    )
    return ocs.parse_ocs(response, what="Profile Fields update")


async def set_value(
    clients: NcClients,
    field_id: int,
    value_json: str,
    *,
    user_uid: str = "",
    visibility: str = "",
) -> dict[str, Any]:
    """Upsert own or admin-selected value, relying on Profile Fields permission checks."""
    if field_id <= 0:
        raise ToolError(message="Invalid field id.", hint="Use a positive definition id.")
    try:
        content = json.loads(value_json)
    except json.JSONDecodeError:
        raise ToolError(message="Invalid JSON value.", hint="Use a JSON scalar or list.") from None
    if isinstance(content, dict):
        raise ToolError(message="JSON object not supported.", hint="Use a scalar or list value.")
    uid = user_uid.strip()
    if len(uid) > 256 or any(char in uid for char in ("/", "\\", "\x00")):
        raise ToolError(message="Invalid user UID.", hint="Use exact UID without path separators.")
    if visibility and visibility not in ("private", "users", "public"):
        raise ToolError(message="Invalid visibility.", hint="Use private, users or public.")
    path = (
        f"{_PREFIX}/users/{quote(uid, safe='')}/values/{field_id}"
        if uid
        else f"{_PREFIX}/me/values/{field_id}"
    )
    url = f"{_PREFIX}/users/{quote(uid, safe='')}/values" if uid else f"{_PREFIX}/me/values"
    response = await ocs.ocs_get(clients.client, clients.creds, url)
    existing = ocs.parse_ocs(response, what="existing Profile Fields values")
    if not isinstance(existing, list):
        raise ToolError(message="Invalid existing values.", hint="Check Profile Fields API.")
    for row in existing:
        if not isinstance(row, dict):
            continue
        record = row.get("value") if not uid else row
        if not isinstance(record, dict):
            continue
        if record.get("field_definition_id") == field_id:
            prior = record.get("value")
            if (
                isinstance(prior, dict)
                and prior.get("value") == content
                and (not visibility or record.get("current_visibility") == visibility)
            ):
                return {
                    "field_id": field_id,
                    "scope": "admin" if uid else "me",
                    "changed": False,
                    "value": record,
                }
    body: dict[str, Any] = {"value": {"value": content}}
    if visibility:
        body["currentVisibility"] = visibility
    data = await _put(clients, path, body)
    if not isinstance(data, dict):
        raise ToolError(message="Invalid write result.", hint="Verify result through browse.")
    return {"field_id": field_id, "scope": "admin" if uid else "me", "value": data}


async def save_definition(
    clients: NcClients,
    definition_json: str,
    *,
    definition_id: int = 0,
) -> dict[str, Any]:
    """Admin-only create/update, explicitly disallowing destructive deletion."""
    if definition_id < 0:
        raise ToolError(message="Invalid definition id.", hint="Use 0 for create.")
    try:
        fields = json.loads(definition_json)
    except json.JSONDecodeError:
        raise ToolError(
            message="Invalid definition JSON.", hint="Provide one JSON object."
        ) from None
    if not isinstance(fields, dict):
        raise ToolError(message="Invalid definition.", hint="Provide one JSON object.")
    allowed = {
        "fieldKey",
        "label",
        "type",
        "editPolicy",
        "exposurePolicy",
        "sortOrder",
        "active",
        "options",
    }
    if set(fields) - allowed:
        raise ToolError(
            message="Unknown definition properties.", hint="Use the OCS definition keys."
        )
    required = {"label", "type"}
    if not definition_id:
        required.add("fieldKey")
    if not required <= fields.keys():
        raise ToolError(message="Incomplete definition.", hint="Provide key, label and type.")
    # The PHP endpoint applies defaults on omitted update parameters: require an
    # explicit complete update to avoid silently resetting admin policies.
    if (
        definition_id
        and not {"editPolicy", "exposurePolicy", "sortOrder", "active"} <= fields.keys()
    ):
        raise ToolError(
            message="Partial definition update refused.",
            hint="Read the existing definition and provide all policy attributes.",
        )
    if definition_id:
        response = await ocs.ocs_get(clients.client, clients.creds, _PREFIX + "/definitions")
        definitions = ocs.parse_ocs(response, what="existing Profile Fields definitions")
        if not isinstance(definitions, list):
            raise ToolError(message="Invalid catalog.", hint="Check Profile Fields API.")
        for entry in definitions:
            if not isinstance(entry, dict) or entry.get("id") != definition_id:
                continue
            converted = {
                "fieldKey": "field_key",
                "label": "label",
                "type": "type",
                "editPolicy": "edit_policy",
                "exposurePolicy": "exposure_policy",
                "sortOrder": "sort_order",
                "active": "active",
                "options": "options",
            }
            if all(entry.get(converted[key]) == val for key, val in fields.items()):
                return {"operation": "update", "changed": False, "definition": entry}
            break
        data = await _put(clients, f"{_PREFIX}/definitions/{definition_id}", fields)
    else:
        response = await ocs.ocs_post(
            clients.client, clients.creds, _PREFIX + "/definitions", fields
        )
        data = ocs.parse_ocs(response, what="Profile Fields definition creation")
    if not isinstance(data, dict):
        raise ToolError(message="Invalid definition result.", hint="Read definitions to verify.")
    return {"operation": "update" if definition_id else "create", "definition": data}
