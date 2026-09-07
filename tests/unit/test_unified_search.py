"""Unit tests for the cloud wide search, all paths.

The three properties that make this tool trustworthy get one test each, and none of them
is about the happy path: the provider list is read from the instance on every call, a
provider that fails or stalls appears under ``degraded`` instead of quietly shrinking the
result, and a hit whose id cannot be resolved later says so instead of pretending.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import search as search_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

PROVIDERS_URL = f"{BASE}/ocs/v2.php/search/providers"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def search_url(provider_id: str) -> str:
    return f"{PROVIDERS_URL}/{provider_id}/search"


def provider_list(*ids: str) -> dict[str, Any]:
    """The runtime provider list, optionally narrowed to a few of the fixture providers."""
    payload = fixture("ocs_providers.json")
    if ids:
        entries = [item for item in payload["ocs"]["data"] if item["id"] in ids]
        return envelope(entries)
    return payload


def hits(name: str, entries: list[dict[str, Any]], cursor: Any = None) -> dict[str, Any]:
    return envelope(
        {"name": name, "isPaginated": cursor is not None, "entries": entries, "cursor": cursor}
    )


NOTE_ENTRY = {
    "title": "Protokoll 2026-08-14",
    "subline": "Anwesend: Anja, Khaled",
    "resourceUrl": f"{BASE}/index.php/apps/notes/note/12",
    "attributes": [],
}
CARD_ENTRY = {
    "title": "Übergabe vorbereiten",
    "subline": "Board Projekt",
    "resourceUrl": f"{BASE}/index.php/apps/deck/card/57",
    "attributes": [],
}
TALK_ENTRY = {
    "title": "Khaled",
    "subline": "Budget passt",
    "resourceUrl": f"{BASE}/index.php/call/abc123#message_42",
    "attributes": [],
}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_every_installed_provider_is_asked_and_the_list_comes_from_the_instance(
    clients: NcClients,
) -> None:
    """The provider landscape depends on installed apps, so it is never hardcoded."""
    with respx.mock(assert_all_called=True) as mock:
        providers = mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=provider_list())
        )
        files = mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        notes = mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )
        deck = mock.get(search_url("search-deck-card-board")).mock(
            return_value=httpx.Response(200, json=hits("Deck", [CARD_ENTRY]))
        )
        talk = mock.get(search_url("spreed")).mock(
            return_value=httpx.Response(200, json=hits("Talk", [TALK_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="budget")

    assert providers.call_count == 1
    for route in (files, notes, deck, talk):
        assert route.call_count == 1, "every installed provider is asked exactly once"
        assert route.calls[0].request.url.params["term"] == "budget"
        assert route.calls[0].request.headers["OCS-APIRequest"] == "true"

    assert result["query"] == "budget"
    assert result["count"] == 5
    assert "degraded" not in result
    assert result["note"] == search_tools.SEARCH_NOTE

    by_id = {hit["id"]: hit for hit in result["results"]}
    assert set(by_id) == {
        "file:4711",
        "file:4712",
        "note:12",
        "card:57",
        f"url:{BASE}/index.php/call/abc123#message_42",
    }
    assert by_id["file:4711"] == {
        "id": "file:4711",
        "title": "Budget 2026.md",
        "subline": "in Dokumente",
        "url": f"{BASE}/index.php/f/4711",
        "provider": "files",
        "kind": "file",
    }


@pytest.mark.anyio
async def test_a_hit_that_cannot_be_resolved_later_says_so(clients: NcClients) -> None:
    """Short card ids and url ids are honest about their limits; a file id is not marked."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(
                200, json=provider_list("files", "search-deck-card-board", "spreed")
            )
        )
        mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        mock.get(search_url("search-deck-card-board")).mock(
            return_value=httpx.Response(200, json=hits("Deck", [CARD_ENTRY]))
        )
        mock.get(search_url("spreed")).mock(
            return_value=httpx.Response(200, json=hits("Talk", [TALK_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="budget")

    by_id = {hit["id"]: hit for hit in result["results"]}
    assert by_id["card:57"]["resolvable"] is False, "the provider knows no board and no stack"
    assert by_id[f"url:{BASE}/index.php/call/abc123#message_42"]["resolvable"] is False
    assert by_id[f"url:{BASE}/index.php/call/abc123#message_42"]["kind"] == "url"
    assert "resolvable" not in by_id["file:4711"], "a file id resolves, so it costs no field"


@pytest.mark.anyio
async def test_an_empty_term_never_reaches_nextcloud(clients: NcClients) -> None:
    """Unified search answers an empty term with 400 "No valid filters provided"."""
    with respx.mock(assert_all_called=False) as mock:
        providers = mock.get(PROVIDERS_URL)

        with pytest.raises(ToolError, match="empty") as excinfo:
            await search_tools.unified_search(clients, query="   ")

    assert providers.call_count == 0
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_failing_provider_is_degraded_and_the_others_still_answer(
    clients: NcClients,
) -> None:
    """A removed app can leave a provider behind that answers 500 (gotcha from plan 06)."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=provider_list("files", "notes"))
        )
        mock.get(search_url("files")).mock(return_value=httpx.Response(500, text="boom"))
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="protokoll")

    assert [hit["id"] for hit in result["results"]] == ["note:12"]
    assert result["count"] == 1
    assert len(result["degraded"]) == 1
    assert result["degraded"][0]["provider"] == "files"
    assert "500" in result["degraded"][0]["reason"]
    assert SECRET not in json.dumps(result), "a reason names the provider, never a credential"


@pytest.mark.anyio
async def test_a_slow_provider_is_cut_off_and_marked_degraded(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One stalling provider must not hold the whole answer hostage (threat T-01-71)."""
    monkeypatch.setattr(search_tools, "PER_PROVIDER_TIMEOUT", 0.05)

    async def never_answers(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, json=hits("Files", []))

    # assert_all_called stays off: the cancelled request never completes, so respx never
    # records it as a call. That is exactly the behaviour under test.
    with respx.mock(assert_all_called=False) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=provider_list("files", "notes"))
        )
        mock.get(search_url("files")).mock(side_effect=never_answers)
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="protokoll")

    assert [hit["id"] for hit in result["results"]] == ["note:12"]
    assert result["degraded"] == [
        {"provider": "files", "reason": "The provider did not answer within 0.05 seconds."}
    ]


