"""Behavioral tests for isolated event subscriptions and durable delivery."""

import asyncio
import base64
import hashlib
import hmac
import json

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector.events.protocol import NAME, Refused, callback, headers, talk_message
from mcp_connector.events.service import EventService
from mcp_connector.events.store import EventStore
from mcp_connector.events.transport import EventTransport
from mcp_connector.oauth.verifier import OAuthIdentity

SECRET = "whsec_" + base64.b64encode(b"a" * 32).decode()
URL = "https://connectors.api.openai.com/test-callback"


def params(url=URL, secret=SECRET, room="room1234", ttl: int | None = 3600000):
    return {
        "name": NAME,
        "arguments": {"conversation": room},
        "ttlMs": ttl,
        "delivery": {"mode": "webhook", "url": url, "secret": secret},
    }


class Harness:
    def __init__(self, tmp_path):
        self.now, self.allowed, self.sent, self.status = 1000.0, True, [], 200
        self.path = tmp_path / "events.sqlite3"
        self.store = EventStore(self.path, b"k" * 32)
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.receive))
        self.service = EventService(
            self.store,
            self.client,
            self.authorize,
            frozenset({"room1234"}),
            lambda: self.now,
            resolve=self.resolve,
        )

    async def resolve(self, host, port):
        return ["8.8.8.8"]  # Mock transport only; no actual network connection.

    async def authorize(self, auth, room):
        return {"a": "neo", "b": "other"}.get(auth) if self.allowed else None

    def receive(self, request):
        payload = json.loads(request.content)
        # Independent verifier, not the signing implementation under test.
        signed = request.headers["webhook-id"] + "." + request.headers["webhook-timestamp"] + "."
        expected = base64.b64encode(
            hmac.digest(b"a" * 32, signed.encode() + request.content, "sha256")
        ).decode()
        assert "v1," + expected in request.headers["webhook-signature"]
        if payload.get("type") == "verification":
            return httpx.Response(200, json={"challenge": payload["challenge"]})
        self.sent.append(payload)
        return httpx.Response(self.status)

    async def close(self):
        await self.client.aclose()
        self.store.close()


def test_roundtrip_dedup_restart_and_no_content(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "10", "samuel")
        await h.service.ingest("room1234", "10", "samuel")
        # Restart retains the outbox without storing a Nextcloud password or callback plaintext.
        h.store.close()
        assert SECRET.encode() not in h.path.read_bytes()
        h.store = EventStore(h.path, b"k" * 32)
        h.service.store = h.store
        assert await h.service.deliver_one()
        assert not await h.service.deliver_one()
        assert len(h.sent) == 1
        assert h.sent[0]["data"] == {"conversation": "room1234", "message_id": "10"}
        await h.service.ingest("room1234", "10", "samuel")
        assert not await h.service.deliver_one()
        await h.close()

    asyncio.run(run())


def test_own_messages_and_other_rooms_are_ignored(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "11", "neo")
        await h.service.ingest("other123", "12", "samuel")
        assert not await h.service.deliver_one()
        await h.close()

    asyncio.run(run())


@pytest.mark.parametrize("action", ["revocation", "expiry", "unsubscribe"])
def test_no_delivery_after_access_ends(tmp_path, action):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "13", "samuel")
        if action == "revocation":
            h.allowed = False
        elif action == "expiry":
            h.now += 3601
        else:
            await h.service.subscription("a", "events/unsubscribe", params())
        await h.service.deliver_one()
        assert h.sent == []
        await h.close()

    asyncio.run(run())


def test_owner_cannot_unsubscribe_another_connection(tmp_path):
    async def run():
        h = Harness(tmp_path)
        a = await h.service.subscription("a", "events/subscribe", params())
        b = await h.service.subscription("b", "events/subscribe", params())
        assert a["id"] != b["id"]
        await h.service.subscription("b", "events/unsubscribe", params())
        assert h.store.get(a["id"]) is not None
        await h.close()

    asyncio.run(run())


def test_retry_keeps_event_id_and_then_stops(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "14", "samuel")
        h.status = 503
        await h.service.deliver_one()
        assert not await h.service.deliver_one()
        h.now += 3
        h.status = 200
        await h.service.deliver_one()
        assert h.sent[0]["eventId"] == h.sent[1]["eventId"]
        assert h.sent[0]["timestamp"] == h.sent[1]["timestamp"]
        assert not await h.service.deliver_one()
        await h.close()

    asyncio.run(run())


def test_gone_removes_subscription(tmp_path):
    async def run():
        h = Harness(tmp_path)
        sub = await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "15", "samuel")
        h.status = 410
        await h.service.deliver_one()
        assert h.store.get(sub["id"]) is None
        await h.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "url",
    [
        "http://connectors.api.openai.com/a",
        "https://127.0.0.1/a",
        "https://connectors.api.openai.com.evil.test/a",
        "https://user@chatgpt.com/a",
        "https://chatgpt.com:8443/a",
    ],
)
def test_callback_targets_are_bounded(url):
    with pytest.raises(Refused):
        callback(url)


