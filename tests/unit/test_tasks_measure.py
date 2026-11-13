"""Unit tests for the pure helpers of ``scripts/tasks_measure.py`` (plan 32-02).

The script is not a package module, so it is loaded from its file path, the same way
``tests/unit/test_tasks_spike.py`` loads the measuring script of phase 30. Nothing here
talks to a network or to Docker. Pinned down are only the helpers whose mistakes would
silently falsify a measurement: a query body that is not the one the protocol names, a
name rule that cuts too much or too little, a budget off the rule of the spike, and an app
state read as "missing" from an answer that says nothing.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from lxml import etree

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tasks_measure.py"

CAL = "urn:ietf:params:xml:ns:caldav"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks_measure", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tasks_measure"] = module
    spec.loader.exec_module(module)
    return module


measure = _load()


def _text_match(body: bytes, prop: str) -> etree._Element:
    root = etree.fromstring(body)
    assert etree.QName(root).localname == "calendar-query"
    outer = root.find(f"{{{CAL}}}filter/{{{CAL}}}comp-filter")
    assert outer is not None
    assert outer.get("name") == "VCALENDAR"
    todo = outer.find(f"{{{CAL}}}comp-filter")
    assert todo is not None
    assert todo.get("name") == "VTODO"
    filters = todo.findall(f"{{{CAL}}}prop-filter")
    assert [element.get("name") for element in filters] == [prop]
    match = filters[0].find(f"{{{CAL}}}text-match")
    assert match is not None
    return match


# --- children_filter ---------------------------------------------------------------------------


def test_children_filter_without_collation_is_the_form_the_spike_measured() -> None:
    match = _text_match(measure.children_filter("p-uid-1", None), "RELATED-TO")
    assert match.text == "p-uid-1"
    assert match.get("match-type") == "contains"
    assert "collation" not in match.attrib


def test_children_filter_with_octet_sets_the_collation_attribute() -> None:
    match = _text_match(measure.children_filter("p-uid-1", "i;octet"), "RELATED-TO")
    assert match.get("collation") == "i;octet"
    assert match.get("match-type") == "contains"
    assert match.text == "p-uid-1"


def test_children_filter_escapes_markup_in_the_uid() -> None:
    uid = 'a<b&c"d'
    body = measure.children_filter(uid, "i;octet")
    assert b"<b&c" not in body
    assert _text_match(body, "RELATED-TO").text == uid


def test_children_filter_asks_for_etag_and_calendar_data() -> None:
    root = etree.fromstring(measure.children_filter("x", None))
    prop = root.find("{DAV:}prop")
    assert prop is not None
    names = [etree.QName(child).localname for child in prop]
    assert names == ["getetag", "calendar-data"]


def test_children_filter_refuses_an_empty_uid() -> None:
    with pytest.raises(ValueError, match="needs a value"):
        measure.children_filter("", None)


# --- uid_filter --------------------------------------------------------------------------------


def test_uid_filter_matches_on_the_uid_property() -> None:
    match = _text_match(measure.uid_filter("p-uid-2", None), "UID")
    assert match.text == "p-uid-2"
    assert "collation" not in match.attrib


def test_uid_filter_with_octet() -> None:
    match = _text_match(measure.uid_filter('q"&<', "i;octet"), "UID")
    assert match.get("collation") == "i;octet"
    assert match.text == 'q"&<'


# --- owner_suffix_strip ------------------------------------------------------------------------


def test_owner_suffix_strip_removes_exactly_the_owner_suffix() -> None:
    assert measure.owner_suffix_strip("Team tasks (Bob Example)", "Bob Example") == "Team tasks"


def test_owner_suffix_strip_is_none_when_the_suffix_is_another_name() -> None:
    assert measure.owner_suffix_strip("Team tasks (Carol)", "Bob Example") is None


def test_owner_suffix_strip_is_none_without_any_suffix() -> None:
    assert measure.owner_suffix_strip("Team tasks", "Bob Example") is None


def test_owner_suffix_strip_with_parentheses_in_the_owner_name() -> None:
    owner = "Bob (Ops)"
    assert measure.owner_suffix_strip("Plan (v2) (Bob (Ops))", owner) == "Plan (v2)"
    assert measure.owner_suffix_strip("Plan (Ops))", owner) is None


def test_owner_suffix_strip_keeps_brackets_that_belong_to_the_list_name() -> None:
    assert measure.owner_suffix_strip("Plan (v2) (bob)", "bob") == "Plan (v2)"


def test_owner_suffix_strip_refuses_an_empty_owner() -> None:
    assert measure.owner_suffix_strip("Team tasks ()", "") is None
    assert measure.owner_suffix_strip("Team tasks ()", "   ") is None


def test_owner_suffix_strip_refuses_a_name_that_is_only_the_suffix() -> None:
    assert measure.owner_suffix_strip(" (bob)", "bob") is None


# --- derive_budget -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "budget"),
    [(0.0, 1), (0.2, 1), (0.5, 1), (0.51, 2), (1.0, 2), (1.01, 3), (2.4, 5)],
)
def test_derive_budget_is_the_rule_of_the_spike(seconds: float, budget: int) -> None:
    assert measure.derive_budget(seconds) == budget


def test_derive_budget_agrees_with_the_proposal_of_the_spike() -> None:
    for seconds in (0.2, 0.75, 1.01, 3.3):
        text = measure.spike.proposal(0.5, seconds)
        assert f"Zeitbudget je Liste {measure.derive_budget(seconds)} s" in text


# --- navigation_lists --------------------------------------------------------------------------


def test_navigation_lists_finds_the_app_by_app_or_id() -> None:
    assert measure.navigation_lists([{"id": "files"}, {"app": "tasks", "id": "x"}], "tasks")
    assert measure.navigation_lists([{"id": "tasks"}], "tasks") is True


def test_navigation_lists_is_false_when_the_app_is_absent() -> None:
    assert measure.navigation_lists([{"id": "files", "app": "files"}], "tasks") is False


@pytest.mark.parametrize("payload", [None, [], {}, "tasks", 3, {"tasks": 1}])
def test_navigation_lists_is_none_for_an_answer_that_says_nothing(payload: object) -> None:
    assert measure.navigation_lists(payload, "tasks") is None


def test_navigation_lists_is_none_when_no_entry_is_an_object() -> None:
    assert measure.navigation_lists(["tasks", 1], "tasks") is None


# --- share_state (plan 32-09, D-32-18) ---------------------------------------------------------

_MS = (
    '<?xml version="1.0"?>'
    '<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" '
    'xmlns:cs="http://calendarserver.org/ns/">{}</d:multistatus>'
)
_OC_INVITE = "{http://owncloud.org/ns}invite"
_CS_INVITE = "{http://calendarserver.org/ns/}invite"
_SHARE_ACCESS = "{DAV:}share-access"
_PUBLISH_URL = "{http://calendarserver.org/ns/}publish-url"


def _response(href: str, ok: str = "", missing: str = "") -> str:
    found = f"<d:propstat><d:prop>{ok}</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
    gone = (
        f"<d:propstat><d:prop>{missing}</d:prop>"
        "<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat>"
        if missing
        else ""
    )
    return f"<d:response><d:href>{href}</d:href>{found}{gone}</d:response>"


def test_share_state_counts_the_sharees_of_an_invite_without_returning_them() -> None:
    ok = (
        "<oc:invite><oc:user><d:href>principal:principals/users/sharee</d:href>"
        "<oc:common-name>Sharee</oc:common-name><oc:access><oc:read-write/></oc:access>"
        "</oc:user></oc:invite>"
        "<d:share-access><d:shared-owner/></d:share-access>"
    )
    body = _MS.format(_response("/remote.php/dav/calendars/alice/p3209-aus/", ok)).encode()
    marks = measure.share_states(body)["p3209-aus"]
    assert marks[_OC_INVITE] == measure.ShareMark("2xx", True, 1)
    assert marks[_SHARE_ACCESS] == measure.ShareMark("2xx", True, 1)
    assert marks[_CS_INVITE] == measure.ShareMark("fehlt", False, 0)
    assert "sharee" not in repr(marks).casefold()


def test_share_state_reads_an_empty_invite_and_not_shared_as_empty() -> None:
    ok = "<oc:invite/><d:share-access><d:not-shared/></d:share-access>"
    body = _MS.format(_response("/remote.php/dav/calendars/alice/p3209-aus/", ok)).encode()
    marks = measure.share_states(body)["p3209-aus"]
    assert marks[_OC_INVITE] == measure.ShareMark("2xx", False, 0)
    assert marks[_SHARE_ACCESS] == measure.ShareMark("2xx", False, 0)


def test_share_state_names_a_404_propstat() -> None:
    body = _MS.format(
        _response("/remote.php/dav/calendars/alice/x/", "<oc:invite/>", "<cs:publish-url/>")
    ).encode()
    marks = measure.share_states(body)["x"]
    assert marks[_PUBLISH_URL] == measure.ShareMark("404", False, 0)


def test_share_state_counts_a_publish_url_by_its_href() -> None:
    ok = "<cs:publish-url><d:href>https://example.org/dav/public-calendars/T0K3N</d:href></cs:publish-url>"
    body = _MS.format(_response("/remote.php/dav/calendars/alice/x/", ok)).encode()
    marks = measure.share_states(body)["x"]
    assert marks[_PUBLISH_URL] == measure.ShareMark("2xx", True, 1)
    assert "T0K3N" not in repr(marks)


def test_share_line_is_only_marks_and_numbers() -> None:
    line = measure.share_line(
        "nc35", "an-bob-ro", "basic", _OC_INVITE, measure.ShareMark("2xx", True, 1)
    )
    assert line == (
        "HINAUS nc35 zustand=an-bob-ro auth=basic prop={http://owncloud.org/ns}invite "
        "status=2xx belegt=ja eintraege=1"
    )


# --- subline_form (plan 32-09, D-32-17) --------------------------------------------------------


def test_subline_form_of_a_shared_list_on_35() -> None:
    form = measure.subline_form(
        "Due on Nov 20, 2026 (Team (Bob Example))", "Team (Bob Example)", "Bob Example"
    )
    assert form == {
        "endet_mit_rohname": True,
        "enthaelt_besitzer": True,
        "bereinigt_moeglich": True,
    }


def test_subline_form_of_a_due_date_only_subline_on_32() -> None:
    form = measure.subline_form("Due on Nov 20, 2026", "Team (Bob Example)", "Bob Example")
    assert form == {
        "endet_mit_rohname": False,
        "enthaelt_besitzer": False,
        "bereinigt_moeglich": False,
    }


def test_subline_form_of_an_own_list_never_offers_a_cleaning() -> None:
    form = measure.subline_form("Due soon (p3209-eigen)", "p3209-eigen", "Bob Example")
    assert form["endet_mit_rohname"] is True
    assert form["enthaelt_besitzer"] is False
    assert form["bereinigt_moeglich"] is False


def test_subline_form_refuses_when_the_owner_stays_elsewhere() -> None:
    form = measure.subline_form(
        "Bob Example: due (Team (Bob Example))", "Team (Bob Example)", "Bob Example"
    )
    assert form["bereinigt_moeglich"] is False


# --- group shares, recurring forms and the cap (plan 32-10) ------------------------------------

_OC = "http://owncloud.org/ns"


def test_group_share_body_names_the_group_principal_and_the_write_right() -> None:
    root = etree.fromstring(measure.group_share_body("testgroup", writable=True))
    assert etree.QName(root).localname == "share"
    entry = root.find(f"{{{_OC}}}set")
    assert entry is not None
    assert entry.findtext("{DAV:}href") == "principal:principals/groups/testgroup"
    assert entry.find(f"{{{_OC}}}read-write") is not None


def test_group_share_body_read_only_has_no_write_right() -> None:
    root = etree.fromstring(measure.group_share_body("testgroup", writable=False))
    entry = root.find(f"{{{_OC}}}set")
    assert entry is not None
    assert entry.find(f"{{{_OC}}}read-write") is None


def test_group_share_body_remove_takes_the_share_back() -> None:
    root = etree.fromstring(measure.group_share_body("testgroup", writable=False, remove=True))
    assert root.find(f"{{{_OC}}}set") is None
    entry = root.find(f"{{{_OC}}}remove")
    assert entry is not None
    assert entry.findtext("{DAV:}href") == "principal:principals/groups/testgroup"


def _invite(inner: str) -> etree._Element:
    return etree.fromstring(f'<oc:invite xmlns:oc="{_OC}" xmlns:d="DAV:">{inner}</oc:invite>')


def test_invite_shape_of_a_group_entry_counts_without_returning_it() -> None:
    shape = measure.invite_shape(
        _invite(
            "<oc:user><d:href>principal:principals/groups/testgroup</d:href>"
            "<oc:common-name>testgroup</oc:common-name><oc:access><oc:read/></oc:access>"
            "</oc:user>"
        )
    )
    assert shape == measure.InviteShape(entries=1, children=("user",), kinds="groups")
    assert "testgroup" not in repr(shape)


def test_invite_shape_of_a_user_and_a_group() -> None:
    shape = measure.invite_shape(
        _invite(
            "<oc:user><d:href>principal:principals/users/sharee</d:href></oc:user>"
            "<oc:group><d:href>principal:principals/groups/testgroup</d:href></oc:group>"
        )
    )
    assert shape.entries == 2
    assert shape.children == ("group", "user")
    assert shape.kinds == "groups+users"


def test_invite_shape_of_an_empty_invite_and_of_an_unknown_principal() -> None:
    assert measure.invite_shape(_invite("")) == measure.InviteShape(0, (), "keine")
    other = measure.invite_shape(
        _invite("<oc:user><d:href>principal:principals/system/public</d:href></oc:user>")
    )
    assert other.kinds == "andere"


def _unfolded(text: str) -> list[str]:
    return text.replace("\r\n ", "").split("\r\n")


def test_recurring_todo_app_form_is_the_template_with_uid_and_summary() -> None:
    text = measure.recurring_todo("p3210-w-1", "p3210 wieder app", "app")
    lines = _unfolded(text)
    assert "UID:p3210-w-1" in lines
    assert "SUMMARY:p3210 wieder app" in lines
    assert "RRULE:FREQ=DAILY" in lines
    assert "DUE:20261120T130000Z" in lines
    assert lines.count("BEGIN:VTODO") == 1
    assert "s30 wiederkehrend" not in text
    assert not any(line.startswith("STATUS:") for line in lines)


def test_recurring_todo_completed_instance_is_an_override_in_the_same_object() -> None:
    text = measure.recurring_todo("p3210-w-2", "p3210 wieder instanz", "instanz-erledigt")
    lines = _unfolded(text)
    assert lines.count("BEGIN:VTODO") == 2
    assert lines.count("UID:p3210-w-2") == 2
    assert "RECURRENCE-ID:20261121T130000Z" in lines
    assert "STATUS:COMPLETED" in lines
    assert "PERCENT-COMPLETE:100" in lines
    assert any(line.startswith("COMPLETED:") for line in lines)
    master = text.split("END:VTODO", 1)[0]
    assert "RRULE:FREQ=DAILY" in master
    assert "STATUS:" not in master
    assert "COMPLETED:" not in master


def test_recurring_todo_completed_master_carries_the_rule_and_the_status() -> None:
    text = measure.recurring_todo("p3210-w-3", "p3210 wieder master", "master-erledigt")
    lines = _unfolded(text)
    assert lines.count("BEGIN:VTODO") == 1
    assert "RRULE:FREQ=DAILY" in lines
    assert "STATUS:COMPLETED" in lines
    assert "PERCENT-COMPLETE:100" in lines
    assert not any(line.startswith("RECURRENCE-ID") for line in lines)


def test_recurring_todo_refuses_an_unknown_form() -> None:
    with pytest.raises(ValueError, match="unknown recurring form"):
        measure.recurring_todo("u", "s", "anders")


def _page(ids: list[str], **extra: object) -> dict[str, object]:
    return {"tasks": [{"id": i} for i in ids], **extra}


def test_paging_summary_of_a_capped_walk() -> None:
    pages = [_page([f"t{p}-{i}" for i in range(25)], truncated=True, next="c") for p in range(19)]
    pages.append(_page([f"t19-{i}" for i in range(25)], truncated=True, note="capped"))
    summary = measure.paging_summary(pages)
    assert summary == measure.PagingSummary(
        pages=20,
        per_page=25,
        hits=500,
        unique=500,
        last_note=True,
        last_next=False,
        degraded=False,
    )


def test_paging_summary_counts_duplicates_and_degraded_pages() -> None:
    pages = [
        _page(["a", "b"], next="c"),
        _page(["b"], degraded=[{"list": "x", "reason": "slow"}]),
    ]
    summary = measure.paging_summary(pages)
    assert summary.pages == 2
    assert summary.per_page == 2
    assert summary.hits == 3
    assert summary.unique == 2
    assert summary.last_note is False
    assert summary.last_next is False
    assert summary.degraded is True


def test_paging_summary_of_no_page() -> None:
    summary = measure.paging_summary([])
    assert summary.pages == 0
    assert summary.hits == 0
    assert summary.last_note is False