@pytest.mark.anyio
async def test_an_entry_without_a_usable_reference_is_skipped_and_counted(
    clients: NcClients,
) -> None:
    """Skipping beats guessing, and the count keeps the omission visible."""
    broken = {"title": "kaputt", "subline": "", "attributes": []}
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("notes")))
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [broken, NOTE_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="protokoll")

    assert [hit["id"] for hit in result["results"]] == ["note:12"]
    assert result["skipped"] == 1


@pytest.mark.anyio
async def test_a_search_without_a_hit_is_an_empty_list_and_not_an_error(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("files")))
        mock.get(search_url("files")).mock(return_value=httpx.Response(200, json=hits("Files", [])))

        result = await search_tools.unified_search(clients, query="gibtesnicht")

    assert result["results"] == []
    assert result["count"] == 0
    assert result["query"] == "gibtesnicht"
    assert "degraded" not in result


@pytest.mark.anyio
async def test_the_providers_parameter_restricts_the_fan_out(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list()))
        files = mock.get(search_url("files"))
        notes = mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="protokoll", providers="notes")

    assert notes.call_count == 1
    assert files.call_count == 0, "a restricted search must not ask the other providers"
    assert result["count"] == 1


@pytest.mark.anyio
async def test_an_unknown_requested_provider_is_reported_as_degraded(clients: NcClients) -> None:
    """A typo must never look like "nothing found" (must-have: no silent partial result)."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list()))
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        result = await search_tools.unified_search(
            clients, query="protokoll", providers=["notes", "gibtsnicht"]
        )

    assert result["count"] == 1
    assert result["degraded"] == [
        {"provider": "gibtsnicht", "reason": "This Nextcloud has no search provider with that id."}
    ]


@pytest.mark.anyio
async def test_only_unknown_providers_give_an_empty_result_with_a_reason(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list()))

        result = await search_tools.unified_search(
            clients, query="protokoll", providers="gibtsnicht"
        )

    assert result["results"] == []
    assert len(result["degraded"]) == 1


@pytest.mark.anyio
async def test_an_instance_without_any_provider_is_an_error_with_a_way_out(
    clients: NcClients,
) -> None:
    """Zero providers is not zero hits: the answer would be a lie the model repeats."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=envelope([])))

        with pytest.raises(ToolError, match="no search provider") as excinfo:
            await search_tools.unified_search(clients, query="protokoll")

    assert excinfo.value.hint