def test_signature_rotation_supports_overlap():
    old = "whsec_" + base64.b64encode(b"b" * 32).decode()
    assert len(headers(SECRET, "sub", "event", b"{}", 1, old)["webhook-signature"].split()) == 2


def test_talk_signature_and_system_filter():
    body = json.dumps(
        {
            "type": "Create",
            "actor": {"type": "Person", "id": "users/samuel"},
            "target": {"id": "room1234"},
            "object": {
                "type": "Note",
                "name": "message",
                "id": 20,
                "content": json.dumps({"message": "not exported"}),
            },
        }
    ).encode()
    random, secret = "a" * 64, "b" * 64
    sig = hmac.new(secret.encode(), random.encode() + body, hashlib.sha256).hexdigest()
    assert talk_message(secret, random, sig, body) == ("room1234", "20", "samuel")
    with pytest.raises(Refused):
        talk_message(secret, random, sig, body + b" ")
    system = body.replace(b'"Create"', b'"Join"')
    sig = hmac.new(secret.encode(), random.encode() + system, hashlib.sha256).hexdigest()
    assert talk_message(secret, random, sig, system) is None


def test_transport_discovery_and_authenticated_events(tmp_path):
    h = Harness(tmp_path)

    async def downstream(scope, receive, send):
        request = Request(scope, receive)
        rpc = await request.json()
        await JSONResponse(
            {"jsonrpc": "2.0", "id": rpc["id"], "result": {"capabilities": {"tools": {}}}}
        )(scope, receive, send)

    transport = EventTransport(downstream, h.service)

    async def app(scope, receive, send):
        if dict(scope.get("headers", [])).get(b"authorization") == b"test":
            scope.setdefault("state", {})["oauth_identity"] = OAuthIdentity(
                "neo", "hidden", "a", "client", "neo"
            )
        await transport(scope, receive, send)

    client = TestClient(app)
    try:
        discovery = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"}
        ).json()
        assert discovery["result"]["capabilities"] == {"tools": {}, "events": {}}
        payload = {"jsonrpc": "2.0", "id": 2, "method": "events/list"}
        assert "error" in client.post("/mcp", json=payload).json()
        answer = client.post("/mcp", headers={"authorization": "test"}, json=payload).json()
        assert answer["result"]["events"][0]["name"] == NAME
    finally:
        client.close()
        asyncio.run(h.close())


def test_real_sdk_discovery_and_tools_are_preserved(tmp_path):
    from mcp.server import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings

    server = MCPServer("events-contract-test")

    @server.tool()
    def echo(value: str) -> str:
        return value

    app = server.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    h = Harness(tmp_path)
    for route in app.routes:
        if isinstance(route, Route) and route.path == "/mcp":
            route.app = EventTransport(route.app, h.service)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/mcp",
                headers={
                    "accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "server/discover",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "server/discover",
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        }
                    },
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert "events" in data["result"]["capabilities"], data
            assert "tools" in data["result"]["capabilities"], data
    finally:
        asyncio.run(h.close())


def test_exapp_events_default_off_and_lifecycle(tmp_path, monkeypatch):
    from mcp_connector import entry_exapp
    from mcp_connector.events import exapp

    env = {
        "APP_ID": "mcp_events_test",
        "APP_SECRET": "test-app-secret",
        "APP_VERSION": "0.5.0",
        "NEXTCLOUD_URL": "https://cloud.test",
        "APP_PERSISTENT_STORAGE": str(tmp_path),
        "NC_MCP_DISABLE_DNS_REBINDING_PROTECTION": "1",
    }
    app = entry_exapp.build_exapp_app(env)
    assert "/events/talk" not in {getattr(r, "path", "") for r in app.routes}
    assert not (tmp_path / "talk-events.sqlite3").exists()

    async def data_key(_env):
        return b"k" * 32

    monkeypatch.setattr(exapp.crypto, "data_key", data_key)
    app = entry_exapp.build_exapp_app(
        {
            **env,
            "NC_MCP_TALK_EVENTS_ENABLED": "true",
            "NC_MCP_TALK_EVENTS_ROOMS": "room1234",
            "NC_MCP_TALK_EVENTS_SECRET": "s" * 32,
        }
    )
    with TestClient(app) as client:
        assert (tmp_path / "talk-events.sqlite3").exists()
        assert client.post("/events/talk", content=b"{}").status_code == 403
        # The opt-in extension must not bypass the existing MCP authentication boundary.
        assert client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "events/list"}
        ).status_code in (401, 403)
