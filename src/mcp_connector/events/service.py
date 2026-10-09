"""Opt-in single-process event delivery with authorization checked at send time."""

import asyncio
import json
import secrets
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx

from ..oauth.cimd import resolve_addresses
from .protocol import NAME, Refused, callback, headers, room_argument, signing_key, stable_id
from .store import EventStore


class EventService:
    def __init__(
        self,
        store: EventStore,
        client: httpx.AsyncClient,
        authorize: Callable[[str, str], Awaitable[str | None]],
        rooms: frozenset[str],
        clock: Callable[[], float] = time.time,
        max_ttl_ms: int = 3600000,
        resolve: Callable[[str, int], Awaitable[list[str] | None]] = resolve_addresses,
    ):
        self.store, self.client, self.authorize, self.rooms, self.clock = (
            store,
            client,
            authorize,
            rooms,
            clock,
        )
        self.lock = asyncio.Lock()
        if type(max_ttl_ms) is not int or not 60000 <= max_ttl_ms <= 3600000:
            raise ValueError("Event lifetime must be between one minute and one hour")
        self.max_ttl_ms = max_ttl_ms
        self.resolve = resolve

    async def post(self, material: dict, sid: str, eid: str, payload: dict):
        body = json.dumps(payload, separators=(",", ":")).encode()
        old = material.get("old", "") if self.clock() - material.get("rotated", 0) < 300 else ""
        url = httpx.URL(callback(material["url"]))
        addresses = await self.resolve(url.host, 443)
        if not addresses:
            raise Refused("Callback destination unavailable")
        ip = addresses[0]
        pinned = url.copy_with(host=f"[{ip}]" if ":" in ip else ip)
        signed_headers = headers(material["secret"], sid, eid, body, int(self.clock()), old)
        signed_headers["Host"] = url.netloc.decode("ascii")
        # A dedicated no-cookie client; never the authenticated Nextcloud pool.
        async with self.client.stream(
            "POST",
            pinned,
            content=body,
            headers=signed_headers,
            extensions={"sni_hostname": url.raw_host.decode("ascii")},
            follow_redirects=False,
            timeout=8,
        ) as response:
            data = b""
            async for chunk in response.aiter_bytes():
                data += chunk
                if len(data) > 4096:
                    raise Refused("Callback response too large")
            return response.status_code, data

    async def subscription(self, auth: str, method: str, params: dict):
        if params.get("name") != NAME:
            raise Refused("Unknown event")
        room = room_argument(params.get("arguments"))
        delivery = params.get("delivery", {})
        if not isinstance(delivery, dict) or delivery.get("mode") != "webhook":
            raise Refused("Webhook delivery required")
        url = callback(delivery.get("url"))
        sid = stable_id(auth, NAME, room, url)
        async with self.lock:
            self.store.prune(self.clock())
            if method == "events/unsubscribe":
                self.store.remove(sid)
                return {}
            if room not in self.rooms:
                raise Refused("Conversation not enabled by administrator")
            principal = await self.authorize(auth, room)
            if not principal:
                raise Refused("Conversation unavailable")
            ttl = params.get("ttlMs", 3600000)
            if ttl is None:
                ttl = self.max_ttl_ms  # Indefinite leases are never granted by this server.
            if type(ttl) is not int or ttl <= 0:
                raise Refused("Invalid subscription lifetime")
            secret = delivery.get("secret")
            signing_key(secret)
            prior = self.store.get(sid)
            count = self.store.db.execute(
                "SELECT count(*) FROM subscriptions WHERE auth=?", (auth,)
            ).fetchone()[0]
            if prior is None and count >= 10:
                raise Refused("Subscription limit reached")
            now = self.clock()
            material = {"url": url, "secret": secret}
            if prior and prior["secret"] != secret:
                material.update(old=prior["secret"], rotated=now)
            elif prior:
                material.update(old=prior.get("old", ""), rotated=prior.get("rotated", 0))
            challenge = secrets.token_urlsafe(24)
            try:
                status, body = await self.post(
                    material,
                    sid,
                    "verify_" + secrets.token_hex(16),
                    {"type": "verification", "challenge": challenge},
                )
                verified = json.loads(body).get("challenge")
                if (
                    not 200 <= status < 300
                    or not isinstance(verified, str)
                    or not secrets.compare_digest(verified, challenge)
                ):
                    raise Refused("Callback verification failed")
            except (httpx.HTTPError, ValueError, AttributeError):
                raise Refused("Callback verification failed") from None
            expires = now + min(ttl, self.max_ttl_ms) / 1000
            self.store.put(sid, auth, principal, room, expires, material)
            return {
                "id": sid,
                "refreshBefore": datetime.fromtimestamp(expires, UTC).isoformat(),
                "cursor": None,
                "truncated": False,
            }

    async def ingest(self, room: str, mid: str, actor: str):
        async with self.lock:
            self.store.prune(self.clock())
            if room in self.rooms:
                self.store.enqueue(room, mid, actor, self.clock())

    async def deliver_one(self) -> bool:
        # Serial processing deliberately bounds load; acknowledged unsubscribe fences later sends.
        async with self.lock:
            now = self.clock()
            self.store.prune(now)
            row = self.store.next(now)
            if row is None:
                return False
            sub = self.store.get(row["sub"])
            if sub is None:
                return True
            if sub["room"] not in self.rooms:
                self.store.remove(sub["id"])
                return True
            attempts = row["attempts"] + 1
            status = 0
            try:
                principal = await self.authorize(sub["auth"], sub["room"])
                if principal != sub["principal"] or row["actor"] == principal:
                    self.store.remove(sub["id"])
                    return True
                payload = {
                    "eventId": row["id"],
                    "name": NAME,
                    "timestamp": datetime.fromtimestamp(row["created"], UTC).isoformat(),
                    "data": {"conversation": sub["room"], "message_id": row["message"]},
                    "cursor": None,
                }
                status, _ = await self.post(sub, sub["id"], row["id"], payload)
            except Exception:
                # Unexpected permission/storage-provider failures also consume the bounded
                # retry budget; never turn an unavailable dependency into a busy loop.
                status = 0
            if status == 410:
                self.store.remove(sub["id"])
                return True
            retry = status in (0, 408, 429) or status >= 500
            state = (
                "accepted"
                if 200 <= status < 300
                else "pending"
                if retry and attempts < 5
                else "failed"
            )
            self.store.finish(row["id"], attempts, state, status, now + min(300, 2**attempts))
            return True

    async def run(self):
        while True:
            try:
                if await self.deliver_one():
                    continue
            except Exception:
                # No payload, credential or callback URL enters logs. Persistent work stays pending.
                import logging

                logging.getLogger(__name__).warning("Talk event worker deferred a delivery")
            await asyncio.sleep(1)