@pytest.mark.anyio
async def test_the_limit_is_capped_and_the_server_cursor_is_reported(clients: NcClients) -> None:
    """The limit goes to OCS, which caps it again; the cursor comes back unchanged."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("files")))
        files = mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )

        result = await search_tools.unified_search(clients, query="budget", limit=500)

    assert files.calls[0].request.url.params["limit"] == str(search_tools.MAX_LIMIT)
    assert result["cursors"] == {"files": 25}


@pytest.mark.anyio
async def test_a_foreign_resource_url_never_leaves_the_configured_instance(
    clients: NcClients,
) -> None:
    """resourceUrl is parsed, never fetched, and never returned as a foreign link."""
    stolen = {**NOTE_ENTRY, "resourceUrl": "http://evil.test/index.php/apps/notes/note/12"}
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("notes")))
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [stolen]))
        )

        result = await search_tools.unified_search(clients, query="protokoll")

    assert result["results"][0]["url"] == f"{BASE}/index.php/apps/notes/note/12"


@pytest.mark.anyio
async def test_the_provider_list_is_read_again_on_the_next_call(clients: NcClients) -> None:
    """An app installed a minute ago has to show up without restarting this server."""
    with respx.mock(assert_all_called=True) as mock:
        providers = mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=provider_list("notes"))
        )
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        await search_tools.unified_search(clients, query="protokoll")
        await search_tools.unified_search(clients, query="protokoll")

    assert providers.call_count == 2, "no cached provider list, not even for one process"


FINDLING_ENTRY = {
    "title": "Kuendigung-Lagerflaeche.docx",
    "subline": "... die Kuendigungsfrist betraegt drei Monate ...",
    "resourceUrl": f"{BASE}/index.php/f/9917",
    "attributes": [],
}


def providers_with_findling() -> dict[str, Any]:
    """The runtime list of an instance that carries a content provider (BL-15)."""
    payload = provider_list("files")
    payload["ocs"]["data"].append({"id": "findling", "name": "Findling", "order": 60})
    return payload


@pytest.mark.anyio
async def test_the_note_admits_content_hits_when_findling_answered(clients: NcClients) -> None:
    """BL-15: the note describes the answer in hand, not the installation.

    The day a content provider answers, the blanket sentence "file contents are not
    indexed" becomes a lie in the direction pitfall 5 guards against: a model that
    believes it distrusts a correct content hit. So an answer a content provider
    contributed to has to say so, and the old sentence must not appear in it.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=providers_with_findling())
        )
        mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        mock.get(search_url("findling")).mock(
            return_value=httpx.Response(200, json=hits("Findling", [FINDLING_ENTRY]))
        )

        result = await search_tools.unified_search(clients, query="budget")

    assert result["note"] == (
        "matched on names, metadata and file contents; findling searched inside documents"
    )
    assert "not indexed" not in result["note"]


@pytest.mark.anyio
async def test_the_note_stays_conservative_when_the_content_provider_broke(
    clients: NcClients,
) -> None:
    """A degraded content provider contributed nothing, so the old sentence is the truth."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=providers_with_findling())
        )
        mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        mock.get(search_url("findling")).mock(return_value=httpx.Response(500))

        result = await search_tools.unified_search(clients, query="budget")

    assert result["note"] == search_tools.SEARCH_NOTE
    assert result["degraded"][0]["provider"] == "findling"
