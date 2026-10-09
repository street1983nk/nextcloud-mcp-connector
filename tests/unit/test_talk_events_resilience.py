"""Fault and accelerated renewal tests; these do not certify a live host lease."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from test_talk_events import Harness, params

from mcp_connector.errors import ToolError
from mcp_connector.events.exapp import Runtime
from mcp_connector.events.protocol import Refused
from mcp_connector.events.store import EventStore


def test_callback_pins_validated_ip_and_preserves_tls_hostname(tmp_path):
    async def run():
        h = Harness(tmp_path)
        seen = []

        def receive(request):
            seen.append(request)
            payload = json.loads(request.content)
            return httpx.Response(200, json={"challenge": payload["challenge"]})

        await h.client.aclose()
        h.client = httpx.AsyncClient(transport=httpx.MockTransport(receive))
        h.service.client = h.client
        resolver = AsyncMock(return_value=["8.8.8.8"])
        h.service.resolve = resolver
        await h.service.subscription("a", "events/subscribe", params())
        resolver.assert_awaited_once_with("connectors.api.openai.com", 443)
        assert seen[0].url.host == "8.8.8.8"
        assert seen[0].headers["host"] == "connectors.api.openai.com"
        assert seen[0].extensions["sni_hostname"] == "connectors.api.openai.com"
        resolver.return_value = None
        with pytest.raises(Refused, match="destination unavailable"):
            await h.service.subscription("a", "events/subscribe", params())
        assert len(seen) == 1
        await h.close()

    asyncio.run(run())


def test_indefinite_lease_request_is_granted_finite(tmp_path):
    async def run():
        h = Harness(tmp_path)
        sub = await h.service.subscription("a", "events/subscribe", params(ttl=None))
        stored = h.store.get(sub["id"])
        assert stored is not None
        assert stored["expires"] == h.now + 3600
        assert sub["refreshBefore"] is not None
        await h.close()

    asyncio.run(run())


def test_short_lifetime_is_advertised_and_expires(tmp_path):
    async def run():
        h = Harness(tmp_path)
        h.service.max_ttl_ms = 120000
        sub = await h.service.subscription("a", "events/subscribe", params())
        stored = h.store.get(sub["id"])
        assert stored is not None
        assert stored["expires"] == h.now + 120
        h.now += 121
        await h.service.ingest("room1234", "8", "samuel")
        assert not await h.service.deliver_one()
        assert h.store.get(sub["id"]) is None
        await h.close()

    asyncio.run(run())


def test_three_days_renewal_and_restart(tmp_path):
    async def run():
        h = Harness(tmp_path)
        original = await h.service.subscription("a", "events/subscribe", params())
        for cycle in range(144):
            h.now += 1800
            renewed = await h.service.subscription("a", "events/subscribe", params())
            assert renewed["id"] == original["id"]
            await h.service.ingest("room1234", str(100 + cycle), "samuel")
            h.store.close()
            h.store = EventStore(h.path, b"k" * 32)
            h.service.store = h.store
            assert await h.service.deliver_one()
            assert not await h.service.deliver_one()
        assert len(h.sent) == 144
        assert h.store.db.execute("SELECT count(*) FROM subscriptions").fetchone()[0] == 1
        h.now += 3601
        await h.service.ingest("room1234", "999", "samuel")
        assert not await h.service.deliver_one()
        assert h.store.get(original["id"]) is None
        await h.close()

    asyncio.run(run())


def test_failed_renewal_preserves_existing_lease(tmp_path):
    async def run():
        h = Harness(tmp_path)
        sub = await h.service.subscription("a", "events/subscribe", params())
        stored = h.store.get(sub["id"])
        assert stored is not None
        expires = stored["expires"]
        h.now += 1800
        old_post = h.service.post

        async def unavailable(*args, **kwargs):
            raise httpx.ConnectError("Synthetic offline receiver")

        h.service.post = unavailable
        with pytest.raises(Refused):
            await h.service.subscription("a", "events/subscribe", params())
        stored = h.store.get(sub["id"])
        assert stored is not None
        assert stored["expires"] == expires
        h.service.post = old_post
        await h.service.ingest("room1234", "1", "samuel")
        assert await h.service.deliver_one()
        assert len(h.sent) == 1
        await h.close()

    asyncio.run(run())


def test_callback_outage_retry_budget_and_restart(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "2", "samuel")
        h.status = 503
        for _ in range(5):
            assert await h.service.deliver_one()
            h.store.close()
            h.store = EventStore(h.path, b"k" * 32)
            h.service.store = h.store
            h.now += 301
        assert not await h.service.deliver_one()
        row = h.store.db.execute("SELECT * FROM deliveries").fetchone()
        assert (row["state"], row["attempts"]) == ("failed", 5)
        assert len({p["eventId"] for p in h.sent}) == 1
        await h.close()

    asyncio.run(run())


def test_removed_allowlist_blocks_persisted_delivery(tmp_path):
    async def run():
        h = Harness(tmp_path)
        sub = await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "3", "samuel")
        h.service.rooms = frozenset()
        await h.service.deliver_one()
        assert h.sent == []
        assert h.store.get(sub["id"]) is None
        await h.close()

    asyncio.run(run())


def test_uncertain_membership_retries_without_sending_or_removing(tmp_path, monkeypatch):
    async def run():
        h = Harness(tmp_path)
        sub = await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "4", "samuel")
        row = SimpleNamespace(nc_user="neo", nc_account_id="neo", revoked_at=None, client_id="c")
        oauth = SimpleNamespace(
            load_authorization=AsyncMock(return_value=row),
            access_disabled=AsyncMock(return_value=False),
            app_password=AsyncMock(return_value="synthetic-password"),
        )
        runtime = Runtime(
            None,
            AsyncMock(return_value=oauth),
            AsyncMock(return_value={}),
            "https://cloud.test",
            frozenset({"room1234"}),
            "unused",
        )
        runtime.nc_client = h.client
        check = AsyncMock(side_effect=ToolError("Unavailable", "Retry"))
        monkeypatch.setattr("mcp_connector.events.exapp.one_room", check)
        h.service.authorize = runtime.authorize
        await h.service.deliver_one()
        assert h.sent == []
        assert h.store.get(sub["id"]) is not None
        check.side_effect = None
        check.return_value = {"token": "room1234"}
        h.now += 3
        await h.service.deliver_one()
        assert len(h.sent) == 1
        await h.close()

    asyncio.run(run())


def test_crash_after_receiver_acceptance_replays_same_identity(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "5", "samuel")
        finish = h.store.finish

        def disk_failure(*args, **kwargs):
            raise OSError("Synthetic write failure after HTTP acceptance")

        h.store.finish = disk_failure
        with pytest.raises(OSError, match="Synthetic write failure"):
            await h.service.deliver_one()
        h.store.finish = finish
        h.store.close()
        h.store = EventStore(h.path, b"k" * 32)
        h.service.store = h.store
        await h.service.deliver_one()
        assert len(h.sent) == 2
        assert h.sent[0] == h.sent[1]  # Receiver must deduplicate: this is at-least-once.
        assert not await h.service.deliver_one()
        await h.close()

    asyncio.run(run())


def test_unsubscribe_waits_for_inflight_then_fences_sends(tmp_path):
    async def run():
        h = Harness(tmp_path)
        await h.service.subscription("a", "events/subscribe", params())
        await h.service.ingest("room1234", "6", "samuel")
        entered, release = asyncio.Event(), asyncio.Event()

        async def receive(request):
            entered.set()
            await release.wait()
            h.sent.append(json.loads(request.content))
            return httpx.Response(200)

        await h.client.aclose()
        h.client = httpx.AsyncClient(transport=httpx.MockTransport(receive))
        h.service.client = h.client
        delivery = asyncio.create_task(h.service.deliver_one())
        await asyncio.wait_for(entered.wait(), 2)
        stop = asyncio.create_task(h.service.subscription("a", "events/unsubscribe", params()))
        await asyncio.sleep(0)
        assert not stop.done()
        release.set()
        await delivery
        await stop
        await h.service.ingest("room1234", "7", "samuel")
        assert not await h.service.deliver_one()
        assert len(h.sent) == 1
        await h.close()

    asyncio.run(run())
