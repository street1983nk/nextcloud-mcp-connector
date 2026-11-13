"""Unit tests for the task chain of ``tools/tasks.py`` (plan 33-05), every path without a network.

Pinned here: the descendants of a task (children, grandchildren, ...) in post-order, found
with an exact UID match over ``RELATED-TO`` without ``RELTYPE`` or with ``RELTYPE=PARENT``
only, safe against cycles and double edges, siblings ordered by object name (D-33-09); the
check before the first write (more than ``CHAIN_CAP`` descendants, a recurring descendant or
one with several VTODO, a read only list), which never sends a request (D-33-10, D-33-11);
the read of the list (one REPORT without prefilter under the budget of the list, skipped
objects counted), and the run of the chain: one write after the other, never side by side,
descendants with the ETag of the same REPORT, the named task last with the ETag of the
assistant, target state and left alone without a call, a stop at the first failure with an
honest report that names only task ids and the list (D-33-09).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import task_store

from mcp_connector import ids
from mcp_connector.errors import REASON_GUARD_TRIPPED, REASON_TIMEOUT, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import tasks as tasks_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import ics_edit
from mcp_connector.tools import tasks as tasks_tools

OWN = "spike30-aufgaben"
RAW_MEASUREMENT = (
    Path(__file__).resolve().parents[2]
    / ".planning"
    / "phases"
    / "33-aufgaben-aendern"
    / "raw"
    / "33-01-messung.txt"
)


def task_list(*, writable: bool = True, name: str = OWN) -> tasks_client.TaskList:
    return tasks_client.TaskList(
        uri=OWN, key=ids.task_list_key(OWN), name=name, shared=False, writable=writable
    )


def vtodo(uid: str, *lines: str, summary: str | None = None) -> str:
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "DTSTAMP:20261111T120000Z",
        f"SUMMARY:{summary if summary is not None else uid}",
        *lines,
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return "\r\n".join(body) + "\r\n"


def obj(name: str, ics: str, etag: str = "") -> tasks_client.TodoObject:
    return tasks_client.TodoObject(
        object_name=name, ics=ics.encode("utf-8"), etag=etag or f'"etag-{name}"'
    )


def child(uid: str, parent: str, *lines: str) -> tasks_client.TodoObject:
    return obj(f"{uid}.ics", vtodo(uid, f"RELATED-TO:{parent}", *lines))


def entries_of(*objects: tasks_client.TodoObject) -> list[dict[str, Any]]:
    entries, skipped = tasks_tools.chain_entries(task_list(), list(objects))
    assert skipped == 0
    return entries


def uids(order: list[dict[str, Any]]) -> list[str]:
    return [entry["uid"] for entry in order]


# --- CHAIN_CAP -----------------------------------------------------------------------------


def test_the_chain_cap_is_the_measured_value_with_its_raw_line() -> None:
    assert tasks_tools.CHAIN_CAP == 50
    raw = next(
        line
        for line in RAW_MEASUREMENT.read_text(encoding="utf-8").splitlines()
        if line.startswith("MESSWERT chain_cap=")
    )
    source = Path(inspect.getfile(tasks_tools)).read_text(encoding="utf-8")
    block = source[: source.index("\nCHAIN_CAP = ")]
    comment = " ".join(
        line.removeprefix("#:").strip()
        for line in block.splitlines()[-12:]
        if line.startswith("#:")
    )
    assert raw in comment
    assert "2026-11-13" in comment
    assert re.search(r"^CHAIN_CAP = 50$", source, re.MULTILINE)


# --- entries of the list -------------------------------------------------------------------


def test_entries_carry_text_etag_object_name_and_id() -> None:
    text = vtodo("a", "RELATED-TO:root")
    (entry,) = entries_of(obj("a.ics", text, '"e-a"'))
    assert entry["uid"] == "a"
    assert entry["parents"] == ["root"]
    assert entry["etag"] == '"e-a"'
    assert entry["object_name"] == "a.ics"
    assert entry["text"] == text
    assert entry["id"] == ids.encode_task(ids.task_list_key(OWN), "a.ics")
    assert entry["status"] == "open"


def test_unreadable_objects_are_counted_as_skipped() -> None:
    entries, skipped = tasks_tools.chain_entries(
        task_list(),
        [obj("broken.ics", "not ical"), obj("ok.ics", vtodo("ok")), obj("x:y.ics", vtodo("x"))],
    )
    assert [entry["uid"] for entry in entries] == ["ok"]
    assert skipped == 2


# --- descendants ---------------------------------------------------------------------------


def test_a_task_without_children_has_no_descendants() -> None:
    entries = entries_of(obj("root.ics", vtodo("root")), obj("other.ics", vtodo("other")))
    assert tasks_tools.descendants_post_order("root", entries) == []


def test_depth_one_comes_in_object_name_order() -> None:
    entries = entries_of(
        child("c", "root"), child("a", "root"), child("b", "root"), obj("root.ics", vtodo("root"))
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["a", "b", "c"]


def test_depth_three_comes_in_post_order() -> None:
    entries = entries_of(
        obj("root.ics", vtodo("root")),
        child("k1", "root"),
        child("k2", "root"),
        child("e1", "k1"),
        child("e2", "k1"),
        child("u1", "e1"),
        child("e3", "k2"),
    )
    order = uids(tasks_tools.descendants_post_order("root", entries))
    assert order == ["u1", "e1", "e2", "k1", "e3", "k2"]
    # every parent comes after its whole subtree
    for entry in tasks_tools.descendants_post_order("root", entries):
        for parent in entry["parents"]:
            if parent != "root":
                assert order.index(parent) > order.index(entry["uid"])


def test_siblings_follow_the_object_name_not_the_uid_or_summary() -> None:
    entries = entries_of(
        obj("2.ics", vtodo("a", "RELATED-TO:root", summary="zz")),
        obj("1.ics", vtodo("b", "RELATED-TO:root", summary="aa")),
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["b", "a"]


def test_a_cycle_through_the_named_task_ends_without_doubles() -> None:
    entries = entries_of(
        obj("root.ics", vtodo("root", "RELATED-TO:b")),
        child("a", "root"),
        child("b", "a"),
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["b", "a"]


def test_a_cycle_between_children_ends_without_doubles() -> None:
    entries = entries_of(
        child("a", "root"),
        obj("b.ics", vtodo("b", "RELATED-TO:a")),
        obj("c.ics", vtodo("c", "RELATED-TO:b")),
        obj("d.ics", vtodo("d", "RELATED-TO:c")),
    )
    # a also names c as a parent: a -> b -> c -> a
    looped = entries_of(
        obj("a.ics", vtodo("a", "RELATED-TO:root", "RELATED-TO:c")),
        obj("b.ics", vtodo("b", "RELATED-TO:a")),
        obj("c.ics", vtodo("c", "RELATED-TO:b")),
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["d", "c", "b", "a"]
    order = uids(tasks_tools.descendants_post_order("root", looped))
    assert sorted(order) == ["a", "b", "c"]
    assert order == ["c", "b", "a"]


def test_child_and_sibling_reltypes_do_not_count() -> None:
    entries = entries_of(
        obj("a.ics", vtodo("a", "RELATED-TO;RELTYPE=CHILD:root")),
        obj("b.ics", vtodo("b", "RELATED-TO;RELTYPE=SIBLING:root")),
        obj("c.ics", vtodo("c", "RELATED-TO;RELTYPE=PARENT:root")),
        obj("d.ics", vtodo("d", "RELATED-TO;RELTYPE=parent:root")),
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["c", "d"]


def test_a_uid_that_only_contains_the_named_one_does_not_count() -> None:
    entries = entries_of(
        child("a", "root-2"),
        child("b", "xroot"),
        child("c", "ROOT"),
        child("d", " root"),
        child("e", "root"),
    )
    # " root" is stripped like every UID; case and substrings never match
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["d", "e"]


def test_a_double_edge_counts_once() -> None:
    entries = entries_of(
        obj("a.ics", vtodo("a", "RELATED-TO:root", "RELATED-TO:root")),
        obj("b.ics", vtodo("b", "RELATED-TO:root", "RELATED-TO:a")),
    )
    # b is a child of root and of a: it comes once, under a, before a
    order = uids(tasks_tools.descendants_post_order("root", entries))
    assert order == ["b", "a"]


def test_the_named_task_itself_and_a_copy_of_its_uid_never_come_back() -> None:
    entries = entries_of(
        obj("root.ics", vtodo("root", "RELATED-TO:root")),
        obj("copy.ics", vtodo("root", "RELATED-TO:root")),
        child("a", "root"),
    )
    assert uids(tasks_tools.descendants_post_order("root", entries)) == ["a"]


def test_a_deep_chain_needs_no_recursion() -> None:
    objects = [obj("n0000.ics", vtodo("n0", "RELATED-TO:root"))]
    objects += [
        obj(f"n{i:04d}.ics", vtodo(f"n{i}", f"RELATED-TO:n{i - 1}")) for i in range(1, 3000)
    ]
    order = tasks_tools.descendants_post_order("root", entries_of(*objects))
    assert len(order) == 3000
    assert order[0]["uid"] == "n2999"
    assert order[-1]["uid"] == "n0"


# --- the check before the first write ------------------------------------------------------


def wide(count: int) -> list[dict[str, Any]]:
    return entries_of(*(child(f"k{i:03d}", "root") for i in range(count)))


def refusal(task: tasks_client.TaskList, descendants: list[dict[str, Any]]) -> ToolError:
    with pytest.raises(ToolError) as caught:
        tasks_tools.check_chain(task, descendants)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    return caught.value


def test_exactly_chain_cap_descendants_pass() -> None:
    descendants = tasks_tools.descendants_post_order("root", wide(tasks_tools.CHAIN_CAP))
    assert len(descendants) == tasks_tools.CHAIN_CAP
    tasks_tools.check_chain(task_list(), descendants)


def test_one_more_than_chain_cap_is_refused_with_count_and_cap() -> None:
    count = tasks_tools.CHAIN_CAP + 1
    descendants = tasks_tools.descendants_post_order("root", wide(count))
    error = refusal(task_list(), descendants)
    assert str(count) in error.message
    assert str(tasks_tools.CHAIN_CAP) in error.message


def test_a_recurring_descendant_is_refused_with_its_id() -> None:
    entries = entries_of(
        child("a", "root"),
        child("b", "root", "DTSTART:20261111T120000Z", "RRULE:FREQ=WEEKLY"),
    )
    descendants = tasks_tools.descendants_post_order("root", entries)
    error = refusal(task_list(), descendants)
    assert ids.encode_task(ids.task_list_key(OWN), "b.ics") in error.message
    assert "recurring" in error.message


def test_a_descendant_with_several_vtodo_is_refused_with_its_id() -> None:
    two = vtodo("b", "RELATED-TO:root").replace(
        "END:VCALENDAR",
        "BEGIN:VTODO\r\nUID:b2\r\nDTSTAMP:20261111T120000Z\r\nSUMMARY:x\r\nEND:VTODO\r\n"
        "END:VCALENDAR",
    )
    entries = entries_of(child("a", "root"), obj("b.ics", two))
    descendants = tasks_tools.descendants_post_order("root", entries)
    assert "b" in uids(descendants)
    error = refusal(task_list(), descendants)
    assert ids.encode_task(ids.task_list_key(OWN), "b.ics") in error.message


def test_a_read_only_list_is_refused() -> None:
    descendants = tasks_tools.descendants_post_order("root", wide(2))
    error = refusal(task_list(writable=False, name="Einkauf"), descendants)
    assert "Einkauf" in error.message
    assert "read only" in error.message
    # also without any descendant: the named task lives in the same list
    refusal(task_list(writable=False), [])


def test_no_refusal_sends_a_request() -> None:
    assert not inspect.iscoroutinefunction(tasks_tools.check_chain)
    assert not inspect.iscoroutinefunction(tasks_tools.descendants_post_order)
    recurring = entries_of(child("b", "root", "DTSTART:20261111T120000Z", "RRULE:FREQ=DAILY"))
    with respx.mock(assert_all_called=False) as mock:
        for task, descendants in (
            (task_list(), wide(tasks_tools.CHAIN_CAP + 1)),
            (task_list(), recurring),
            (task_list(writable=False), []),
        ):
            with pytest.raises(ToolError):
                tasks_tools.check_chain(task, descendants)
        assert mock.calls.call_count == 0


# --- reading the list and running the chain ------------------------------------------------
# A mocked list that honours If-Match (task_store.py, shared with plans 33-06 to 33-08).

SECRET = "app-password-test"
SHARED = "spike30-b-rw_shared_by_bob"
LEAKS = ("_shared_by_", "bob", "remote.php", "http", "calendars/")

Decide = Callable[[dict[str, Any]], "bytes | tasks_tools.ChainSkip"]
Write = Callable[[dict[str, Any], bytes, str], Awaitable[str]]


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(task_store.BASE, task_store.USER, SECRET),
    )


def listed(uri: str, name: str = "Einkauf") -> tasks_client.TaskList:
    return tasks_client.TaskList(
        uri=uri, key=ids.task_list_key(uri), name=name, shared=False, writable=True
    )


def tid(uri: str, name: str) -> str:
    return ids.encode_task(ids.task_list_key(uri), name)


def tree(
    store: task_store.TaskStore, *edges: tuple[str, str], extra: dict[str, str] | None = None
) -> None:
    """``root`` plus one object per edge (uid, parent uid), object name ``<uid>.ics``."""
    extra = extra or {}
    store.add("root.ics", vtodo("root", *_lines(extra.get("root"))))
    for uid, parent in edges:
        store.add(f"{uid}.ics", vtodo(uid, f"RELATED-TO:{parent}", *_lines(extra.get(uid))))


def _lines(text: str | None) -> tuple[str, ...]:
    return (text,) if text else ()


def complete(entry: dict[str, Any]) -> bytes | tasks_tools.ChainSkip:
    """A stand-in for the edit of 33-06: target state is skipped, cancelled left alone."""
    if entry["status"] == "completed":
        return tasks_tools.ChainSkip.UNCHANGED
    if entry["status"] == "cancelled":
        return tasks_tools.ChainSkip.LEFT_ALONE
    return entry["text"].replace("SUMMARY:", "STATUS:COMPLETED\r\nSUMMARY:", 1).encode("utf-8")


def relocate(entry: dict[str, Any]) -> bytes | tasks_tools.ChainSkip:
    return b""


def put_writer(clients: NcClients, task_list: tasks_client.TaskList) -> Write:
    async def write(entry: dict[str, Any], payload: bytes, etag: str) -> str:
        return await tasks_client.put_existing_todo(
            clients.client, clients.creds, task_list, entry["object_name"], payload, etag
        )

    return write


def move_writer(
    clients: NcClients, source: tasks_client.TaskList, target: tasks_client.TaskList
) -> Write:
    async def write(entry: dict[str, Any], payload: bytes, etag: str) -> str:
        assert payload == b""
        await tasks_client.move_todo(
            clients.client, clients.creds, source, target, entry["object_name"], etag
        )
        return ""

    return write


async def run(
    clients: NcClients,
    task_list: tasks_client.TaskList,
    *,
    root_etag: str | None = None,
    decide: Decide = complete,
    write: Write | None = None,
) -> tasks_tools.ChainReport:
    entries, skipped = await tasks_tools.read_chain_list(clients, task_list)
    root = next(entry for entry in entries if entry["object_name"] == "root.ics")
    descendants = tasks_tools.descendants_post_order(root["uid"], entries)
    tasks_tools.check_chain(task_list, descendants)
    return await tasks_tools.run_chain(
        task_list,
        root,
        root["etag"] if root_etag is None else root_etag,
        descendants,
        decide,
        write if write is not None else put_writer(clients, task_list),
        skipped=skipped,
    )


def written(store: task_store.TaskStore) -> list[str]:
    return [name for _method, name, _match in store.writes]


@pytest.mark.anyio
async def test_the_list_is_read_with_one_report_without_prefilter(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"))
    store.add("broken.ics", "not ical")
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        entries, skipped = await tasks_tools.read_chain_list(clients, listed(OWN))
        requests = [call.request for call in mock.calls]
    assert [request.method for request in requests] == ["REPORT"]
    assert b"prop-filter" not in requests[0].content
    assert skipped == 1
    by_name = {entry["object_name"]: entry for entry in entries}
    assert by_name["a.ics"]["etag"] == store.etag("a.ics")
    assert by_name["a.ics"]["text"] == store.text("a.ics")
    assert by_name["a.ics"]["parents"] == ["root"]


@pytest.mark.parametrize(
    "answer", [httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow")], ids=["read", "connect"]
)
@pytest.mark.anyio
async def test_a_report_timeout_is_a_refusal_without_a_write(
    clients: NcClients, answer: Exception
) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"))
    store.report_answer = answer
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await run(clients, listed(OWN))
    assert "list did not answer in time" in caught.value.message
    assert caught.value.reason == REASON_TIMEOUT
    assert store.writes == []


@pytest.mark.anyio
async def test_the_budget_covers_the_report(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tasks_tools, "PER_LIST_TIMEOUT", 0.05)
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"))

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return store.report(request)

    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        # the same pattern again replaces the REPORT route of the store
        mock.route(method="REPORT", url=task_store.list_url(OWN)).mock(side_effect=slow)
        with pytest.raises(ToolError) as caught:
            await run(clients, listed(OWN))
    assert "list did not answer in time" in caught.value.message
    assert store.writes == []


def test_no_write_runs_under_a_time_budget_or_side_by_side() -> None:
    source = Path(inspect.getfile(tasks_tools)).read_text(encoding="utf-8")
    body = source[source.index("async def run_chain(") :]
    end = body.find("\n\n\n")
    body = body if end < 0 else body[:end]
    assert "await write(" in body
    assert "return report" in body
    assert "timeout" not in body
    assert "gather" not in body
    assert "create_task" not in body


@pytest.mark.anyio
async def test_descendants_first_then_the_named_task_each_with_its_own_etag(
    clients: NcClients,
) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("k1", "root"), ("e1", "k1"), ("k2", "root"))
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert written(store) == ["e1.ics", "k1.ics", "k2.ics", "root.ics"]
    for _method, name, match in store.writes:
        assert match == before[name][1]
    assert report.changed == [tid(OWN, n) for n in ("e1.ics", "k1.ics", "k2.ics", "root.ics")]
    assert report.failed is None
    assert report.reason is None
    assert report.root_etag == store.etag("root.ics")
    for name in ("e1.ics", "k1.ics", "k2.ics", "root.ics"):
        assert "STATUS:COMPLETED" in store.text(name)
    answer = report.as_answer()
    assert "failed" not in answer
    assert "message" not in answer


@pytest.mark.anyio
async def test_only_the_named_task_carries_the_etag_of_the_assistant(
    clients: NcClients,
) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"))
    read = store.etag("a.ics")
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN), root_etag='"what-the-assistant-read"')
    assert store.writes == [
        ("PUT", "a.ics", read),
        ("PUT", "root.ics", '"what-the-assistant-read"'),
    ]
    # the assistant read an older state: the named task stays, the subtask is reported
    assert report.changed == [tid(OWN, "a.ics")]
    assert report.failed == tid(OWN, "root.ics")
    assert report.reason == "conflict"
    assert "STATUS:COMPLETED" not in store.text("root.ics")


@pytest.mark.anyio
async def test_descendants_in_the_target_state_are_skipped_without_a_call(
    clients: NcClients,
) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), ("b", "root"), extra={"a": "STATUS:COMPLETED"})
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert written(store) == ["b.ics", "root.ics"]
    assert report.unchanged == 1
    assert report.changed == [tid(OWN, "b.ics"), tid(OWN, "root.ics")]
    assert report.as_answer()["unchanged"] == 1


@pytest.mark.anyio
async def test_a_descendant_marked_to_be_left_alone_gets_no_call(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), ("b", "root"), extra={"a": "STATUS:CANCELLED"})
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert written(store) == ["b.ics", "root.ics"]
    assert report.left_alone == [tid(OWN, "a.ics")]
    assert store.snapshot()["a.ics"] == before["a.ics"]
    assert report.as_answer()["left_alone"] == [tid(OWN, "a.ics")]


@pytest.mark.anyio
async def test_a_named_task_in_the_target_state_gets_no_call(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), extra={"root": "STATUS:COMPLETED"})
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert written(store) == ["a.ics"]
    assert report.changed == [tid(OWN, "a.ics")]
    assert report.unchanged == 1
    assert report.root_etag is None


STOPS = [
    (412, "conflict"),
    (404, "not_found_or_read_only"),
    (403, "refused"),
    (500, "server_error"),
    (503, "server_error"),
    (httpx.ReadTimeout("slow"), "outcome_unknown"),
    (httpx.ConnectError("gone"), "outcome_unknown"),
]


@pytest.mark.parametrize(
    ("planted", "reason"),
    STOPS,
    ids=["412", "404", "403", "500", "503", "timeout", "connect"],
)
@pytest.mark.anyio
async def test_the_first_failure_stops_the_chain_and_keeps_the_named_task(
    clients: NcClients, planted: int | Exception, reason: str
) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), ("b", "root"), ("c", "root"))
    store.fail["b.ics"] = planted
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    # no further request after the failure, no second attempt, nothing undone
    assert written(store) == ["a.ics", "b.ics"]
    assert store.snapshot()["root.ics"] == before["root.ics"]
    assert store.snapshot()["c.ics"] == before["c.ics"]
    assert "STATUS:COMPLETED" in store.text("a.ics")
    assert report.changed == [tid(OWN, "a.ics")]
    assert report.failed == tid(OWN, "b.ics")
    assert report.reason == reason
    answer = report.as_answer()
    assert answer["changed"] == [tid(OWN, "a.ics")]
    assert answer["failed"] == tid(OWN, "b.ics")
    assert answer["reason"] == reason
    assert "tasks_read" in answer["message"]
    assert f"{tid(OWN, 'root.ics')} was not changed" in answer["message"]


MOVE_STOPS = [
    (409, "uid_conflict"),
    (412, "conflict"),
    (404, "not_found_or_read_only"),
    (403, "refused"),
    (502, "server_error"),
    (httpx.ReadTimeout("slow"), "outcome_unknown"),
]


@pytest.mark.parametrize(
    ("planted", "reason"), MOVE_STOPS, ids=["409", "412", "404", "403", "502", "timeout"]
)
@pytest.mark.anyio
async def test_a_relocation_chain_stops_at_the_first_failure_as_well(
    clients: NcClients, planted: int | Exception, reason: str
) -> None:
    source, target = task_store.TaskStore(OWN), task_store.TaskStore("ziel")
    tree(source, ("a", "root"), ("b", "root"))
    source.fail["b.ics"] = planted
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, source, target)
        report = await run(
            clients,
            listed(OWN),
            decide=relocate,
            write=move_writer(clients, listed(OWN), listed("ziel", "Ziel")),
        )
    assert [(method, name) for method, name, _e in source.writes] == [
        ("MOVE", "a.ics"),
        ("MOVE", "b.ics"),
    ]
    assert set(target.objects) == {"a.ics"}
    assert "root.ics" in source.objects
    assert report.changed == [tid(OWN, "a.ics")]
    assert report.failed == tid(OWN, "b.ics")
    assert report.reason == reason


@pytest.mark.anyio
async def test_a_relocation_chain_relocates_the_named_task_last(clients: NcClients) -> None:
    source, target = task_store.TaskStore(OWN), task_store.TaskStore("ziel")
    tree(source, ("a", "root"), ("b", "a"))
    before = source.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, source, target)
        report = await run(
            clients,
            listed(OWN),
            decide=relocate,
            write=move_writer(clients, listed(OWN), listed("ziel", "Ziel")),
        )
    assert written(source) == ["b.ics", "a.ics", "root.ics"]
    for _method, name, match in source.writes:
        assert match == before[name][1]
    assert set(target.objects) == {"a.ics", "b.ics", "root.ics"}
    assert source.objects == {}
    assert report.failed is None


@pytest.mark.anyio
async def test_an_edit_refused_on_the_way_stops_without_a_request(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), ("b", "root"))

    def picky(entry: dict[str, Any]) -> bytes | tasks_tools.ChainSkip:
        if entry["uid"] == "b":
            raise ics_edit.EditRefused("field DUE appears more than once")
        return complete(entry)

    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN), decide=picky)
    assert written(store) == ["a.ics"]
    assert report.failed == tid(OWN, "b.ics")
    assert report.reason == "refused"


@pytest.mark.anyio
async def test_writes_never_overlap(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, *((f"k{i:02d}", "root") for i in range(12)))
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert len(store.writes) == 13
    assert store.max_open == 1
    assert report.failed is None


@pytest.mark.anyio
async def test_the_overlap_counter_sees_parallel_writes(clients: NcClients) -> None:
    """Positive control: the same counter reports overlapping writes when they happen."""
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"), ("b", "root"))
    task = listed(OWN)
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        await asyncio.gather(
            *(
                tasks_client.put_existing_todo(
                    clients.client,
                    clients.creds,
                    task,
                    name,
                    store.objects[name][0],
                    store.etag(name),
                )
                for name in ("a.ics", "b.ics")
            )
        )
    assert store.max_open == 2


@pytest.mark.anyio
async def test_the_report_names_ids_and_the_list_but_never_uri_or_owner(
    clients: NcClients,
) -> None:
    store = task_store.TaskStore(SHARED)
    tree(store, ("a", "root"), ("b", "root"))
    store.fail["b.ics"] = 412
    shared = tasks_client.TaskList(
        uri=SHARED, key=ids.task_list_key(SHARED), name="Einkauf", shared=True, writable=True
    )
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, shared)
    answer = report.as_answer()
    text = json.dumps(answer)
    for leak in LEAKS:
        assert leak not in text, leak
    assert answer["list"] == {"name": "Einkauf", "shared": True, "writable": True}


@pytest.mark.anyio
async def test_the_report_counts_skipped_objects(clients: NcClients) -> None:
    store = task_store.TaskStore(OWN)
    tree(store, ("a", "root"))
    store.add("broken.ics", "not ical")
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    assert report.as_answer()["skipped"] == 1


@pytest.mark.anyio
async def test_the_size_of_a_full_chain_report(
    clients: NcClients, capsys: pytest.CaptureFixture[str]
) -> None:
    store = task_store.TaskStore(OWN)
    names = [str(uuid.UUID(int=i + 1)) for i in range(tasks_tools.CHAIN_CAP)]
    tree(store, *((name, "root") for name in names))
    store.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        task_store.mount(mock, store)
        report = await run(clients, listed(OWN))
    answer = report.as_answer()
    assert len(answer["changed"]) == tasks_tools.CHAIN_CAP
    size = len(json.dumps(answer, ensure_ascii=False).encode("utf-8"))
    with capsys.disabled():
        print(f"\nMESSWERT kettenbericht_bytes={size} ids={tasks_tools.CHAIN_CAP}")
    assert size < 8000
