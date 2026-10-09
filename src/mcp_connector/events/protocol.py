"""Bounded wire contract. No message text is part of an outgoing event."""

import base64
import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit

NAME = "nextcloud.talk.message.created"
MAX_BODY = 65536
CALLBACK_HOSTS = frozenset({"chatgpt.com", "api.openai.com", "connectors.api.openai.com"})
DEFINITION = {
    "name": NAME,
    "description": (
        "New local-user message in one authorized Talk conversation; own messages excluded."
    ),
    "delivery": ["webhook"],
    "inputSchema": {
        "type": "object",
        "properties": {"conversation": {"type": "string", "pattern": "^[a-z0-9]{4,30}$"}},
        "required": ["conversation"],
        "additionalProperties": False,
    },
    "payloadSchema": {
        "type": "object",
        "properties": {
            "conversation": {"type": "string"},
            "message_id": {"type": "string"},
        },
        "required": ["conversation", "message_id"],
        "additionalProperties": False,
    },
}


class Refused(Exception):
    """Fixed, non-sensitive protocol errors."""


def callback(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise Refused("Invalid callback")
    try:
        u = urlsplit(value)
        valid = u.scheme == "https" and u.hostname in CALLBACK_HOSTS and u.port is None
    except ValueError:
        raise Refused("Callback not permitted") from None
    if not valid or u.username or u.password or u.fragment:
        raise Refused("Callback not permitted")
    return value


def signing_key(value: object) -> bytes:
    if not isinstance(value, str) or not value.startswith("whsec_"):
        raise Refused("Invalid signing key")
    try:
        key = base64.b64decode(value[6:], validate=True)
    except ValueError:
        raise Refused("Invalid signing key") from None
    if not 24 <= len(key) <= 64:
        raise Refused("Invalid signing key")
    return key


def room_argument(arguments: object) -> str:
    if not isinstance(arguments, dict) or set(arguments) != {"conversation"}:
        raise Refused("One conversation is required")
    room = arguments["conversation"]
    if not isinstance(room, str) or not re.fullmatch(r"[a-z0-9]{4,30}", room):
        raise Refused("Invalid conversation")
    return room


def stable_id(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def headers(
    secret: str, sub: str, event: str, body: bytes, now: int, old: str = ""
) -> dict[str, str]:
    signed = f"{event}.{now}.".encode() + body
    values = [
        "v1," + base64.b64encode(hmac.digest(signing_key(s), signed, "sha256")).decode()
        for s in (secret, old)
        if s
    ]
    return {
        "content-type": "application/json",
        "webhook-id": event,
        "webhook-timestamp": str(now),
        "webhook-signature": " ".join(values),
        "X-MCP-Subscription-Id": sub,
    }


def talk_message(
    secret: str, random: str, signature: str, body: bytes
) -> tuple[str, str, str] | None:
    if len(body) > MAX_BODY or not re.fullmatch(r"[A-Za-z0-9+/]{32,128}", random):
        raise Refused("Invalid webhook")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", signature):
        raise Refused("Invalid webhook")
    expected = hmac.new(secret.encode(), random.encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise Refused("Invalid webhook")
    try:
        d = json.loads(body)
        actor, target, obj = d["actor"], d["target"], d["object"]
        if (
            d["type"] != "Create"
            or actor["type"] != "Person"
            or obj["type"] != "Note"
            or obj["name"] != "message"
        ):
            return None
        # Local authenticated users only; no guest, bot, system or private-message inference.
        actor_id = actor["id"]
        if (
            not isinstance(actor_id, str)
            or not actor_id.startswith("users/")
            or len(actor_id) > 512
        ):
            return None
        room = room_argument({"conversation": target["id"]})
        mid = str(obj["id"])
        if not re.fullmatch(r"[0-9]{1,19}", mid):
            return None
        content = json.loads(obj["content"])
        if content.get("messageType", "comment") != "comment":
            return None
        return room, mid, actor_id[6:]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Refused("Invalid webhook body") from None
