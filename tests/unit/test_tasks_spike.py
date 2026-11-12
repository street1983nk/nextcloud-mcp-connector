"""Unit tests for the pure helpers of ``scripts/tasks_spike.py`` (phase 30).

The script is not a package module, so it is loaded from its file path. Nothing here talks
to a network or to Docker: the measuring blocks run against the live nc35 topology from the
script itself. Pinned down here are only the helpers whose mistakes would silently falsify
a measurement: a refusal counted although the folder exists, an abort criterion that lets a
403 pass, a RAM gate that starts next to a foreign Nextcloud, a secret written into a
protocol, a quoted raw value that stands in no raw file.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tasks_spike.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks_spike", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tasks_spike"] = module
    spec.loader.exec_module(module)
    return module


spike = _load()


# --- the status matrix --------------------------------------------------------------------


def test_mkcol_expectations_name_the_fourteen_rows_in_order_with_the_researched_status() -> None:
    assert spike.mkcol_expectations() == {
        "frei": 201,
        "ordner-vorhanden": 405,
        "datei-vorhanden": 405,
        "eltern-fehlt": 409,
        "eltern-ist-datei": 409,
        "name-htaccess": 400,
        "name-backslash": 400,
        "name-ueberlang": 400,
        "share-ro": 403,
        "share-rw": 201,
        "root-vorhanden": 201,
        "root-fehlt": 409,
        "root-selbst": 405,
        "quota": 201,
    }
    assert list(spike.mkcol_expectations()) == [
        "frei",
        "ordner-vorhanden",
        "datei-vorhanden",
        "eltern-fehlt",
        "eltern-ist-datei",
        "name-htaccess",
        "name-backslash",
        "name-ueberlang",
        "share-ro",
        "share-rw",
        "root-vorhanden",
        "root-fehlt",
        "root-selbst",
        "quota",
    ]


def test_mkcol_keys_are_exactly_the_keys_of_the_expectations_in_their_order() -> None:
    assert tuple(spike.mkcol_expectations()) == spike.MKCOL_KEYS
    assert len(spike.MKCOL_KEYS) == 14


def test_gf_keys_are_the_five_group_folder_rows_in_order() -> None:
    assert spike.GF_KEYS == (
        "acl-rw",
        "acl-ro",
        "acl-ro-kontrolle-b",
        "acl-ro-nach-regelentzug",
        "gruppe-nur-lesen",
    )


def test_only_a_201_keeps_the_abort_criterion_of_mess_01_silent() -> None:
    assert spike.abort_mess01(201) is False
    assert spike.abort_mess01(403) is True
    assert spike.abort_mess01(405) is True
    assert spike.abort_mess01(0) is True


def test_refused_needs_a_status_outside_2xx_and_nothing_created() -> None:
    assert spike.refused(403, created=False) is True
    assert spike.refused(201, created=True) is False


def test_a_refusal_with_a_created_folder_is_a_contradiction_and_never_counted() -> None:
    with pytest.raises(ValueError, match="contradiction"):
        spike.refused(403, created=True)


def test_same_status_names_every_row_that_differs() -> None:
    left = {"frei": 201, "share-ro": 403}
    assert spike.same_status(left, {"frei": 201, "share-ro": 403}) == (True, [])
    assert spike.same_status(left, {"frei": 201, "share-ro": 404}) == (False, ["share-ro"])
    assert spike.same_status(left, {"frei": 201}) == (False, ["share-ro"])


# --- describe_error -----------------------------------------------------------------------

_ERROR_BODY = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b'<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">\n'
    b"  <s:exception>Sabre\\DAV\\Exception\\MethodNotAllowed</s:exception>\n"
    b"  <s:message>The resource you tried to create already exists</s:message>\n"
    b"</d:error>\n"
)


def test_describe_error_reads_exception_and_message_of_a_sabre_error_body() -> None:
    assert spike.describe_error(_ERROR_BODY) == (
        "Sabre\\DAV\\Exception\\MethodNotAllowed The resource you tried to create already exists"
    )


@pytest.mark.parametrize("body", [b"", b"   \n"])
def test_describe_error_of_an_empty_body_is_an_empty_string(body: bytes) -> None:
    assert spike.describe_error(body) == ""


def test_describe_error_of_something_that_is_no_xml_says_so() -> None:
    assert spike.describe_error(b"<html><body>login") == "(not XML)"


# --- the RAM gate -------------------------------------------------------------------------


def test_free_host_memory_is_read_from_kib() -> None:
    assert spike.free_host_memory_gb("5300000\n") == pytest.approx(5.05)
    assert spike.free_host_memory_gb("MemTotal: 1 kB\nMemAvailable:    5300000 kB\n") == (
        pytest.approx(5.05)
    )


def test_free_host_memory_of_an_unreadable_probe_is_zero_so_the_gate_stays_shut() -> None:
    assert spike.free_host_memory_gb("") == 0.0
    assert spike.free_host_memory_gb("access denied") == 0.0


def test_ram_gate_needs_four_gb_and_no_foreign_run() -> None:
    assert spike.ram_gate_ok(5.05, foreign=[]) is True
    assert spike.ram_gate_ok(3.9, foreign=[]) is False
    assert spike.ram_gate_ok(5.05, foreign=["nc-spike-tags"]) is False


def test_foreign_runs_reports_a_foreign_nextcloud_and_skips_own_containers() -> None:
    lines = ["nc35-nc", "gameworld-dev-app-1 nextcloud:34.0.3-apache 0.5%"]
    assert spike.foreign_runs(lines, own={"nc35-nc"}) == [
        "gameworld-dev-app-1 nextcloud:34.0.3-apache 0.5%"
    ]


def test_foreign_runs_only_lists_a_quiet_helper_container() -> None:
    lines = [
        "nc35-nc nextcloud:35.0.0-apache-local 55.0%",
        "gameworld-dev-gameworld-docker-proxy-1 tecnativa/docker-socket-proxy:v0.5.0 0.02%",
    ]
    assert spike.foreign_runs(lines, own={"nc35-nc"}) == []


@pytest.mark.parametrize(
    "line",
    [
        "some-db postgres:17 0.1%",
        "other mariadb:11 0.0%",
        "nc_app_mcp_connector_park34 127.0.0.1:5000/mcp_connector:0.1.11 0.0%",
        "builder alpine:3 42.5%",
    ],
)
def test_foreign_runs_reports_databases_the_connector_image_and_busy_containers(line: str) -> None:
    assert spike.foreign_runs([line], own={"nc35-nc"}) == [line]


# --- secrets ------------------------------------------------------------------------------


def test_scan_for_secrets_names_every_hit_by_name_and_line_never_by_value() -> None:
    texts = {"protocol": "clean line\nvalue s3cr3t-value here\nAUTHORIZATION-APP-API: abc\n"}
    hits = spike.scan_for_secrets(texts, {"APP_SECRET": "s3cr3t-value", "EMPTY": ""})
    assert hits == ["protocol:2: APP_SECRET", "protocol:3: AUTHORIZATION-APP-API"]
    assert all("s3cr3t-value" not in hit for hit in hits)


def test_scan_for_secrets_ignores_empty_values() -> None:
    assert spike.scan_for_secrets({"p": "a line\n\n"}, {"A": "", "B": "   "}) == []


def test_raw_answer_never_carries_an_authorization_or_cookie_header() -> None:
    headers = [
        ("Content-Type", "application/xml"),
        ("Authorization", "Basic abc"),
        ("AUTHORIZATION-APP-API", "abc"),
        ("Set-Cookie", "oc_sessionPassphrase=abc"),
    ]
    lines = spike.raw_answer(405, "Method Not Allowed", headers, b"<d:error/>")
    text = "\n".join(lines)
    assert "HTTP 405 Method Not Allowed" in text
    assert "Content-Type: application/xml" in text
    assert "abc" not in text
    assert "<d:error/>" in text


# --- quotes of the report -----------------------------------------------------------------

_REPORT = """# Titel

## 1. MKCOL

`nicht im Abschnitt Rohausgaben`

## 12. Rohausgaben

### 12.1 raw/nc35-mkcol.txt

Die Zeile `MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201` steht dort.

```
HTTP 201 Created
  Content-Length: 0
```

## 13. Danach

