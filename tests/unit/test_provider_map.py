"""Unit tests for the provider table and the id extraction of unified search entries.

Pitfall 10 in one sentence: a unified search entry has no ``id`` field, so every id in
this project is either read out of ``attributes`` (only Files fills it), parsed out of
``resourceUrl``, or honestly marked as not resolvable. These tests pin all three outcomes,
including the two that are easy to get wrong: an unknown provider must never be guessed
into a known kind, and a ``resourceUrl`` from a foreign host must never survive into the
answer (threat T-01-68).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from mcp_connector import ids, provider_map

BASE = "http://nc.test"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def files_entries() -> list[dict[str, Any]]:
    return fixture("ocs_search_files.json")["ocs"]["data"]["entries"]


def resolved(provider_id: str, entry: dict[str, Any]) -> tuple[str, str, bool]:
    """:func:`provider_map.extract_id`, with the skip case turned into a clear failure."""
    result = provider_map.extract_id(provider_id, entry, BASE)
    assert result is not None, f"the {provider_id} entry produced no id at all"
    return result


def test_a_files_hit_takes_its_id_from_the_attributes() -> None:
    """Only the files provider fills ``attributes.fileId``, and it is the cheapest source."""
    kind, identifier, canonical = resolved("files", files_entries()[0])

    assert kind == "file"
    assert identifier == "file:4711"
    assert canonical is True


def test_a_files_hit_without_attributes_falls_back_to_the_f_segment() -> None:
    """``attributes`` is an empty list on some instances; ``/f/<fileid>`` still resolves."""
    kind, identifier, canonical = resolved("files", files_entries()[1])

    assert kind == "file"
    assert identifier == "file:4712"
    assert canonical is True


@pytest.mark.parametrize("digit", ["²", "٤٢"])
def test_a_file_id_that_is_not_ascii_digits_degrades_to_the_url_kind(digit: str) -> None:
    """Review finding WR-02: both values are true under ``str.isdigit`` and neither is an
    id Nextcloud ever handed out.

    The attribute reader and the ``/f/`` fallback measure with the same ASCII pattern, so a
    deformed entry becomes the honest ``url`` kind instead of ``file:٤٢``, which would cost
    a SEARCH request for a value the instance never issued.
    """
    entry = {"attributes": {"fileId": digit}, "resourceUrl": f"/index.php/f/{digit}"}

    kind, identifier, canonical = resolved("files", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/f/{digit}"
    assert canonical is False


@pytest.mark.parametrize("digit", ["²", "٤٢"])
def test_a_last_segment_that_is_not_ascii_digits_degrades_to_the_url_kind(digit: str) -> None:
    """The same WR-02 pair over ``last_numeric_segment``, the source of note and card ids."""
    entry = {"title": "kaputt", "resourceUrl": f"/index.php/apps/notes/note/{digit}"}

    kind, identifier, canonical = resolved("notes", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/apps/notes/note/{digit}"
    assert canonical is False


def test_a_notes_hit_takes_its_id_from_the_last_url_segment() -> None:
    """The notes provider ships no ``attributes`` at all (verified in the notes app)."""
    entry = {"title": "Protokoll", "resourceUrl": f"{BASE}/index.php/apps/notes/note/12"}

    assert provider_map.extract_id("notes", entry, BASE) == ("note", "note:12", True)


def test_a_deck_hit_becomes_the_short_card_form_and_is_not_canonical() -> None:
    """``search-deck-card-board`` only ever delivers the cardId, never board and stack."""
    entry = {"title": "Karte", "resourceUrl": "/apps/deck/card/57"}

    kind, identifier, canonical = resolved("search-deck-card-board", entry)

    assert kind == "card"
    assert identifier == "card:57"
    assert canonical is False, "board and stack are missing, so this id needs a sweep"


def test_an_unknown_provider_becomes_a_url_and_is_never_guessed() -> None:
    """An honest boundary beats a wrong resolution (pitfall 10).

    The example is a provider that really exists and really is unknown here. ``"spreed"`` used
    to stand in this line and was never a provider id at all, so the rule was checked against
    the one app whose two real provider ids are now in the table.
    """
    entry = {"title": "Formular", "resourceUrl": "/apps/forms/abc123"}

    kind, identifier, canonical = resolved("forms", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/apps/forms/abc123"
    assert canonical is False


def test_a_talk_conversation_hit_stays_a_url_because_a_conversation_is_no_document() -> None:
    """``talk-conversations`` is deliberately absent from the table; ``talk_browse`` is the way."""
    entry = {"title": "Team", "resourceUrl": "/index.php/call/abcd1234"}

    kind, identifier, canonical = resolved("talk-conversations", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/call/abcd1234"
    assert canonical is False


def test_an_entry_without_a_resource_url_and_without_attributes_is_skipped() -> None:
    assert provider_map.extract_id("files", {"title": "kaputt"}, BASE) is None
    assert provider_map.extract_id("forms", {"title": "kaputt", "attributes": []}, BASE) is None


def test_a_known_provider_with_an_unusable_url_degrades_to_the_url_kind() -> None:
    """A wrong note id would read a different note; the url stays honest instead."""
    entry = {"title": "kaputt", "resourceUrl": "/index.php/apps/notes/"}

    kind, identifier, canonical = resolved("notes", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/apps/notes/"
    assert canonical is False


def test_attributes_are_read_as_an_object_and_a_missing_key_is_no_error() -> None:
    """The server annotation says ``list<string>``; the wire format is an object."""
    entry = {"resourceUrl": f"{BASE}/index.php/f/8", "attributes": {"path": "Docs/x.md"}}

    assert provider_map.extract_id("files", entry, BASE) == ("file", "file:8", True)


def test_a_foreign_resource_url_is_rebuilt_on_the_configured_base_url() -> None:
    """The url is only ever parsed, never fetched, and never left pointing elsewhere."""
    entry = {"title": "geklaut", "resourceUrl": "http://evil.test/index.php/apps/notes/note/5"}

    _, identifier, _ = resolved("notes", entry)
    url = provider_map.hit_url(BASE, "note", identifier, entry)

    assert identifier == "note:5"
    assert url == f"{BASE}/index.php/apps/notes/note/5"
    assert "evil.test" not in url


@pytest.mark.parametrize(
    ("provider_id", "entry"),
    [
        ("files", {"resourceUrl": f"{BASE}/index.php/f/4711"}),
        ("files", {"attributes": {"fileId": "4711"}}),
        ("notes", {"resourceUrl": "/index.php/apps/notes/note/12"}),
        ("search-deck-card-board", {"resourceUrl": "/apps/deck/card/57"}),
        ("forms", {"resourceUrl": "/apps/forms/abc123"}),
        ("talk-message", {"resourceUrl": "/index.php/call/abcd1234#message_42"}),
        ("tables-search-tables", {"resourceUrl": "/index.php/apps/tables/#/table/7"}),
    ],
)
def test_every_hit_carries_an_absolute_non_empty_url(
    provider_id: str, entry: dict[str, Any]
) -> None:
    """ChatGPT only builds a citation when ``url`` is a non-empty, openable string."""
    kind, identifier, _ = resolved(provider_id, entry)
    url = provider_map.hit_url(BASE, kind, identifier, entry)

    assert url.startswith(f"{BASE}/"), url
    assert url != BASE


def test_a_talk_hit_takes_the_conversation_and_the_message_from_the_attributes() -> None:
    """``conversation`` and ``messageId`` are the cheapest source, exactly like ``fileId``."""
    entry = {
        "title": "Protokoll",
        "resourceUrl": "/index.php/call/abcd1234#message_42",
        "attributes": {"conversation": "abcd1234", "messageId": "42", "threadId": "7"},
    }

    kind, identifier, canonical = resolved("talk-message", entry)

    assert kind == "message"
    assert identifier == "message:abcd1234:42", "threadId must never reach the id"
    assert canonical is True


def test_a_talk_hit_without_attributes_falls_back_to_the_call_path_and_the_fragment() -> None:
    """``attributes`` arrives as an empty list on some instances (pitfall 7)."""
    entry = {
        "title": "Protokoll",
        "resourceUrl": "/index.php/call/abcd1234#message_42",
        "attributes": [],
    }

    assert resolved("talk-message", entry) == ("message", "message:abcd1234:42", True)


def test_the_second_talk_provider_resolves_exactly_like_the_first_one() -> None:
    """``CurrentMessageSearch`` extends ``MessageSearch`` and inherits ``performSearch``."""
    entry = {
        "title": "Protokoll",
        "resourceUrl": "/index.php/call/abcd1234#message_42",
        "attributes": {"conversation": "abcd1234", "messageId": "42"},
    }

    assert resolved("talk-message-current", entry) == ("message", "message:abcd1234:42", True)


def test_a_talk_hit_without_a_usable_conversation_or_message_stays_a_url() -> None:
    """A guessed token would address a conversation of somebody else (threat T-11-02)."""
    entry = {"title": "Talk", "resourceUrl": "/index.php/apps/spreed/", "attributes": []}

    kind, identifier, canonical = resolved("talk-message", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/apps/spreed/"
    assert canonical is False


def test_a_talk_hit_with_a_non_numeric_message_id_stays_a_url() -> None:
    """No fragment to fall back to, so the entry degrades instead of inventing a number."""
    entry = {
        "title": "Talk",
        "resourceUrl": "/index.php/call/abcd1234",
        "attributes": {"conversation": "abcd1234", "messageId": "abc"},
    }

    kind, _, canonical = resolved("talk-message", entry)

    assert kind == "url"
    assert canonical is False


def test_a_tables_hit_takes_its_id_from_the_fragment_not_from_the_path() -> None:
    """The tables app puts the node into ``#/table/<id>``; the path ends at the app route."""
    entry = {"title": "Inventar", "resourceUrl": "/index.php/apps/tables/#/table/7"}

    assert resolved("tables-search-tables", entry) == ("table", "table:7", True)


