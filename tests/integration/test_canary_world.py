"""The canary world of phase 28 is real, tagged and gone again afterwards (plan 28-07).

The canary of plan 28-10 and the live pairs of plan 28-11 only prove something when the world
they run in exists: an empty index, a wrong container or a blunt reference canary would all
end in a green run. This test proves the world through the harness, never through the
connector: the control marker is read back from the untagged control file, the tagged file
ids are listed by the same tag REPORT the guard sends, the Tables row carries the tagged name
raw, and the calendar object carries its ATTACH. It also books one harness write of every
ledger kind, so the cleanup path the canary relies on for its write tools is exercised live.

Every cleanup line is read back from the instance and asserted after the block. Two runs in a
row prove that the first one left nothing that disturbs the build of the second.

Run it against nc35 with the environment of ``.env.nc35`` plus the six ``NC_MCP_E2E_*``
exports of ``topology.py``::

    .venv/Scripts/python.exe -m pytest tests/integration/test_canary_world.py -m integration -s

Without that environment it skips.
"""

import subprocess
import time
import uuid

import canary_world as cw
import pytest
import topology

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = cw.RAW_DIR / "28-07-world.txt"


def log(line: str) -> None:
    cw.record(RAW, line)


def git_head() -> str:
    finished = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return finished.stdout.strip() or "unbekannt"


def _book_harness_writes(world: cw.World) -> list[str]:
    """One harness write of every ledger kind, booked like a write tool of the canary."""
    harness, stamm = world.harness, world.stamm
    booked: list[str] = []

    note = harness.notes(
        "POST", "/notes", {"title": f"{stamm}-werkzeug", "content": f"{stamm}-werkzeug\n"}
    )
    world.register_tool_write("note", f"note:{note['id']}")

    row = harness.create_row(
        world.table_id,
        {world.column_id: world.link_cell(world.control_name, world.fileids["control_file"])},
    )
    world.register_tool_write("row", str(row["id"]))

    card_id = harness.deck_created(
        f"/boards/{world.board_id}/stacks/{world.stack_id}/cards",
        {"title": f"{stamm}-werkzeug", "type": "plain", "order": 999},
    )
    world.register_tool_write("card", f"card:{world.board_id}:{world.stack_id}:{card_id}")

    uid = f"{stamm}-werkzeug-{uuid.uuid4().hex[:8]}"
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//nc-mcp-connector//canary 28-07//EN\r\n"
        f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTAMP:20260928T080000Z\r\n"
        "DTSTART:20261006T090000Z\r\nDTEND:20261006T100000Z\r\n"
        f"SUMMARY:{stamm}-werkzeug\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()
    response = harness.request(
        "PUT",
        f"{world.calendar_url}{uid}.ics",
        headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        content=ics,
    )
    assert response.status_code == 201, f"PUT tool event: {response.status_code}"
    world.register_tool_write("event", f"event:{world.calendar_uri}:{uid}.ics")

    task_uid = f"{stamm}-werkzeug-{uuid.uuid4().hex[:8]}"
    response = harness.request(
        "PUT",
        f"{world.task_list_url}{task_uid}.ics",
        headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        content=cw.todo_ics(task_uid, f"{stamm}-werkzeug"),
    )
    assert response.status_code == 201, f"PUT tool task: {response.status_code}"
    world.register_tool_write("task", f"task:{world.task_list_uri}:{task_uid}.ics")

    posted = harness.ocs_post(f"{cw.TALK_CHAT}/{world.talk_token}", {"message": stamm})
    message = harness.ocs_data(posted, "post chat message")
    world.register_tool_write("message", f"message:{world.talk_token}:{message['id']}")

    with pytest.raises(ValueError, match="unknown write kind"):
        world.register_tool_write("mail", "mail:1")
    booked.extend(world.writes_ledger)
    return booked


