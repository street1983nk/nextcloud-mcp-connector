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