`auch nicht`
"""


def test_quoted_lines_reads_the_backtick_quotes_and_fenced_lines_of_the_raw_section() -> None:
    assert spike.quoted_lines(_REPORT) == [
        "MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201",
        "HTTP 201 Created",
        "Content-Length: 0",
    ]


def test_missing_quotes_names_what_stands_in_no_raw_file() -> None:
    raw = {
        "raw/nc35-mkcol.txt": (
            "2026 | MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201 | \n"
            "    HTTP 201 Created\n"
        )
    }
    assert spike.missing_quotes(_REPORT, raw) == ["Content-Length: 0"]
    raw["raw/zwei.txt"] = "      Content-Length: 0\n"
    assert spike.missing_quotes(_REPORT, raw) == []


# --- plan 30-02: modifying access -----------------------------------------------------------

_LONG = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor"

_TODO = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//test//EN\r\n"
    "BEGIN:VTODO\r\n"
    "UID:u1\r\n"
    "SUMMARY:" + _LONG[:66] + "\r\n " + _LONG[66:] + "\r\n"
    "X-SPIKE30-FOO:bar\r\n"
    "BEGIN:VALARM\r\n"
    "ACTION:DISPLAY\r\n"
    "TRIGGER:-PT15M\r\n"
    "END:VALARM\r\n"
    "\r\n"
    "END:VTODO\r\n"
    "END:VCALENDAR\r\n"
)
_FOLDED_SUMMARY = "SUMMARY:" + _LONG[:66] + "\r\n " + _LONG[66:]


def test_ics_line_set_unfolds_a_folded_summary_into_one_line_per_component() -> None:
    lines = spike.ics_line_set(_TODO)
    summaries = [line for path, line in lines if line.startswith("SUMMARY")]
    assert summaries == [f"SUMMARY:{_LONG}"]
    assert ("VCALENDAR/VTODO", "X-SPIKE30-FOO:bar") in lines
    assert ("VCALENDAR/VTODO/VALARM", "TRIGGER:-PT15M") in lines
    assert ("VCALENDAR", "VERSION:2.0") in lines
    assert not any(line == "" for _, line in lines)


def test_ics_line_set_unfolds_a_tab_continuation_and_bare_line_feeds() -> None:
    text = "BEGIN:VCALENDAR\nBEGIN:VTODO\nSUMMARY:ab\n\tcd\nEND:VTODO\nEND:VCALENDAR\n"
    assert ("VCALENDAR/VTODO", "SUMMARY:abcd") in spike.ics_line_set(text)


def test_ics_line_set_counts_components_so_a_lost_second_alarm_shows() -> None:
    twice = _TODO.replace(
        "END:VTODO", "BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT15M\r\nEND:VALARM\r\nEND:VTODO"
    )
    added, removed, changed = spike.line_diff(twice, _TODO)
    assert (added, removed) == ([], [])
    assert changed == {"VALARM.BEGIN"}


def test_line_diff_names_a_changed_summary_and_nothing_else() -> None:
    after = _TODO.replace(_FOLDED_SUMMARY, "SUMMARY:neu")
    added, removed, changed = spike.line_diff(_TODO, after)
    assert changed == {"SUMMARY"}
    assert added == []
    assert removed == []


def test_line_diff_names_added_and_removed_lines_with_their_component() -> None:
    after = _TODO.replace("X-SPIKE30-FOO:bar\r\n", "STATUS:COMPLETED\r\n")
    added, removed, changed = spike.line_diff(_TODO, after)
    assert added == ["VCALENDAR/VTODO:STATUS:COMPLETED"]
    assert removed == ["VCALENDAR/VTODO:X-SPIKE30-FOO:bar"]
    assert changed == set()


def test_preserved_is_true_when_only_the_allowed_property_differs() -> None:
    after = _TODO.replace(_FOLDED_SUMMARY, "SUMMARY:neu")
    assert spike.preserved(_TODO, after, allowed={"SUMMARY"}) == (True, [])
    assert spike.preserved(_TODO, _TODO) == (True, [])


def test_preserved_names_a_lost_x_line() -> None:
    after = _TODO.replace("X-SPIKE30-FOO:bar\r\n", "").replace(_LONG[:66], "neu")
    ok, lost = spike.preserved(_TODO, after, allowed={"SUMMARY"})
    assert ok is False
    assert lost == ["entfernt VCALENDAR/VTODO:X-SPIKE30-FOO:bar"]


def test_preserved_names_a_changed_and_an_added_line_that_are_not_allowed() -> None:
    after = _TODO.replace("TRIGGER:-PT15M", "TRIGGER:-PT30M").replace(
        "UID:u1\r\n", "UID:u1\r\nSEQUENCE:1\r\n"
    )
    ok, lost = spike.preserved(_TODO, after, allowed={"SUMMARY"})
    assert ok is False
    assert lost == ["hinzu VCALENDAR/VTODO:SEQUENCE:1", "geaendert VALARM.TRIGGER"]


def test_abort_if_match_is_not_triggered_only_by_the_expected_four_values() -> None:
    aborted, reason = spike.abort_if_match(
        status_current=204, etag_changed=True, status_stale=412, unchanged_after_stale=True
    )
    assert aborted is False
    assert reason == "keiner"


@pytest.mark.parametrize(
    ("values", "word"),
    [
        ((403, True, 412, True), "aktuelle"),
        ((204, False, 412, True), "ETag"),
        ((204, True, 204, True), "veraltete"),
        ((204, True, 409, True), "veraltete"),
        ((204, True, 412, False), "veraendert"),
    ],
)
def test_abort_if_match_is_triggered_by_every_single_deviation(
    values: tuple[int, bool, int, bool], word: str
) -> None:
    aborted, reason = spike.abort_if_match(
        status_current=values[0],
        etag_changed=values[1],
        status_stale=values[2],
        unchanged_after_stale=values[3],
    )
    assert aborted is True
    assert word in reason


def test_value_form_tells_utc_floating_date_and_tzid_apart() -> None:
    assert spike.value_form("20261120T101500Z") == "utc"
    assert spike.value_form("20261120T101500") == "floating"
    assert spike.value_form("20261120") == "date"
    assert spike.value_form("DUE;TZID=Europe/Berlin:20261120T101500") == "tzid"
    assert spike.value_form("COMPLETED:20261120T101500Z") == "utc"
    assert spike.value_form("DUE;VALUE=DATE:20261120") == "date"
    assert spike.value_form("morgen") == "other"


def test_build_probe_todo_carries_everything_a_modifying_put_must_keep() -> None:
    text = spike.build_probe_todo("uid-1", "s30 eigenschaften")
    for wanted in (
        "BEGIN:VTIMEZONE",
        "BEGIN:VALARM",
        "X-SPIKE30-FOO",
        "X-APPLE-SORT-ORDER",
        "X-OC-HIDESUBTASKS",
        "CLASS:",
        "UID:uid-1",
    ):
        assert wanted in text
    assert text.endswith("\r\n")
    assert text.count("BEGIN:VTODO") == 1
    assert "\n" not in text.replace("\r\n", "")
    lines = spike.ics_line_set(text)
    summary = [line for _, line in lines if line.startswith("SUMMARY")]
    assert summary == ["SUMMARY;X-SPIKE30-PARAM=abc:s30 eigenschaften"]
    categories = [line for _, line in lines if line.startswith("CATEGORIES")]
    assert categories == ["CATEGORIES:spike30,wichtig"]
    description = [line for _, line in lines if line.startswith("DESCRIPTION") and len(line) > 75]
    assert len(description) == 1
    assert all(len(raw.encode()) <= 75 for raw in text.split("\r\n"))


def test_set_summary_changes_exactly_the_summary_line_and_keeps_its_parameters() -> None:
    text = spike.build_probe_todo("uid-1", "alt")
    changed = spike.set_summary(text, "neu")
    assert "SUMMARY;X-SPIKE30-PARAM=abc:neu\r\n" in changed
    assert spike.line_diff(text, changed) == ([], [], {"SUMMARY"})


def test_complete_todo_adds_the_three_lines_of_checking_off_before_the_end() -> None:
    text = spike.simple_todo("uid-2", "s30 x", ["RRULE:FREQ=DAILY"])
    done = spike.complete_todo(text, "20261111T120000Z")
    added, removed, changed = spike.line_diff(text, done)
    assert added == [
        "VCALENDAR/VTODO:COMPLETED:20261111T120000Z",
        "VCALENDAR/VTODO:PERCENT-COMPLETE:100",
        "VCALENDAR/VTODO:STATUS:COMPLETED",
    ]
    assert (removed, changed) == ([], set())
    assert "RRULE:FREQ=DAILY\r\n" in done
    assert done.endswith("END:VTODO\r\nEND:VCALENDAR\r\n")


def test_short_etag_drops_quotes_and_the_weak_marker() -> None:
    assert spike.short_etag('"0123456789abcdef0123"') == "0123456789ab"
    assert spike.short_etag('W/"0123456789abcdef0123"') == "0123456789ab"
    assert spike.short_etag("") == "-"
    assert spike.etag_kind('W/"x"') == "schwach"
    assert spike.etag_kind('"x"') == "stark"
    assert spike.etag_kind("") == "fehlt"


_HOME = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
 <d:response><d:href>/remote.php/dav/calendars/spike30ui/</d:href>
  <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
  <d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
 <d:response><d:href>/remote.php/dav/calendars/spike30ui/spike30-liste-1/</d:href>
  <d:propstat><d:prop><d:displayname>spike30-liste-1</d:displayname>
   <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
   <cal:supported-calendar-component-set><cal:comp name="VTODO"/>
   </cal:supported-calendar-component-set></d:prop>
  <d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
 <d:response><d:href>/remote.php/dav/calendars/spike30ui/x_shared_by_spike30b/</d:href>
  <d:propstat><d:prop><d:displayname>x</d:displayname>
   <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
   <cal:supported-calendar-component-set><cal:comp name="VEVENT"/><cal:comp name="VTODO"/>
   </cal:supported-calendar-component-set></d:prop>
  <d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
 <d:response><d:href>/remote.php/dav/calendars/spike30ui/inbox/</d:href>
  <d:propstat><d:prop><d:resourcetype><d:collection/><cal:schedule-inbox/></d:resourcetype>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
</d:multistatus>"""


def test_calendar_collections_keeps_calendars_with_name_and_components_only() -> None:
    assert spike.calendar_collections(_HOME) == [
        ("spike30-liste-1", "spike30-liste-1", ("VTODO",)),
        ("x_shared_by_spike30b", "x", ("VEVENT", "VTODO")),
    ]


def test_property_value_reads_from_the_unfolded_text() -> None:
    assert spike.property_value(_TODO, "SUMMARY") == _LONG
    assert spike.property_value(_TODO, "UID") == "u1"
    assert spike.property_value(_TODO, "DUE") == ""


