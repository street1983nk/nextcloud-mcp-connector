"""A task list on a mocked Nextcloud that honours ETags, for the chain and the modifying tools.

Shared by ``test_tasks_chain.py`` (plan 33-05) and the tool tests of plans 33-06 to 33-08.
One :class:`TaskStore` holds the objects of one list with their ETags and answers:

- ``REPORT`` with every object, its ``getetag`` and its ``calendar-data``,
- ``GET`` with the bytes and the ``ETag`` header,
- ``PUT`` with ``If-Match``: 412 on a wrong ETag, else stored under a fresh ETag (204),
- ``MOVE`` with ``Overwrite`` and ``Destination``: 412 on a wrong ETag or a taken name,
  else the object goes to the target store under the same name and ETag (201).

``fail`` plants one answer (a status or an exception) for the next write of one object
name. Every write is recorded in ``writes`` in arrival order; ``max_open`` is the largest
number of write calls in flight at the same time, so a test sees whether writes overlapped.
"""

import asyncio
from collections.abc import Iterable
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

import httpx
import respx

BASE = "http://nc.test"
USER = "alice"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/{USER}/"
HOME_PATH = f"/remote.php/dav/calendars/{USER}/"


def list_url(uri: str) -> str:
    return f"{CALENDAR_HOME}{quote(uri, safe='')}/"


class TaskStore:
    """The objects of one task list, keyed by object name, each with its current ETag."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.writes: list[tuple[str, str, str]] = []  # (method, object name, If-Match)
        self.reports = 0
        self.gets: list[str] = []
        self.fail: dict[str, int | Exception] = {}
        self.report_answer: httpx.Response | Exception | None = None
        self.open = 0
        self.max_open = 0
        self.peers: dict[str, TaskStore] = {}
        self._counter = 0

    # --- content ----------------------------------------------------------------------

    def _fresh_etag(self) -> str:
        self._counter += 1
        return f'"{self.uri}-{self._counter}"'

    def add(self, name: str, ics: str | bytes, etag: str | None = None) -> str:
        blob = ics.encode("utf-8") if isinstance(ics, str) else ics
        tag = etag if etag is not None else self._fresh_etag()
        self.objects[name] = (blob, tag)
        return tag

    def text(self, name: str) -> str:
        return self.objects[name][0].decode("utf-8")

    def etag(self, name: str) -> str:
        return self.objects[name][1]

    def snapshot(self) -> dict[str, tuple[bytes, str]]:
        return dict(self.objects)

    # --- routes -----------------------------------------------------------------------

    @staticmethod
    def _name(request: httpx.Request) -> str:
        return unquote(request.url.path.rsplit("/", 1)[-1])

    def report(self, request: httpx.Request) -> httpx.Response:
        self.reports += 1
        if isinstance(self.report_answer, Exception):
            raise self.report_answer
        if self.report_answer is not None:
            return self.report_answer
        return multistatus(self.uri, ((n, b, e) for n, (b, e) in self.objects.items()))

    def get(self, request: httpx.Request) -> httpx.Response:
        name = self._name(request)
        self.gets.append(name)
        if name not in self.objects:
            return httpx.Response(404)
        blob, tag = self.objects[name]
        return httpx.Response(200, content=blob, headers={"ETag": tag})

    async def _enter(self) -> None:
        self.open += 1
        self.max_open = max(self.max_open, self.open)
        # Give any other write that might run concurrently the chance to start.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    def _planted(self, name: str) -> httpx.Response | None:
        planted = self.fail.pop(name, None)
        if planted is None:
            return None
        if isinstance(planted, Exception):
            raise planted
        return httpx.Response(planted)

    async def put(self, request: httpx.Request) -> httpx.Response:
        name = self._name(request)
        match = request.headers.get("If-Match", "")
        self.writes.append(("PUT", name, match))
        await self._enter()
        try:
            planted = self._planted(name)
            if planted is not None:
                return planted
            if name not in self.objects:
                return httpx.Response(404)
            if match != self.objects[name][1]:
                return httpx.Response(412)
            tag = self._fresh_etag()
            self.objects[name] = (request.content, tag)
            return httpx.Response(204, headers={"ETag": tag})
        finally:
            self.open -= 1

    async def move(self, request: httpx.Request) -> httpx.Response:
        name = self._name(request)
        match = request.headers.get("If-Match", "")
        self.writes.append(("MOVE", name, match))
        await self._enter()
        try:
            planted = self._planted(name)
            if planted is not None:
                return planted
            destination = urlsplit(request.headers.get("Destination", "")).path
            target_uri = unquote(destination.rstrip("/").rsplit("/", 2)[-2])
            target_name = unquote(destination.rsplit("/", 1)[-1])
            target = self.peers.get(target_uri)
            if name not in self.objects or target is None:
                return httpx.Response(404)
            if request.headers.get("Overwrite") != "F":
                return httpx.Response(400)
            if match != self.objects[name][1] or target_name in target.objects:
                return httpx.Response(412)
            target.objects[target_name] = self.objects.pop(name)
            return httpx.Response(201)
        finally:
            self.open -= 1


#: A carriage return survives XML only as a character reference; without it the parser turns
#: every CRLF of the stored text into LF and the REPORT would not show the stored bytes.
CR = {"\r": "&#13;"}


def multistatus(uri: str, objects: Iterable[tuple[str, bytes, str]]) -> httpx.Response:
    """The REPORT answer: every object with its ``getetag`` and its exact text."""
    entries = "".join(
        f"<d:response><d:href>{HOME_PATH}{quote(uri, safe='')}/{quote(name, safe='')}</d:href>"
        f"<d:propstat><d:prop><d:getetag>{escape(tag)}</d:getetag>"
        f"<cal:calendar-data>{escape(blob.decode('utf-8'), CR)}</cal:calendar-data></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for name, blob, tag in objects
    )
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:cal="urn:ietf:params:xml:ns:caldav">{entries}</d:multistatus>'
    )
    return httpx.Response(207, text=body, headers={"Content-Type": "application/xml"})


def mount(mock: respx.MockRouter, *stores: TaskStore) -> None:
    """REPORT, GET, PUT and MOVE routes for each store; stores see each other for MOVE."""
    for store in stores:
        store.peers = {other.uri: other for other in stores}
        prefix = list_url(store.uri)
        mock.route(method="REPORT", url=prefix).mock(side_effect=store.report)
        mock.route(method="GET", url__startswith=prefix).mock(side_effect=store.get)
        mock.route(method="PUT", url__startswith=prefix).mock(side_effect=store.put)
        mock.route(method="MOVE", url__startswith=prefix).mock(side_effect=store.move)
