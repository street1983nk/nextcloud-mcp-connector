"""Unit tests for the task chain of ``tools/tasks.py`` (plan 33-05), every path without a network.

Pinned here: the descendants of a task (children, grandchildren, ...) in post-order, found
with an exact UID match over ``RELATED-TO`` without ``RELTYPE`` or with ``RELTYPE=PARENT``
only, safe against cycles and double edges, siblings ordered by object name (D-33-09); the
check before the first write (more than ``CHAIN_CAP`` descendants, a recurring descendant or
one with several VTODO, a read only list), which never sends a request (D-33-10, D-33-11).
"""

import inspect
import re
from pathlib import Path
from typing import Any

import pytest
import respx

from mcp_connector import ids
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError
from mcp_connector.nextcloud.clients import tasks as tasks_client
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