def test_missing_names_reports_every_expected_summary_a_snapshot_lacks() -> None:
    seen = [name for name in spike.UI_EXPECTED if name != "s30 notiz"]
    assert spike.missing_names(seen) == ["s30 notiz"]
    assert spike.missing_names([*spike.UI_EXPECTED, "sonstiges"]) == []
    assert len(spike.UI_EXPECTED) == 14
    assert "s30 wiederkehrend" not in spike.UI_EXPECTED


def test_write_snapshot_keeps_two_states_apart_and_replaces_an_older_one(tmp_path: Path) -> None:
    state_a = [
        spike.SnapshotObject("liste-1", "a.ics", '"e1"', _TODO.encode(), False),
        spike.SnapshotObject("liste-1", "b.ics", '"e2"', _TODO.replace("u1", "u2").encode(), False),
    ]
    state_b = [
        spike.SnapshotObject("liste-2", "a.ics", '"e3"', _TODO.encode(), False),
        spike.SnapshotObject("trashbin", "7-deleted.ics", '"e4"', _TODO.encode(), True),
    ]
    assert spike.write_snapshot(tmp_path, "a", state_a) == ["a.ics", "b.ics"]
    assert spike.write_snapshot(tmp_path, "b", state_b) == ["a.ics", "trash-7-deleted.ics"]
    assert sorted(path.name for path in (tmp_path / "ui-a").iterdir()) == ["a.ics", "b.ics"]
    assert (tmp_path / "ui-a" / "a.ics").read_bytes() == _TODO.encode()
    # A second snapshot under the same label replaces the first, so no stale file survives.
    assert spike.write_snapshot(tmp_path, "a", state_a[:1]) == ["a.ics"]
    assert sorted(path.name for path in (tmp_path / "ui-a").iterdir()) == ["a.ics"]


def test_write_snapshot_tells_two_objects_of_the_same_name_apart(tmp_path: Path) -> None:
    twins = [
        spike.SnapshotObject("liste-1", "a.ics", '"e1"', b"x", False),
        spike.SnapshotObject("liste-2", "a.ics", '"e2"', b"y", False),
    ]
    assert spike.write_snapshot(tmp_path, "b", twins) == ["a.ics", "liste-2--a.ics"]


def test_read_ui_file_takes_user_password_and_base_url_from_three_lines(tmp_path: Path) -> None:
    path = tmp_path / "ui.txt"
    path.write_text("spike30ui\ngeheim\nhttp://127.0.0.1:8082\n", encoding="utf-8")
    assert spike.read_ui_file(path) == ("spike30ui", "geheim", "http://127.0.0.1:8082")
    path.write_text("spike30ui\n", encoding="utf-8")
    with pytest.raises(spike.RunFailed):
        spike.read_ui_file(path)


def test_baseline_from_protocol_takes_the_lines_of_the_last_controls_block() -> None:
    protocol = "\n".join(
        [
            "# Lauf blocks=controls",
            "",
            "== controls ==",
            "BASELINE-START nutzer=alt",
            "BASELINE-START gruppen=alt",
            "# Lauf blocks=controls,modify",
            "",
            "== controls ==",
            'BASELINE-START apps_an={"dav": "2.0.0"}',
            "BASELINE-START nutzer=- admin: admin - alice: alice",
            "BASELINE quota_alice vorher=x nachher=x gleich=ja",
            "",
            "== modify ==",
        ]
    )
    assert spike.baseline_from_protocol(protocol) == {
        "apps_an": '{"dav": "2.0.0"}',
        "nutzer": "- admin: admin - alice: alice",
    }
    assert spike.baseline_from_protocol("nichts") == {}


# --- plan 30-02 task 3: evaluation of the browser session and the inventory ------------------


def _todo(uid: str, summary: str, *extra: str, stamp: str = "20261111T125045Z") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nextcloud Tasks v0.18.1",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "CREATED:20261111T125045Z",
        f"LAST-MODIFIED:{stamp}",
        f"DTSTAMP:{stamp}",
        f"SUMMARY:{summary}",
        *extra,
        "END:VTODO",
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(lines)


def _states(tmp_path: Path) -> tuple[dict, dict]:
    done = ("PERCENT-COMPLETE:100", "COMPLETED:20261111T125947Z", "STATUS:COMPLETED")
    state_a = [
        spike.SnapshotObject("l1", "AAA.ics", '"1"', _todo("u-ab", "s30 abhaken").encode(), False),
        spike.SnapshotObject(
            "l1", "BBB.ics", '"2"', _todo("u-un", "s30 unberuehrt").encode(), False
        ),
        spike.SnapshotObject(
            "l1", "CCC.ics", '"3"', _todo("u-lo", "s30 eltern-loeschen").encode(), False
        ),
    ]
    state_b = [
        spike.SnapshotObject(
            "l1",
            "AAA.ics",
            '"4"',
            _todo("u-ab", "s30 abhaken", *done, stamp="20261111T125947Z").encode(),
            False,
        ),
        spike.SnapshotObject(
            "l2", "BBB.ics", '"2"', _todo("u-un", "s30 unberuehrt").encode(), False
        ),
        spike.SnapshotObject(
            "trashbin", "135.ics", '"5"', _todo("u-lo", "s30 eltern-loeschen").encode(), True
        ),
    ]
    spike.write_snapshot(tmp_path, "a", state_a)
    spike.write_snapshot(tmp_path, "b", state_b)
    return spike.load_snapshot(tmp_path / "ui-a"), spike.load_snapshot(tmp_path / "ui-b")


def test_load_snapshot_keys_the_objects_by_uid_and_marks_the_trash(tmp_path: Path) -> None:
    before, after = _states(tmp_path)
    assert sorted(before) == ["u-ab", "u-lo", "u-un"]
    assert before["u-ab"].file == "AAA.ics"
    assert after["u-lo"].file == "trash-135.ics"
    assert after["u-lo"].trashed is True
    assert after["u-ab"].trashed is False


def test_snapshot_lists_reads_the_list_of_every_file_from_the_last_run_of_a_label() -> None:
    protocol = "\n".join(
        [
            "UI-OBJEKT stand=a liste=alt name=AAA.ics summary=s30 abhaken etag=1",
            "UI-OBJEKT stand=a liste=l1 name=AAA.ics summary=s30 abhaken etag=1",
            "UI-OBJEKT stand=b liste=l2 name=AAA.ics summary=s30 abhaken etag=4",
            "UI-OBJEKT stand=b liste=trashbin name=trash-135.ics summary=s30 x etag=5",
        ]
    )
    assert spike.snapshot_lists(protocol, "a") == {"AAA.ics": "l1"}
    assert spike.snapshot_lists(protocol, "b") == {"AAA.ics": "l2", "trash-135.ics": "trashbin"}


def test_evaluate_snapshots_writes_the_mandatory_lines_from_two_small_states(
    tmp_path: Path,
) -> None:
    before, after = _states(tmp_path)
    lists_a = {"AAA.ics": "l1", "BBB.ics": "l1", "CCC.ics": "l1"}
    lists_b = {"AAA.ics": "l1", "BBB.ics": "l2", "trash-135.ics": "trashbin"}
    lines = spike.evaluate_snapshots(before, after, lists_a, lists_b)
    assert (
        "ABHAKEN FELDER hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine "
        "geaendert=DTSTAMP,LAST-MODIFIED zeitform_completed=utc"
    ) in lines
    assert "KONTROLLE unberuehrt differenz=leer" in lines
    assert any(line.startswith("WIEDEROEFFNEN FELDER ungemessen grund=") for line in lines)
    assert any(line.startswith("ELTERN ABHAKEN ungemessen grund=") for line in lines)
    assert any(line.startswith("WIEDERKEHREND app ungemessen grund=") for line in lines)
    assert "UI-PAPIERKORB objekte=1" in " ".join(lines)
    assert any(
        line.startswith("UI-UMZUG objekt=s30 unberuehrt von=l1 nach=l2 dateiname_gleich=ja")
        for line in lines
    )
    assert any(
        line.startswith("UI-PAPIERKORB objekt=s30 eltern-loeschen")
        and "inhalt_gleich_stand_a=ja" in line
        for line in lines
    )


def test_evaluate_snapshots_names_a_touched_control_object(tmp_path: Path) -> None:
    before, after = _states(tmp_path)
    touched = dict(after)
    touched["u-un"] = spike.SnapshotEntry(
        "BBB.ics", _todo("u-un", "s30 unberuehrt", "PRIORITY:1"), False
    )
    lines = spike.evaluate_snapshots(before, touched, {}, {})
    assert "KONTROLLE unberuehrt differenz=hinzu=PRIORITY entfernt=keine geaendert=keine" in lines


def _access(time: str, method: str, user: str, name: str, status: int) -> str:
    request = f"{method} /remote.php/dav/calendars/{user}/l1/{name} HTTP/1.1"
    return f'172.1.0.2 - - [11/Nov/2026:{time} +0000] "{request}" {status} 478 "-" "Mozilla"'


_ACCESS_LOG = "\n".join(
    [
        _access("13:01:25", "PUT", "spike30ui", "AAA.ics", 204),
        _access("13:01:26", "PUT", "spike30ui", "BBB.ics", 500),
        _access("13:01:27", "GET", "spike30ui", "BBB.ics", 200),
        _access("13:01:28", "PUT", "spike30a", "CCC.ics", 204),
        _access("13:03:41", "DELETE", "spike30ui", "CCC.ics", 204),
    ]
)


