"""Composition for ExApp OAuth only; the default deployment stays unchanged."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress

import httpx
from starlette.routing import Route

from .. import config
from ..nextcloud import NcClients
from ..nextcloud.credentials import Credentials
from ..nextcloud.http import NoCookieJar
from ..oauth import crypto
from ..oauth.principal import principal_of
from ..tools.talk import one_room
from .protocol import Refused, room_argument
from .service import EventService
from .store import EventStore
from .transport import EventTransport, webhook


class Runtime:
    def __init__(self, env, oauth_store, client_lookup, backend, rooms, secret):
        self.env, self.oauth_store, self.client_lookup = env, oauth_store, client_lookup
        self.backend, self.rooms, self.secret = backend, rooms, secret
        self.service: EventService | None = None
        self.nc_client: httpx.AsyncClient | None = None

    async def authorize(self, auth_id, room):
        store = await self.oauth_store()
        row = await store.load_authorization(auth_id)
        if (
            row is None
            or row.revoked_at is not None
            or await store.access_disabled(principal_of(row))
        ):
            return None
        if await self.client_lookup(row.client_id, may_fetch=False) is None:
            return None
        password = await store.app_password(auth_id)
        if not password:
            return None  # Delegated impersonation connections are outside this first POC.
        creds = Credentials(self.backend, row.nc_user, password)
        if self.nc_client is None:
            return None
        # An unavailable membership/guard check is not proof of revoked OAuth access.
        # Propagate it to the bounded retry path; no callback is sent without success.
        await one_room(
            NcClients(client=self.nc_client, creds=creds), room, include_last_message=False
        )
        return principal_of(row)

    async def subscription(self, *args):
        if self.service is None:
            raise Refused("Events are not ready")
        return await self.service.subscription(*args)

    async def ingest(self, *args):
        if self.service is None:
            raise OverflowError("Events are not ready")
        return await self.service.ingest(*args)


def configure(app, env, oauth_store, client_lookup, backend):
    source = os.environ if env is None else env
    if source.get("NC_MCP_TALK_EVENTS_ENABLED", "false").lower() != "true":
        return None
    rooms = frozenset(filter(None, source.get("NC_MCP_TALK_EVENTS_ROOMS", "").split(",")))
    secret = source.get("NC_MCP_TALK_EVENTS_SECRET", "")
    max_ttl_ms = int(source.get("NC_MCP_TALK_EVENTS_MAX_TTL_MS", "3600000"))
    if not 60000 <= max_ttl_ms <= 3600000:
        raise ValueError("Event lifetime must be between one minute and one hour")
    if not rooms or len(rooms) > 10 or len(secret) < 32:
        raise ValueError(
            "Talk events require bounded rooms and a webhook secret of at least 32 characters"
        )
    for room in rooms:
        room_argument({"conversation": room})
    runtime = Runtime(env, oauth_store, client_lookup, backend, rooms, secret)
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous(application) as state:
            key = await crypto.data_key(env)
            store = EventStore(config.persistent_storage(env) / "talk-events.sqlite3", key)
            async with (
                # Pinned IP URLs must never share a TLS connection across original names.
                httpx.AsyncClient(
                    cookies=NoCookieJar(),
                    trust_env=False,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
                ) as outbound,
                httpx.AsyncClient(cookies=NoCookieJar(), timeout=8, follow_redirects=False) as nc,
            ):
                runtime.nc_client = nc
                runtime.service = EventService(
                    store, outbound, runtime.authorize, rooms, max_ttl_ms=max_ttl_ms
                )
                worker = asyncio.create_task(runtime.service.run(), name="talk-events-outbox")
                try:
                    yield state
                finally:
                    worker.cancel()
                    with suppress(asyncio.CancelledError):
                        await worker
                    runtime.service = None
                    store.close()

    app.router.lifespan_context = lifespan
    app.router.routes.append(
        Route("/events/talk", webhook(runtime, secret, backend), methods=["POST"])
    )
    return runtime


def wrap(app, runtime):
    return EventTransport(app, runtime) if runtime is not None else app