def test_a_tables_view_hit_stays_a_url_because_a_guessed_table_reads_a_foreign_table() -> None:
    """``#/view/3`` as ``table:3`` would read the table numbered three (threat T-11-01)."""
    entry = {"title": "Ansicht", "resourceUrl": "/index.php/apps/tables/#/view/3"}

    kind, identifier, canonical = resolved("tables-search-tables", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/apps/tables/#/view/3"
    assert canonical is False


@pytest.mark.parametrize(
    "resource_url",
    [
        "/index.php/apps/tables/#/table/",
        "/index.php/apps/tables/#/table/7a",
        "/index.php/apps/tables/",
    ],
)
def test_a_tables_hit_without_a_numeric_node_stays_a_url(resource_url: str) -> None:
    """No fragment, an empty node or a non numeric one: all three degrade honestly."""
    kind, _, canonical = resolved(
        "tables-search-tables", {"title": "t", "resourceUrl": resource_url}
    )

    assert kind == "url"
    assert canonical is False


def test_a_mail_hit_stays_a_url_because_the_deep_link_resolution_is_unmeasured() -> None:
    """``mail:<databaseId>`` needs a database id; a guessed one reads a foreign mailbox."""
    entry = {"title": "Rechnung", "resourceUrl": "/index.php/apps/mail/box/1/thread/5"}

    kind, identifier, canonical = resolved("mail", entry)

    assert kind == "url"
    assert identifier == f"url:{BASE}/index.php/apps/mail/box/1/thread/5"
    assert canonical is False


def test_a_foreign_origin_in_a_tables_fragment_never_reaches_the_id() -> None:
    """The fragment survives, the origin never does (threat T-11-04)."""
    entry = {"title": "t", "resourceUrl": "http://evil.test/index.php/apps/tables/#/table/7"}

    kind, identifier, _ = resolved("tables-search-tables", entry)

    assert kind == "table"
    assert identifier == "table:7"
    assert "evil.test" not in identifier
    assert "evil.test" not in provider_map.hit_url(BASE, kind, identifier, entry)


@pytest.mark.parametrize(
    "resource_url",
    [
        # The form measured on 32 and 35: path, no index.php, no percent encoding.
        "/apps/tasks/calendars/tasks/tasks/abc.ics",
        # The same route behind index.php, for an instance without pretty URLs.
        "/index.php/apps/tasks/calendars/tasks/tasks/abc.ics",
        # The fragment form of older Tasks releases.
        "/apps/tasks/#/calendars/tasks/tasks/abc.ics",
        "/index.php/apps/tasks/#/calendars/tasks/tasks/abc.ics",
        # Absolute, as the provider really sends it.
        f"{BASE}/apps/tasks/calendars/tasks/tasks/abc.ics",
    ],
)
def test_a_tasks_hit_becomes_a_task_id_in_every_measured_form(resource_url: str) -> None:
    """TASK-09: path with or without index.php and the fragment after ``#/`` all read the same."""
    entry = {"title": "Einkaufen", "resourceUrl": resource_url}

    assert resolved("tasks", entry) == ("task", "task:tasks:abc.ics", True)


def test_a_tasks_hit_of_a_shared_list_carries_the_key_and_never_the_account() -> None:
    """D-32-14: the URI of a shared list names the sharer, the id carries the neutral key."""
    entry = {
        "title": "Team",
        "resourceUrl": f"{BASE}/apps/tasks/calendars/team_shared_by_bob/tasks/t1.ics",
    }

    kind, identifier, canonical = resolved("tasks", entry)

    assert (kind, canonical) == ("task", True)
    assert identifier == f"task:{ids.task_list_key('team_shared_by_bob')}:t1.ics"
    assert "bob" not in identifier
    assert "shared_by" not in identifier


def test_a_tasks_hit_of_a_shared_list_links_only_the_start_page_of_the_tasks_app() -> None:
    """D-32-15 for the search hit as well: the deep link carries ``_shared_by_<account>``."""
    entry = {
        "title": "Team",
        "resourceUrl": f"{BASE}/apps/tasks/calendars/team_shared_by_bob/tasks/t1.ics",
    }
    kind, identifier, _ = resolved("tasks", entry)

    url = provider_map.hit_url(BASE, kind, identifier, entry)

    assert url == f"{BASE}/index.php/apps/tasks/"
    assert "bob" not in url


def test_a_tasks_hit_of_an_own_list_keeps_its_deep_link() -> None:
    """Only the shared case loses the deep link; an own list names nobody."""
    entry = {"title": "t", "resourceUrl": f"{BASE}/apps/tasks/calendars/tasks/tasks/abc.ics"}
    kind, identifier, _ = resolved("tasks", entry)

    assert provider_map.hit_url(BASE, kind, identifier, entry) == (
        f"{BASE}/apps/tasks/calendars/tasks/tasks/abc.ics"
    )


def test_a_tasks_hit_reads_special_characters_through_unquote() -> None:
    """Percent encoded URI and object name come back as the codec reads them."""
    entry = {
        "title": "t",
        "resourceUrl": "/apps/tasks/calendars/liste-%C3%A4%C3%B6/tasks/a%26%2B%20b.ics",
    }

    kind, identifier, _ = resolved("tasks", entry)

    assert kind == "task"
    assert ids.parse(identifier) == ("task", ("liste-äö", "a&+ b.ics"))


def test_a_tasks_hit_reads_the_unencoded_form_the_provider_really_sends() -> None:
    """Measured: the provider sends umlauts, ``&``, ``+`` and a blank as they are."""
    entry = {"title": "t", "resourceUrl": "/apps/tasks/calendars/sonder-äö/tasks/ä&+ 1.ics"}

    _, identifier, _ = resolved("tasks", entry)

    assert ids.parse(identifier) == ("task", ("sonder-äö", "ä&+ 1.ics"))


@pytest.mark.parametrize(
    "resource_url",
    [
        # Deck: its calendars are never task lists of this bundle (E9).
        "/apps/tasks/calendars/app-generated--deck--board-1/tasks/card.ics",
        "/apps/tasks/#/calendars/app-generated--deck--board-1/tasks/card.ics",
        # Extra segments, missing object, missing list, wrong app, wrong middle segment.
        "/apps/tasks/calendars/tasks/tasks/abc.ics/more",
        "/apps/tasks/calendars/extra/tasks/tasks/abc.ics",
        "/apps/tasks/calendars/tasks/tasks/",
        "/apps/tasks/calendars/tasks/tasks",
        "/apps/tasks/calendars//tasks/abc.ics",
        "/apps/tasks/",
        "/apps/calendar/calendars/tasks/tasks/abc.ics",
        "/apps/tasks/calendars/tasks/events/abc.ics",
        # A colon would be refused by the codec; the hit degrades instead of failing.
        "/apps/tasks/calendars/tasks/tasks/a%3Ab.ics",
        # A query is not part of the measured form.
        "/apps/tasks/calendars/tasks/tasks/abc.ics?x=1",
    ],
)
def test_every_other_tasks_link_stays_a_url_and_is_never_a_task(resource_url: str) -> None:
    """Never guess: anything outside the measured form is the honest ``url`` kind."""
    kind, identifier, canonical = resolved("tasks", {"title": "t", "resourceUrl": resource_url})

    assert kind == "url"
    assert canonical is False
    assert not identifier.startswith("task:")


def test_a_foreign_origin_in_a_tasks_link_never_reaches_the_id() -> None:
    """The origin is dropped like everywhere in this module (threat T-01-68, T-32-06-01)."""
    entry = {"title": "t", "resourceUrl": "http://evil.test/apps/tasks/calendars/tasks/tasks/a.ics"}

    kind, identifier, _ = resolved("tasks", entry)

    assert (kind, identifier) == ("task", "task:tasks:a.ics")
    assert "evil.test" not in provider_map.hit_url(BASE, kind, identifier, entry)


def test_the_tasks_provider_link_is_only_parsed_never_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No request at all: any attempt to open a connection fails this test."""
    import httpx

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the provider link was fetched")

    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)

    entry = {"title": "t", "resourceUrl": f"{BASE}/apps/tasks/calendars/tasks/tasks/abc.ics"}
    assert resolved("tasks", entry)[0] == "task"


def test_the_provider_table_knows_the_real_deck_provider_id() -> None:
    """It is ``search-deck-card-board``, not ``deck``, and that is worth a test."""
    assert provider_map.PROVIDER_KINDS["search-deck-card-board"] == "card"
    assert "deck" not in provider_map.PROVIDER_KINDS


def test_the_provider_table_is_not_a_list_of_installed_apps() -> None:
    """The runtime list comes from Nextcloud; this table only maps ids to kinds."""
    assert set(provider_map.PROVIDER_KINDS) == {
        "files",
        "notes",
        "search-deck-card-board",
        "talk-message",
        "talk-message-current",
        "tables-search-tables",
        "tasks",
    }
    assert provider_map.PROVIDER_KINDS["tasks"] == "task"
    assert "talk-conversations" not in provider_map.PROVIDER_KINDS
    assert "mail" not in provider_map.PROVIDER_KINDS


#: The three pages that carry the example answer of ``unified_search``. They spell the same
#: line, so an id that does not exist is a wrong lesson three times over.
READMES = ("README.md", "README.de.md", "README.fr.md")

#: Provider ids that really exist on a Nextcloud and are deliberately **not** in
#: :data:`provider_map.PROVIDER_KINDS`. This list stands in the test and not in
#: ``provider_map.py`` on purpose: that module keeps a translation table, not a list of the ids
#: it declines to translate, and its module docstring already says in prose why this one is
#: absent (a conversation is no document, ``talk_browse`` is the way to it). Exactly one entry
#: today, and the two tests above are its proof.
REAL_BUT_UNREGISTERED = frozenset({"talk-conversations"})

_PROVIDER_IN_JSON = re.compile(r'"provider":"([a-z0-9-]+)"')


def provider_ids(text: str, name: str) -> set[str]:
    """Every provider id the example answers in this text name.

    Takes a text and a name rather than a path, so the holder below and its counter probe run
    through the same extraction. A counter probe with a regex of its own would prove something
    about the counter probe.

    The not empty assertion is part of it: a reformatted example would otherwise turn the
    holder into a test that passes because it found nothing to look at.
    """
    found = set(_PROVIDER_IN_JSON.findall(text))
    assert found, f"{name} names no provider id at all, so the example was reformatted"
    return found


def test_every_provider_id_in_the_readmes_is_one_that_exists() -> None:
    """TOOL-19: ``"provider":"spreed"`` stood in all three READMEs for three releases.

    A documented answer is a lesson about the shape of the world, and ``spreed`` is the name of
    the Talk app, never a provider id, so the example taught a provider landscape that does not
    exist. The replacement is ``talk-conversations``, which is real and deliberately not in the
    table, so ``"kind":"url"`` and ``"resolvable":false`` beside it are true rather than
    invented.
    """
    root = Path(__file__).resolve().parents[2]
    for name in READMES:
        found = provider_ids((root / name).read_text(encoding="utf-8"), name)

        unexplained = found - set(provider_map.PROVIDER_KINDS) - REAL_BUT_UNREGISTERED
        assert unexplained == set(), (
            f"{name} names the provider id(s) {sorted(unexplained)}, and none of them is in "
            "PROVIDER_KINDS or in REAL_BUT_UNREGISTERED. Either the id is real and belongs in "
            "one of the two, or the example names something that does not exist."
        )
        assert "talk-conversations" in found, (
            f"{name} no longer names an unregistered provider id, so the example lost the case "
            "it exists for: the honest boundary of an unknown provider"
        )


def test_the_holder_would_notice_the_id_that_used_to_stand_there() -> None:
    """Counter proof: the line as it read until this plan, through the same extraction.

    Without it the holder would be green from the day it was written, without ever having
    looked at anything.
    """
    as_it_stood = '{"results":[{"provider":"spreed","kind":"url","resolvable":false}]}'

    found = provider_ids(as_it_stood, "a constructed example")

    assert found == {"spreed"}
    assert found - set(provider_map.PROVIDER_KINDS) - REAL_BUT_UNREGISTERED == {"spreed"}