def test_access_writes_keeps_the_writing_requests_of_one_account_with_their_status() -> None:
    assert spike.access_writes(_ACCESS_LOG, "spike30ui") == [
        ("11/Nov/2026:13:01:25 +0000", "PUT", "l1/AAA.ics", 204),
        ("11/Nov/2026:13:01:26 +0000", "PUT", "l1/BBB.ics", 500),
        ("11/Nov/2026:13:03:41 +0000", "DELETE", "l1/CCC.ics", 204),
    ]


def test_merge_hits_joins_the_two_patterns_on_one_line() -> None:
    first = [("README.md", 42, "No deleting"), ("README.md", 60, "create-only")]
    second = [("README.md", 42, "No deleting"), ("tests/x.py", 7, "EXPECTED_PUT_CALLS = 6")]
    assert spike.merge_hits(first, second) == [
        spike.Hit("README.md", 42, "No deleting", "1+2"),
        spike.Hit("README.md", 60, "create-only", "1"),
        spike.Hit("tests/x.py", 7, "EXPECTED_PUT_CALLS = 6", "2"),
    ]


def test_classify_takes_the_first_matching_rule_and_names_an_unruled_hit() -> None:
    rules = (
        spike.Rule(r"^tests/x\.py$", "EXPECTED_PUT_CALLS", "gate", "PUT", "Phase 33"),
        spike.Rule(r"^tests/", "", "ausgeschlossen", "", "anderes Thema"),
    )
    assert spike.classify(spike.Hit("tests/x.py", 7, "EXPECTED_PUT_CALLS = 6", "2"), rules) == (
        "gate",
        "PUT",
        "Phase 33",
    )
    assert spike.classify(spike.Hit("tests/x.py", 9, "other", "2"), rules) == (
        "ausgeschlossen",
        "",
        "anderes Thema",
    )
    assert spike.classify(spike.Hit("README.md", 1, "x", "1"), rules) == ("ungeklaert", "", "")


def test_inventory_line_has_the_agreed_form_for_a_kept_and_an_excluded_hit() -> None:
    hit = spike.Hit("tests/x.py", 7, "EXPECTED_PUT_CALLS = 6", "1+2")
    assert spike.inventory_line(hit, ("gate", "PUT", "Phase 33")) == (
        "INVENTAR gate tests/x.py:7 | EXPECTED_PUT_CALLS = 6 | beruehrt_von=PUT | "
        "abzuarbeiten_in=Phase 33 | muster=1+2"
    )
    assert spike.inventory_line(hit, ("ausgeschlossen", "", "anderes Thema")) == (
        "INVENTAR ausgeschlossen tests/x.py:7 | EXPECTED_PUT_CALLS = 6 | "
        "grund=anderes Thema | muster=1+2"
    )
    long = spike.Hit("a.md", 1, "x" * 300, "1")
    assert (
        len(spike.inventory_line(long, ("zusage-doku", "PUT", "Phase 34")).split(" | ")[1]) == 200
    )


def test_positive_control_names_each_of_the_six_places_a_hit_stands_in() -> None:
    gate = spike.GATE_FILE
    anchors = {"EXPECTED_PUT_CALLS": [480, 571], "FORBIDDEN": [86]}
    hits = [
        (gate, 88, '"MOVE": "no tool may move or rename anything",'),
        (gate, 560, "No PUT anywhere in the production code may overwrite unconditionally."),
        ("README.md", 60, "**create-only** means it can create new objects"),
        ("docs/threat-model.md", 149, "`files_upload` remains create-only."),
        ("appinfo/info.xml", 69, "- Nothing destructive: no delete, no move, no share"),
    ]
    assert spike.positive_control(hits, anchors) == [
        "EXPECTED_PUT_CALLS",
        "FORBIDDEN",
        "README-Rechtetabelle",
        "threat-model",
        "Store-Text",
    ]
    hits.append(("src/mcp_connector/server/__init__.py", 63, "Files are never deleted"))
    assert spike.positive_control(hits, anchors) == list(spike.CONTROL_PLACES)
    far = [(gate, 300, "a destructive call far from both constants")]
    assert spike.positive_control(far, anchors) == []


# --- plan 30-03 task 1: MOVE under impersonation, sub tasks -----------------------------------


def test_abort_move_is_not_triggered_only_by_a_complete_move() -> None:
    assert spike.abort_move(status=201, source_gone=True, target_readable=True, uid_same=True) == (
        False,
        "keiner",
    )
    assert spike.abort_move(status=204, source_gone=True, target_readable=True, uid_same=True) == (
        False,
        "keiner",
    )


@pytest.mark.parametrize(
    ("values", "word"),
    [
        ({"status": 403}, "403"),
        ({"status": 500}, "500"),
        ({"status": 207}, "207"),
        ({"source_gone": False}, "Quelle"),
        ({"target_readable": False}, "Ziel"),
        ({"uid_same": False}, "UID"),
    ],
)
def test_abort_move_is_triggered_by_every_single_deviation_with_a_reason(
    values: dict[str, int | bool], word: str
) -> None:
    good: dict[str, int | bool] = {
        "status": 201,
        "source_gone": True,
        "target_readable": True,
        "uid_same": True,
    }
    aborted, reason = spike.abort_move(**{**good, **values})
    assert aborted is True
    assert word in reason


def test_destination_header_builds_the_url_of_the_target_object_and_quotes_the_name() -> None:
    assert (
        spike.destination_header("http://127.0.0.1:8082", "spike30a", "spike30-b", "x.ics")
        == "http://127.0.0.1:8082/remote.php/dav/calendars/spike30a/spike30-b/x.ics"
    )
    assert spike.destination_header(
        "http://127.0.0.1:8082/", "spike30a", "spike30-b", "a b.ics"
    ).endswith("/calendars/spike30a/spike30-b/a%20b.ics")


def test_uid_of_reads_the_uid_of_the_vtodo_and_refuses_a_text_without_one() -> None:
    text = spike.build_probe_todo("uid-in-the-todo", "s30 uid")
    assert spike.uid_of(text) == "uid-in-the-todo"
    with pytest.raises(ValueError, match="VTODO"):
        spike.uid_of("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:x\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")


def _state(*placed: tuple[str, str, str, str]) -> dict[str, object]:
    """``(uid, summary, collection, extra line)`` per object, as a state of ``child_fate``."""
    return {
        uid: spike.Placed(collection, spike.simple_todo(uid, summary, [extra] if extra else []))
        for uid, summary, collection, extra in placed
    }


def test_child_fate_names_the_four_outcomes_for_the_sub_task() -> None:
    before = _state(("p", "eltern", "liste-1", ""), ("c", "kind", "liste-1", "RELATED-TO:p"))
    stays = _state(("p", "eltern", "liste-2", ""), ("c", "kind", "liste-1", "RELATED-TO:p"))
    follows = _state(("p", "eltern", "liste-2", ""), ("c", "kind", "liste-2", "RELATED-TO:p"))
    gone = _state(("p", "eltern", "trashbin", ""))
    trashed = _state(("p", "eltern", "trashbin", ""), ("c", "kind", "trashbin", "RELATED-TO:p"))
    assert spike.child_fate(before, stays, "eltern", "kind") == "kind bleibt in quelle"
    assert spike.child_fate(before, follows, "eltern", "kind") == "kind zieht mit"
    assert spike.child_fate(before, gone, "eltern", "kind") == "kind geloescht"
    assert spike.child_fate(before, trashed, "eltern", "kind") == "kind im papierkorb"


def test_child_fate_refuses_a_state_a_without_the_parent() -> None:
    before = _state(("c", "kind", "liste-1", "RELATED-TO:p"))
    with pytest.raises(ValueError, match="eltern"):
        spike.child_fate(before, before, "eltern", "kind")


def test_parse_db_rows_reads_place_trash_mark_and_hash_of_every_row() -> None:
    rows = spike.parse_db_rows(
        "2 spike30a/spike30-a/x.ics|leer|ab:12 bob/l/x-deleted.ics|gesetzt|cd:9"
    )
    assert rows == [
        spike.DbRow("spike30a", "spike30-a", "x.ics", False, "ab:12"),
        spike.DbRow("bob", "l", "x-deleted.ics", True, "cd:9"),
    ]
    assert spike.parse_db_rows("0 ") == []
    assert spike.parse_db_rows("") == []


def test_parse_trash_source_reads_key_default_paths_and_command_from_the_grepped_lines() -> None:
    found = {
        "CalDAV/RetentionService.php": [
            "18:\tpublic const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';",
            "19:\tprivate const int DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;",
        ],
        "CalDAV/Trashbin/TrashbinHome.php": ["28:\tpublic const NAME = 'trashbin';"],
        "CalDAV/Trashbin/DeletedCalendarObjectsCollection.php": [
            "26:\tpublic const NAME = 'objects';"
        ],
        "CalDAV/Trashbin/RestoreTarget.php": ["20:\tpublic const NAME = 'restore';"],
        "CalDAV/Trashbin/Plugin.php": [
            (
                "33:\tpublic const PROPERTY_RETENTION_DURATION = "
                "'{http://nextcloud.com/ns}trash-bin-retention-duration';"
            )
        ],
        "CalDAV/CalDavBackend.php": [
            (
                "1778:\t\tif ($forceDeletePermanently || $this->config->getAppValue("
                "Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {"
            )
        ],
        "Command/RetentionCleanupCommand.php": [
            "22:\t\tparent::__construct('dav:retention:clean-up');"
        ],
    }
    assert spike.parse_trash_source(found) == spike.EXPECTED_SOURCE
    del found["CalDAV/Trashbin/RestoreTarget.php"]
    with pytest.raises(ValueError, match="RestoreTarget"):
        spike.parse_trash_source(found)