def test_the_canary_world_is_built_tagged_and_removed() -> None:
    env = cw.live_env()
    log("")
    log(f"# 28-07 world run {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    with cw.canary_world(env, raw=RAW) as world:
        harness = world.harness
        harness_version = str(
            harness.request("GET", f"{env.url}/status.php").json().get("versionstring")
        )
        log(
            f"# nextcloud={harness_version} container={topology.NC_CONTAINER} head={git_head()} "
            f"user={env.user} user2={env.user2}"
        )
        log(f"# stamm={world.stamm} marker={world.marker} kontroll-marker={world.control_marker}")
        log(
            f"# pfade: getaggt={world.tagged_file} gesperrt={world.locked_dir} "
            f"gesperrt-datei={world.locked_file} kontrolle={world.control_file} "
            f"kategorie={world.category_path}"
        )
        for part, value in world.proof.items():
            log(f"WELT {part}: {value}")
        log(f"WELT deck-anhang: {world.deck_attachment}")

        for name, path in (
            ("locked_dir", world.locked_dir),
            ("locked_file", world.locked_file),
            ("tagged_category", world.tagged_category),
        ):
            cw.check(
                RAW,
                "WELT",
                "argumente",
                f"{name} ohne Marker",
                world.marker not in path and world.control_marker not in path,
                path,
            )

        status, text = harness.get_text(world.control_file)
        cw.check(
            RAW,
            "WELT",
            "kontrolle",
            "Kontrolldatei per GET mit Kontroll-Marker",
            status == 200 and world.control_marker in text,
            f"{status} {text.strip()}",
        )
        control_note = harness.notes("GET", f"/notes/{world.control_note_id}") or {}
        cw.check(
            RAW,
            "WELT",
            "kontrolle",
            "Kontrollnotiz mit Kontroll-Marker",
            world.control_marker in str(control_note.get("content") or ""),
            f"note {world.control_note_id} {str(control_note.get('title'))!r}",
        )

        status, found = harness.tagged_fileids(world.tag_id)
        targets = {
            world.fileids["tagged_file"],
            world.fileids["locked_dir"],
            world.note_id,
            world.fileids["category"],
        }
        cw.check(
            RAW,
            "WELT",
            "tags",
            "getaggte fileids per REPORT",
            status == 207 and targets <= found,
            f"REPORT {status} ziel {sorted(targets)} fehlt {sorted(targets - found)}",
        )
        controls = {world.fileids["control_file"], world.control_note_id}
        cw.check(
            RAW,
            "WELT",
            "tags",
            "Kontrolldatei und Kontrollnotiz ungetaggt",
            not controls & found,
            f"kontrolle {sorted(controls)} getaggt {sorted(controls & found)}",
        )

        status, raw = harness.rows_simple_raw(world.table_id)
        wire = raw.replace("\\/", "/")
        cw.check(
            RAW,
            "WELT",
            "tables-link",
            "Zeile 1 roh mit dem Namen der getaggten Datei",
            status == 200
            and world.tagged_name in wire
            and f"/f/{world.fileids['tagged_file']}" in wire,
            f"rows/simple {status}",
        )

        event = harness.request("GET", f"{world.calendar_url}{world.event_uid}.ics")
        unfolded = event.text.replace("\r\n ", "").replace("\n ", "")
        attach = next((line for line in unfolded.splitlines() if line.startswith("ATTACH")), "")
        cw.check(
            RAW,
            "WELT",
            "kalender-attach",
            "Kalenderobjekt roh mit ATTACH auf die getaggte Datei",
            event.status_code == 200
            and world.tagged_name in attach
            and f"/f/{world.fileids['tagged_file']}" in attach,
            f"GET {event.status_code} {attach}",
        )

        tokens = harness.room_tokens()
        cw.check(
            RAW,
            "WELT",
            "datei-raum",
            "Harness-Raum und Datei-Raum gelistet",
            world.talk_token in tokens and world.file_room_token in tokens,
            f"raum {world.talk_token} datei-raum {world.file_room_token}",
        )
        cw.check(
            RAW,
            "WELT",
            "deck",
            "Board und Karte angelegt, Anhangversuch mit Rohstatus",
            bool(world.board_id and world.card_id and world.deck_attachment),
            world.deck_attachment,
        )

        booked = _book_harness_writes(world)
        log(f"WELT ledger: {booked}")

    lines = world.cleanup_lines
    log(
        f"ZUSAMMENFASSUNG 28-07 cleanup: {len(lines)} Zeilen, "
        f"{sum(1 for line in lines if cw.cleanup_ok(line))} gelesen ok"
    )
    assert lines, "the cleanup registered nothing"
    assert len([line for line in lines if line.startswith("CLEANUP tool ")]) == len(
        cw.WRITE_KINDS
    ), lines
    bad = [line for line in lines if not cw.cleanup_ok(line)]
    assert not bad, bad