# --- plan 30-03 task 2: the delete verdict (E13) ----------------------------------------------


def _row(major: int, **values: bool) -> object:
    flags = {"g": True, "w1": True, "w2": True, "w3": False, "w4": True, **values}
    return spike.VersionRow(major=major, version=f"{major}.0.1", who="eigentuemer", **flags)


def _all(**values: bool) -> list[object]:
    return [_row(major, **values) for major in (32, 33, 34, 35)]


def test_delete_verdict_is_restorable_when_the_pretest_tells_the_off_state() -> None:
    assert spike.delete_verdict(_all(w3=False, w4=True)) == "wiederherstellbar"


def test_delete_verdict_is_restorable_when_the_off_state_still_restores() -> None:
    assert spike.delete_verdict(_all(w3=True, w4=False)) == "wiederherstellbar"


def test_delete_verdict_is_lost_when_one_version_has_neither_restore_nor_pretest() -> None:
    rows = [*_all()[:3], _row(35, w3=False, w4=False)]
    assert spike.delete_verdict(rows) == "nicht wiederherstellbar"


def test_delete_verdict_is_lost_when_one_version_fails_on_a_shared_list() -> None:
    rows = [_row(32, w2=False), *_all()[1:]]
    assert spike.delete_verdict(rows) == "nicht wiederherstellbar"


def test_delete_verdict_is_lost_when_one_version_fails_on_an_own_list() -> None:
    rows = [_row(32), _row(33, w1=False), _row(34), _row(35)]
    assert spike.delete_verdict(rows) == "nicht wiederherstellbar"


def test_delete_verdict_is_unclear_when_one_version_is_not_measured() -> None:
    rows = [*_all()[:2], _row(34, g=False), _row(35)]
    assert spike.delete_verdict(rows) == "nicht eindeutig"


def test_delete_verdict_is_unclear_when_a_version_is_missing_and_refuses_an_unknown_one() -> None:
    assert spike.delete_verdict(_all()[:3]) == "nicht eindeutig"
    assert spike.delete_verdict([]) == "nicht eindeutig"
    with pytest.raises(ValueError, match="36"):
        spike.delete_verdict([*_all(), _row(36)])


def test_delete_verdict_is_unclear_when_two_runs_of_one_version_contradict() -> None:
    rows = [*_all(), _row(34, w1=False)]
    assert spike.delete_verdict(rows) == "nicht eindeutig"
    assert spike.delete_verdict([*_all(), _row(34)]) == "wiederherstellbar"


def test_the_three_verdict_words_are_module_constants_with_real_blanks() -> None:
    assert spike.VERDICT_RESTORABLE == "wiederherstellbar"
    assert spike.VERDICT_LOST == "nicht wiederherstellbar"
    assert spike.VERDICT_UNCLEAR == "nicht eindeutig"


def test_parse_version_line_reads_the_major_version_and_the_five_values() -> None:
    row = spike.parse_version_line(
        "LOESCHEN VERSION 34.0.4 g=ja w1=ja w2=ja w3=nein w4=ja wer=eigentuemer"
    )
    assert (row.major, row.version, row.who) == (34, "34.0.4", "eigentuemer")
    assert (row.g, row.w1, row.w2, row.w3, row.w4) == (True, True, True, False, True)
    with pytest.raises(ValueError, match="w3"):
        spike.parse_version_line(
            "LOESCHEN VERSION 34.0.4 g=ja w1=ja w2=ja w3=vielleicht w4=ja wer=eigentuemer"
        )
    with pytest.raises(ValueError, match="LOESCHEN VERSION"):
        spike.parse_version_line("LOESCHEN an-eigen status=204")


def test_version_rows_lets_a_declared_repeat_replace_the_runs_before_it() -> None:
    head = "# Lauf blocks=delete-matrix start="
    first = f"{head}a\nLOESCHEN VERSION 33.0.9 g=nein w1=ja w2=ja w3=nein w4=ja wer=keiner\n"
    repeat = (
        "# Lauf blocks=delete-matrix start=b\nWIEDERHOLUNG Grund: Werkzeugfehler\n"
        "LOESCHEN VERSION 33.0.9 g=ja w1=ja w2=ja w3=nein w4=ja wer=eigentuemer\n"
    )
    plain = f"{head}c\nLOESCHEN VERSION 33.0.9 g=ja w1=nein w2=ja w3=nein w4=ja wer=keiner\n"
    assert [row.g for row in spike.version_rows(first + repeat)] == [True]
    assert [row.g for row in spike.version_rows(first + plain)] == [False, True]
    assert spike.version_rows("# Lauf blocks=delete-matrix start=a\nRUN FAILED | x\n") == []


def test_consequence_names_the_fixed_outcome_of_each_word() -> None:
    assert "TMOD-07" in spike.consequence("wiederherstellbar")
    assert "planbar" in spike.consequence("wiederherstellbar")
    for word in ("nicht wiederherstellbar", "nicht eindeutig"):
        assert "kein L\u00f6schen in 0.8.0, ohne R\u00fcckfrage" in spike.consequence(word)
    with pytest.raises(ValueError, match="vielleicht"):
        spike.consequence("vielleicht")


def test_validate_delete_tag_takes_the_four_tags_and_others_only_on_request() -> None:
    for tag in ("32.0.15-apache", "33.0.9-apache", "34.0.4-apache", "35.0.2-apache"):
        assert spike.validate_delete_tag(tag) == tag
    with pytest.raises(ValueError, match="allow-other-tag"):
        spike.validate_delete_tag("35.0.0-apache")
    assert spike.validate_delete_tag("35.0.0-apache", allow_other=True) == "35.0.0-apache"
    with pytest.raises(ValueError, match="allow-other-tag"):
        spike.validate_delete_tag("latest", allow_other=True)


def test_pretest_shows_reads_each_candidate_as_on_off_or_unclear() -> None:
    assert spike.pretest_shows("frist-eigenschaft", "2592000") == "an"
    assert spike.pretest_shows("frist-eigenschaft", "0") == "aus"
    assert spike.pretest_shows("frist-eigenschaft", "fehlt") == "unklar"
    assert spike.pretest_shows("papierkorb-propfind", "207") == "an"
    assert spike.pretest_shows("papierkorb-propfind", "404") == "aus"
    assert spike.pretest_shows("papierkorb-propfind", "500") == "unklar"
    assert spike.pretest_shows("home-kind-trashbin", "ja") == "an"
    assert spike.pretest_shows("dav-kopf", "nein") == "aus"
    assert spike.pretest_shows("capabilities-dav", '{"chunking": "1.0"}') == "unklar"


def test_pretest_distinguishing_keeps_only_candidates_right_in_both_states() -> None:
    on = {"frist-eigenschaft": "2592000", "papierkorb-propfind": "207", "dav-kopf": "ja"}
    off = {"frist-eigenschaft": "0", "papierkorb-propfind": "207", "dav-kopf": "ja"}
    assert spike.pretest_distinguishing(on, off) == ["frist-eigenschaft"]
    assert spike.pretest_distinguishing(on, on) == []
    assert spike.pretest_distinguishing(off, on) == []


# --- plan 30-04: discovery, queries, provider link, cost rule, fixtures ---------------------

_HOME_3004 = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav"
    xmlns:cs="http://calendarserver.org/ns/" xmlns:oc="http://owncloud.org/ns">
  <d:response><d:href>/remote.php/dav/calendars/alice/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
  {entries}
</d:multistatus>
"""


def _entry(uri: str, comps: str = "", types: str = "<cal:calendar/>", extra: str = "") -> str:
    comp = "".join(f'<cal:comp name="{name}"/>' for name in comps.split(",") if name)
    comp_set = (
        f"<cal:supported-calendar-component-set>{comp}</cal:supported-calendar-component-set>"
        if comp
        else ""
    )
    missing = (
        ""
        if comp
        else "<d:propstat><d:prop><cal:supported-calendar-component-set/></d:prop>"
        "<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat>"
    )
    return (
        f"<d:response><d:href>/remote.php/dav/calendars/alice/{uri}/</d:href>"
        f"<d:propstat><d:prop><d:resourcetype><d:collection/>{types}</d:resourcetype>"
        f"{comp_set}{extra}</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        f"{missing}</d:response>"
    )


def _kinds(*entries: str) -> dict[str, str]:
    body = _HOME_3004.format(entries="\n".join(entries))
    return {entry.uri: spike.classify_collection(entry) for entry in spike.parse_home(body)}


def test_parse_home_drops_the_home_itself_and_reads_only_found_properties() -> None:
    body = _HOME_3004.format(entries=_entry("personal", "VEVENT"))
    entries = spike.parse_home(body)
    assert [entry.uri for entry in entries] == ["personal"]
    assert entries[0].components == ("VEVENT",)
    assert entries[0].read_only is None


def test_classify_collection_names_every_kind_of_the_discovery() -> None:
    assert _kinds(
        _entry("app-generated--deck--board-7", "VEVENT,VTODO"),
        _entry("trashbin", types=""),
        _entry("weg", "VTODO", types='<x:deleted-calendar xmlns:x="http://nextcloud.com/ns"/>'),
        _entry("inbox", types="<cal:schedule-inbox/>"),
        _entry("outbox", types="<cal:schedule-outbox/>"),
        _entry("spike30-abo", types="<cs:subscribed/>"),
        _entry("x_shared_by_bob", "VTODO", extra="<oc:read-only>1</oc:read-only>"),
        _entry("y_shared_by_bob", "VTODO", extra="<oc:read-only></oc:read-only>"),
        _entry("z_shared_by_bob", "VTODO"),
        _entry("gemischt", "VEVENT,VTODO"),
        _entry("liste", "VTODO"),
        _entry("termine", "VEVENT"),
        _entry("leer"),
    ) == {
        "app-generated--deck--board-7": "deck",
        "trashbin": "papierkorb",
        "weg": "geloeschter-kalender",
        "inbox": "scheduling",
        "outbox": "scheduling",
        "spike30-abo": "abo",
        "x_shared_by_bob": "geteilt-nur-lesen",
        "y_shared_by_bob": "geteilt-schreibbar",
        "z_shared_by_bob": "geteilt-schreibbar",
        "gemischt": "gemischt",
        "liste": "aufgabenliste",
        "termine": "terminkalender",
        "leer": "ohne-komponenten",
    }


def test_task_lists_counts_only_lists_a_task_tool_may_use() -> None:
    fresh = spike.parse_home(_HOME_3004.format(entries=_entry("personal", "VEVENT")))
    assert spike.task_lists(fresh) == []
    body = _HOME_3004.format(
        entries="\n".join(
            [
                _entry("app-generated--deck--board-7", "VEVENT,VTODO"),
                _entry("trashbin", types=""),
                _entry("spike30-abo", "VTODO", types="<cs:subscribed/>"),
                _entry("weg", "VTODO", types='<x:deleted-calendar xmlns:x="urn:x"/>'),
                _entry("x_shared_by_bob", "VTODO", extra="<oc:read-only>1</oc:read-only>"),
                _entry("e_shared_by_bob", "VEVENT"),
                _entry("z_shared_by_bob", "VTODO"),
                _entry("gemischt", "VEVENT,VTODO"),
                _entry("liste", "VTODO"),
                _entry("termine", "VEVENT"),
            ]
        )
    )
    assert [entry.uri for entry in spike.task_lists(spike.parse_home(body))] == [
        "x_shared_by_bob",
        "z_shared_by_bob",
        "gemischt",
        "liste",
    ]


def _filter_xml(*args: str, **kwargs: str) -> str:
    return spike.build_todo_filter(*args, **kwargs).decode()


def test_build_todo_filter_offen_has_exactly_one_completed_is_not_defined() -> None:
    body = _filter_xml("offen")
    assert body.count("<c:prop-filter") == 1
    assert 'prop-filter name="COMPLETED"' in body
    assert "is-not-defined" in body
    assert 'comp-filter name="VTODO"' in body


def test_build_todo_filter_alle_has_no_prop_filter() -> None:
    body = _filter_xml("alle")
    assert "prop-filter" not in body
    assert 'comp-filter name="VTODO"' in body
    assert "calendar-data" in body


def test_build_todo_filter_fenster_text_eltern_erledigt() -> None:
    window = _filter_xml("fenster", "20261119T000000Z", "20261122T000000Z")
    assert 'time-range start="20261119T000000Z" end="20261122T000000Z"' in window
    text = _filter_xml("text", term="s30")
    assert 'prop-filter name="SUMMARY"' in text
    assert "text-match" in text
    assert 'match-type="contains"' in text
    assert ">s30<" in text
    parent = _filter_xml("eltern", parent_uid="abc-1")
    assert 'prop-filter name="RELATED-TO"' in parent
    assert ">abc-1<" in parent
    done = _filter_xml("erledigt")
    assert 'prop-filter name="COMPLETED"' in done
    assert "is-not-defined" not in done


def test_build_todo_filter_refuses_an_unknown_mode_and_never_makes_the_term_a_tag() -> None:
    with pytest.raises(ValueError, match="quer"):
        spike.build_todo_filter("quer")
    with pytest.raises(ValueError, match="fenster"):
        spike.build_todo_filter("fenster")
    body = _filter_xml("text", term="<c:evil/>")
    assert "<c:evil" not in body
    assert "&lt;c:evil/&gt;" in body


def _query_todo(summary: str, *extra: str) -> str:
    return spike.simple_todo(summary, summary, extra)


_OBJECTS = (
    _query_todo("q-offen-undatiert"),
    _query_todo("q-offen-im-fenster", "DUE:20261120T100000Z"),
    _query_todo("q-offen-ausserhalb", "DUE:20270301T100000Z"),
    _query_todo("q-erledigt", "STATUS:COMPLETED", "COMPLETED:20261110T090000Z"),
    _query_todo("q-ganztag", "DUE;VALUE=DATE:20261121"),
    _query_todo("q-kind", "RELATED-TO:q-offen-im-fenster"),
)


def test_names_in_reads_the_summaries_of_a_report_answer() -> None:
    responses = "".join(
        f"<d:response><d:href>/x/{number}.ics</d:href><d:propstat><d:prop>"
        f"<cal:calendar-data>{text}</cal:calendar-data></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for number, text in enumerate(_OBJECTS[:2])
    )
    body = (
        '<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
        f"{responses}</d:multistatus>"
    )
    assert spike.names_in(body) == {"q-offen-undatiert", "q-offen-im-fenster"}
    assert spike.names_in('<d:multistatus xmlns:d="DAV:"/>') == set()


def test_client_filter_is_the_set_the_connector_wants_from_each_query() -> None:
    assert spike.client_filter(_OBJECTS, "alle") == {
        "q-offen-undatiert",
        "q-offen-im-fenster",
        "q-offen-ausserhalb",
        "q-erledigt",
        "q-ganztag",
        "q-kind",
    }
    assert spike.client_filter(_OBJECTS, "offen") == {
        "q-offen-undatiert",
        "q-offen-im-fenster",
        "q-offen-ausserhalb",
        "q-ganztag",
        "q-kind",
    }
    assert spike.client_filter(_OBJECTS, "erledigt") == {"q-erledigt"}
    # an undated task is never part of a due window
    assert spike.client_filter(_OBJECTS, "fenster", "20261119T000000Z", "20261122T000000Z") == {
        "q-offen-im-fenster",
        "q-ganztag",
    }
    assert spike.client_filter(_OBJECTS, "text", term="Q-OFFEN") == {
        "q-offen-undatiert",
        "q-offen-im-fenster",
        "q-offen-ausserhalb",
    }
    assert spike.client_filter(_OBJECTS, "eltern", parent_uid="q-offen-im-fenster") == {"q-kind"}
    with pytest.raises(ValueError, match="quer"):
        spike.client_filter(_OBJECTS, "quer")


def test_same_sets_names_the_versions_that_differ_per_query() -> None:
    same = {"offen": {"a", "b"}, "alle": {"a", "b", "c"}}
    assert spike.same_sets({"32": same, "33": same, "34": same, "35": same}) == {
        "offen": [],
        "alle": [],
    }
    other = {"offen": {"a"}, "alle": {"a", "b", "c"}}
    assert spike.same_sets({"32": same, "33": other, "34": same, "35": same}) == {
        "offen": ["33"],
        "alle": [],
    }
    # a version that did not answer a query differs, it is never silently equal
    assert spike.same_sets({"32": same, "33": {"offen": {"a", "b"}}}) == {
        "offen": [],
        "alle": ["33"],
    }


def test_provider_link_parts_resolves_only_the_known_form() -> None:
    link = "/index.php/apps/tasks/calendars/spike30-x/tasks/abc.ics"
    assert spike.provider_link_parts(link) == ("spike30-x", "abc.ics")
    assert spike.provider_link_parts(
        "http://127.0.0.1:8083/index.php/apps/tasks/#/calendars/spike30%20x/tasks/a%20b.ics"
    ) == ("spike30 x", "a b.ics")
    assert spike.provider_link_parts("/index.php/apps/tasks/calendars/spike30-x") is None
    assert spike.provider_link_parts("/index.php/apps/calendar/edit/abc") is None
    assert spike.provider_link_parts("/apps/tasks/calendars/a/tasks/b.ics/extra") is None
    assert spike.provider_link_parts("") is None


def test_proposal_applies_the_derivation_rule_fixed_before_the_measurement() -> None:
    first = spike.proposal(median_all_seconds=0.4, max_seconds=0.9)
    assert "eine Abfrage je Liste ohne zusätzlichen Deckel unterhalb von 2000" in first
    assert "Zeitbudget je Liste 2 s" in first
    second = spike.proposal(1.6, 2.2)
    assert "Standardmodus offen als einziger Weg ohne Hinweis" in second
    assert "Zeitbudget je Liste 5 s" in second
    assert "Antwortgröße" in second
    # exactly 1.0 s still is the first proposal
    assert "ohne zusätzlichen Deckel" in spike.proposal(1.0, 1.0)
    assert "Zeitbudget je Liste 2 s" in spike.proposal(1.0, 1.0)


def test_summarize_and_series_line_name_the_second_largest_value_as_what_it_is() -> None:
    stats = spike.summarize([0.3, 0.1, 0.2, 0.5, 0.4])
    assert stats == {"min": 0.1, "median": 0.3, "p95_second_largest": 0.4, "max": 0.5}
    with pytest.raises(ValueError, match="two"):
        spike.summarize([0.1])
    line = spike.series_line("KOSTEN alle", [207] * 5, [2000] * 5, [10, 10, 10, 10, 12], stats)
    assert line == (
        "KOSTEN alle status=207 treffer=2000 bytes=10..12 min=100 median=300 "
        "p95_zweitgroesster=400 max=500 (n=5)"
    )


def test_pick_fixtures_maps_the_seven_kinds_and_names_what_is_missing() -> None:
    state_a = {
        "s30 ganztag": "a1",
        "s30 uhrzeit": "a2",
        "s30 kind-abhaken": "a3",
        "s30 eltern-abhaken": "a4",
        "s30 wiederkehrend": "a5",
        "s30 tags": "a6",
        "s30 abhaken": "a7",
        "s30 wieder-oeffnen": "a8",
    }
    state_b = {"s30 abhaken": "b7", "s30 wieder-oeffnen": "b8", "s30 ganztag": "b1"}
    picked, missing = spike.pick_fixtures(state_a, state_b)
    assert missing == []
    assert picked == {
        "all_day.ics": ("ganztag", "a", "a1"),
        "with_time.ics": ("uhrzeit", "a", "a2"),
        "subtask.ics": ("unteraufgabe", "a", "a3"),
        "subtask_parent.ics": ("unteraufgabe", "a", "a4"),
        "recurring.ics": ("wiederkehrend", "a", "a5"),
        "tags.ics": ("tags", "a", "a6"),
        "completed.ics": ("abgehakt", "b", "b7"),
        "reopened.ics": ("wieder-geoeffnet", "b", "b8"),
    }
    del state_a["s30 wiederkehrend"]
    del state_a["s30 eltern-abhaken"]
    picked, missing = spike.pick_fixtures(state_a, {})
    assert missing == ["unteraufgabe", "wiederkehrend", "abgehakt", "wieder-geoeffnet"]
    # nothing stands in for a missing kind, and half a sub task pair is no pair
    assert set(picked) == {"all_day.ics", "with_time.ics", "tags.ics"}


def test_probe_values_only_names_everything_that_is_no_probe_value() -> None:
    clean = (
        '<d:multistatus xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">'
        "<d:href>/remote.php/dav/calendars/alice/spike30-abo/</d:href>"
        "<cs:source><d:href>http://127.0.0.1:9/keine.ics</d:href></cs:source>"
        "<d:href>/remote.php/dav/principals/users/bob/</d:href></d:multistatus>"
    )
    assert spike.probe_values_only(clean, ("alice", "bob")) == []
    dirty = clean.replace("users/bob", "users/khaled").replace("127.0.0.1:9", "example.org")
    offences = spike.probe_values_only(dirty + " mail someone@example.org", ("alice", "bob"))
    assert "konto khaled" in offences
    assert "host example.org" in offences
    assert any(offence.startswith("adresse ") for offence in offences)


def test_raw_body_from_protocol_hands_out_the_bytes_only_if_their_hash_holds() -> None:
    import hashlib

    body = b'<?xml version="1.0"?>\n<d:multistatus xmlns:d="DAV:">\n  <d:response/>\n</d:x>\n'
    digest = hashlib.sha256(body).hexdigest()
    lines = [f"    {line}" for line in body.decode().split("\n")]
    protocol = "\n".join(
        [
            "== frisches-konto ==",
            f"ROHANTWORT-ANFANG discovery-frisch status=207 bytes={len(body)} sha256={digest}",
            *lines,
            "ROHANTWORT-ENDE discovery-frisch",
            "FRISCHES KONTO aufgabenlisten=0 kalender=personal(VEVENT)",
            "",
        ]
    )
    assert spike.raw_body_from_protocol(protocol, "discovery-frisch") == body
    assert spike.raw_body_from_protocol(protocol, "discovery-vorbereitet") is None
    # one changed character and the answer is no longer the one the run received
    assert (
        spike.raw_body_from_protocol(
            protocol.replace("<d:response/>", "<d:x/>"), "discovery-frisch"
        )
        is None
    )


def test_time_form_reads_what_icalendar_decoded() -> None:
    from datetime import UTC, date, datetime
    from zoneinfo import ZoneInfo

    assert spike.time_form(datetime(2026, 11, 20, 9, 15, tzinfo=UTC)) == "utc"
    assert spike.time_form(datetime(2026, 11, 20, 9, 15)) == "floating"
    assert (
        spike.time_form(datetime(2026, 11, 20, 9, 15, tzinfo=ZoneInfo("Europe/Berlin"))) == "tzid"
    )
    assert spike.time_form(date(2026, 11, 20)) == "date"
    assert spike.time_form("20261120") == "other"


# --- plan 30-05: the report checks itself, and the rule behind the E15 recommendation ---------


def _assumption_table(rows: dict[str, str]) -> str:
    lines = [
        "# Bericht",
        "",
        "## 8. Annahmen A1 bis A19 und A21",
        "",
        "| Annahme | Wortlaut | Status | Beleg | Folge |",
        "|---------|----------|--------|-------|-------|",
    ]
    lines += [
        f"| {name} | Wortlaut von {name} | {status} | Abschnitt 1, `raw/x.txt` | keine |"
        for name, status in rows.items()
    ]
    lines += ["", "## 9. Abbruchkriterien und Übergabe an die Phasen 31 bis 33", ""]
    return "\n".join(lines)


def test_assumption_rows_reads_the_status_word_of_every_row_of_section_8() -> None:
    rows = dict.fromkeys(spike.ASSUMPTIONS, "belegt") | {"A9": "widerlegt", "A5": "ungemessen"}
    found = spike.assumption_rows(_assumption_table(rows))
    assert found == rows
    assert len(found) == 19
    assert spike.missing_assumptions(found) == []


def test_assumptions_are_the_nineteen_of_this_phase_without_a10_and_a20() -> None:
    assert len(spike.ASSUMPTIONS) == 19
    assert "A10" not in spike.ASSUMPTIONS
    assert "A20" not in spike.ASSUMPTIONS
    assert spike.ASSUMPTIONS[0] == "A1"
    assert spike.ASSUMPTIONS[-1] == "A21"


def test_missing_assumptions_names_every_row_the_table_lacks() -> None:
    rows = dict.fromkeys(spike.ASSUMPTIONS, "belegt")
    del rows["A7"]
    del rows["A21"]
    found = spike.assumption_rows(_assumption_table(rows))
    assert spike.missing_assumptions(found) == ["A7", "A21"]
    assert spike.missing_assumptions({}) == list(spike.ASSUMPTIONS)


def test_assumption_rows_refuses_any_other_status_word() -> None:
    for word in ("teils belegt", "offen", "Belegt", "belegt, mit Einschränkung", ""):
        with pytest.raises(ValueError, match="A3"):
            spike.assumption_rows(_assumption_table({"A1": "belegt", "A3": word}))


def test_assumption_rows_refuses_a_double_row_and_a_row_without_evidence() -> None:
    table = _assumption_table({"A1": "belegt"})
    doubled = table.replace(
        "\n\n## 9.", "\n| A1 | noch einmal | widerlegt | Abschnitt 2 | keine |\n\n## 9."
    )
    with pytest.raises(ValueError, match="A1"):
        spike.assumption_rows(doubled)
    with pytest.raises(ValueError, match="A1"):
        spike.assumption_rows(table.replace("Abschnitt 1, `raw/x.txt`", " "))


def test_assumption_rows_reads_only_section_8_and_keeps_an_escaped_pipe_in_its_cell() -> None:
    table = _assumption_table({"A1": "belegt"}).replace("Wortlaut von A1", r"a \| b")
    elsewhere = table + "\n| A2 | steht in Abschnitt 9 | widerlegt | x | y |\n"
    assert spike.assumption_rows(elsewhere) == {"A1": "belegt"}


def _abort_table(rows: list[tuple[str, str]]) -> str:
    lines = [
        "## 9. Abbruchkriterien und Übergabe an die Phasen 31 bis 33",
        "",
        "| Kriterium | ausgelöst | Rohbeleg | Folge |",
        "|-----------|-----------|----------|-------|",
    ]
    lines += [f"| {name} | {value} | `zeile` in `raw/x.txt` | Folge |" for name, value in rows]
    lines += [
        "",
        "### 9.1 Was Phase 31 übernimmt",
        "",
        "| MESS-01 steht hier nur im Text | ja | x | y |",
        "",
        "## 10. Owner-Entscheid E15",
    ]
    return "\n".join(lines)


_ABORT_ROWS = [
    ("MESS-01 MKCOL unter Impersonation", "nein"),
    ("MESS-05 If-Match und fremde Eigenschaften", "nein"),
    ("MESS-06 MOVE unter Impersonation", "nein"),
    ("MESS-06 Löschen nach E13", "wiederherstellbar"),
]


def test_abort_rows_reads_exactly_the_four_criteria_by_their_keys() -> None:
    assert spike.abort_rows(_abort_table(_ABORT_ROWS)) == {
        "MESS-01": "nein",
        "MESS-05": "nein",
        "MESS-06-MOVE": "nein",
        "MESS-06-LOESCHEN": "wiederherstellbar",
    }
    assert tuple(spike.abort_rows(_abort_table(_ABORT_ROWS))) == spike.ABORT_KEYS


def test_abort_rows_refuses_a_missing_and_a_double_row() -> None:
    with pytest.raises(ValueError, match="MESS-06-MOVE"):
        spike.abort_rows(_abort_table([row for row in _ABORT_ROWS if "MOVE" not in row[0]]))
    with pytest.raises(ValueError, match="MESS-01"):
        spike.abort_rows(_abort_table([*_ABORT_ROWS, ("MESS-01 noch einmal", "ja")]))
    with pytest.raises(ValueError, match="MESS-01"):
        spike.abort_rows("## 9. Abbruchkriterien und Übergabe an die Phasen 31 bis 33\n")


def test_abort_rows_refuses_a_value_that_is_no_answer() -> None:
    wrong_flag = [("MESS-01 MKCOL unter Impersonation", "teilweise"), *_ABORT_ROWS[1:]]
    with pytest.raises(ValueError, match="MESS-01"):
        spike.abort_rows(_abort_table(wrong_flag))
    # deleting answers with the verdict word, never with ja or nein
    wrong_word = [*_ABORT_ROWS[:3], ("MESS-06 Löschen nach E13", "nein")]
    with pytest.raises(ValueError, match="MESS-06-LOESCHEN"):
        spike.abort_rows(_abort_table(wrong_word))
    unknown = [*_ABORT_ROWS, ("MESS-06 etwas anderes", "nein")]
    with pytest.raises(ValueError, match="MESS-06"):
        spike.abort_rows(_abort_table(unknown))


def test_e15_recommendation_names_the_switch_when_deleting_is_restorable() -> None:
    assert spike.e15_recommendation(
        delete_word="wiederherstellbar",
        move_overwrites=False,
        properties_lost=False,
        readonly_put_accepted=False,
    ) == ("eigener Schalter", ["S1"])


def test_e15_recommendation_stays_with_the_bundle_when_nothing_is_triggered() -> None:
    for word in ("nicht eindeutig", "nicht wiederherstellbar"):
        assert spike.e15_recommendation(
            delete_word=word,
            move_overwrites=False,
            properties_lost=False,
            readonly_put_accepted=False,
        ) == ("nur Bundle-Abschaltung", [])


def test_e15_recommendation_does_not_guess_an_unmeasured_trigger() -> None:
    values = {
        "delete_word": "nicht eindeutig",
        "move_overwrites": None,
        "properties_lost": False,
        "readonly_put_accepted": False,
    }
    assert spike.e15_recommendation(**values) == ("nur Bundle-Abschaltung", [])
    assert spike.e15_unmeasured(**values) == ["S2"]
    nothing = dict.fromkeys(values)
    assert spike.e15_recommendation(**nothing) == ("nur Bundle-Abschaltung", [])
    assert spike.e15_unmeasured(**nothing) == ["S1", "S2", "S3", "S4"]


def test_e15_recommendation_counts_each_trigger_on_its_own_and_in_order() -> None:
    quiet = {
        "delete_word": "nicht eindeutig",
        "move_overwrites": False,
        "properties_lost": False,
        "readonly_put_accepted": False,
    }
    assert spike.e15_recommendation(**quiet | {"move_overwrites": True}) == (
        "eigener Schalter",
        ["S2"],
    )
    assert spike.e15_recommendation(**quiet | {"properties_lost": True}) == (
        "eigener Schalter",
        ["S3"],
    )
    assert spike.e15_recommendation(**quiet | {"readonly_put_accepted": True}) == (
        "eigener Schalter",
        ["S4"],
    )
    everything = {
        "delete_word": "wiederherstellbar",
        "move_overwrites": True,
        "properties_lost": True,
        "readonly_put_accepted": True,
    }
    assert spike.e15_recommendation(**everything) == (
        "eigener Schalter",
        ["S1", "S2", "S3", "S4"],
    )
    assert spike.e15_unmeasured(**everything) == []
    # one measured trigger is enough, an unmeasured one next to it is still named
    assert spike.e15_recommendation(**everything | {"move_overwrites": None}) == (
        "eigener Schalter",
        ["S1", "S3", "S4"],
    )
    assert spike.e15_unmeasured(**everything | {"move_overwrites": None}) == ["S2"]


def test_e15_recommendation_refuses_a_word_that_is_no_verdict() -> None:
    with pytest.raises(ValueError, match="vielleicht"):
        spike.e15_recommendation(
            delete_word="vielleicht",
            move_overwrites=False,
            properties_lost=False,
            readonly_put_accepted=False,
        )


def _report_with(headings: list[str]) -> str:
    return "# Titel\n\nKopf\n\n" + "\n\n".join(f"{heading}\n\nText" for heading in headings) + "\n"


def test_headings_intact_wants_the_thirteen_headings_word_for_word_and_in_order() -> None:
    fixed = list(spike.REPORT_HEADINGS)
    assert len(fixed) == 13
    assert fixed[0] == "## Entscheidungskriterien, vorab festgelegt"
    assert fixed[1] == "## 1. MKCOL unter AppAPI-Impersonation (MESS-01)"
    assert fixed[8] == "## 8. Annahmen A1 bis A19 und A21"
    assert fixed[12] == "## 12. Rohausgaben"
    assert spike.headings_intact(_report_with(fixed)) is True
    # a sub heading in between is none of the fixed ones and does not disturb them
    with_sub = _report_with(fixed).replace(
        "## 12. Rohausgaben", "### 11.1 Mehr\n\n## 12. Rohausgaben"
    )
    assert spike.headings_intact(with_sub) is True


def test_headings_intact_notices_a_renamed_a_missing_a_moved_and_a_double_heading() -> None:
    fixed = list(spike.REPORT_HEADINGS)
    renamed = [*fixed[:10], "## 10. Owner-Entscheid", *fixed[11:]]
    assert spike.headings_intact(_report_with(renamed)) is False
    assert spike.headings_intact(_report_with(fixed[:-1])) is False
    moved = [*fixed[:8], fixed[9], fixed[8], *fixed[10:]]
    assert spike.headings_intact(_report_with(moved)) is False
    assert spike.headings_intact(_report_with([*fixed, fixed[3]])) is False
    # a heading that only stands inside a fenced block is a quote, not a heading
    fenced = _report_with(fixed[:-1]) + "\n```\n## 12. Rohausgaben\n```\n"
    assert spike.headings_intact(fenced) is False


def test_has_dash_finds_the_en_dash_and_the_em_dash_and_nothing_else() -> None:
    assert spike.has_dash(f"a {chr(0x2013)} b") is True
    assert spike.has_dash(f"a {chr(0x2014)} b") is True
    assert spike.has_dash("a - b") is False
    assert spike.has_dash("") is False


def test_protocol_field_reads_one_value_and_refuses_two_runs_that_differ() -> None:
    text = "\n".join(
        [
            "2026-11-11T16:40:29Z | MOVE belegt-ohne-kopf auth=appapi status=204 ueberschrieben=ja",
            "ABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201",
            "ABBRUCHKRITERIUM MESS-05 IF-MATCH ausgeloest=nein grund=keiner",
        ]
    )
    assert spike.protocol_field(text, "ABBRUCHKRITERIUM MESS-01", "ausgeloest") == "nein"
    assert spike.protocol_field(text, "ABBRUCHKRITERIUM MESS-01", "status") == "201"
    assert spike.protocol_field(text, "MOVE belegt-ohne-kopf auth=appapi", "ueberschrieben") == "ja"
    # no such line and no such field are both "not measured", never a no
    assert spike.protocol_field(text, "ABBRUCHKRITERIUM MESS-06 MOVE", "ausgeloest") is None
    assert spike.protocol_field(text, "ABBRUCHKRITERIUM MESS-01", "grund") is None
    same = text + "\nABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201\n"
    assert spike.protocol_field(same, "ABBRUCHKRITERIUM MESS-01", "ausgeloest") == "nein"
    differs = text + "\nABBRUCHKRITERIUM MESS-01 ausgeloest=ja status=403\n"
    with pytest.raises(ValueError, match="MESS-01"):
        spike.protocol_field(differs, "ABBRUCHKRITERIUM MESS-01", "ausgeloest")


def _head(lines: list[str]) -> str:
    return "\n".join(["# Titel", "", *lines, "", "## Entscheidungskriterien, vorab festgelegt", ""])


def _version_lines() -> list[str]:
    return [
        f"**{label}:** 1.2.3, gelesen mit `occ status` am 2026-11-11"
        for label in spike.HEAD_VERSION_LABELS
    ]


def test_head_problems_is_empty_when_every_version_line_names_how_it_was_read() -> None:
    assert spike.HEAD_VERSION_LABELS == (
        "Nextcloud",
        "AppAPI",
        "Diese ExApp",
        "groupfolders",
        "Tasks",
        "Deck",
        "Datenbank",
    )
    assert spike.head_problems(_head(_version_lines())) == []
    unmeasured = _version_lines()
    unmeasured[5] = "**Deck:** ungemessen, Grund: die App war nicht installiert (2026-11-12)"
    assert spike.head_problems(_head(unmeasured)) == []


def test_head_problems_names_a_missing_an_open_and_an_unexplained_version_line() -> None:
    lines = _version_lines()
    missing = spike.head_problems(_head(lines[:-1]))
    assert len(missing) == 1
    assert "Datenbank" in missing[0]
    lines[4] = "**Tasks:** offen, füllt Plan 30-02"
    still_open = spike.head_problems(_head(lines))
    assert any("Tasks" in problem for problem in still_open)
    lines[4] = "**Tasks:** 0.18.1"
    assert any("Tasks" in problem for problem in spike.head_problems(_head(lines)))
    lines[4] = "**Tasks:** ungemessen"
    assert any("Tasks" in problem for problem in spike.head_problems(_head(lines)))


def test_head_problems_finds_the_open_marker_anywhere_in_the_report() -> None:
    text = (
        _head(_version_lines())
        + "\n## 8. Annahmen A1 bis A19 und A21\n\nOffen, füllt Plan 30-05.\n"
    )
    problems = spike.head_problems(text)
    assert len(problems) == 1
    assert "füllt Plan" in problems[0]
