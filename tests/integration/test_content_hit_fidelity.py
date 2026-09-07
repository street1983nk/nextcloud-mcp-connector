"""The content-hit permission promise, measured with Findling installed (BL-02).

``tests/integration/test_permission_fidelity_exapp.py`` proves that no tool leaks a foreign
object over the full ExApp chain. Every one of its search cases can be answered from names
and metadata alone, because the stock providers of a bare Nextcloud do not index file
contents. This file asks the harder question that the Findling synergy claim rests on: when
a search provider answers from the INSIDE of documents, does the permission boundary still
hold behind this connector's impersonation?

    MCP client  ->  HaRP  ->  ExApp  ->  impersonation  ->  unified search  ->  Findling
                                                            (ACL prefilter + PHP recheck)

The claim under test, word for word from .planning/BACKLOG.md BL-02: the assistant sees
exactly what the asking user may see, down to hits that exist only because of document
content. The steps, in one test because the indexed state is expensive to build and the
order is the argument:

1. Guard: alice and bob are two different accounts (a shared identity proves nothing).
2. alice uploads a document whose unique marker exists ONLY in the content; the file name
   is asserted to carry no trace of it, so a later hit cannot be a name hit.
3. Positive control: alice finds the document over ``unified_search`` restricted to the
   ``findling`` provider, and the marker stands in the excerpt (subline), which is cut from
   the indexed content. Without this half, bob's empty answer below would also pass on a
   broken index.
4. Leak test: bob, asking the same provider the same marker, gets an empty result, and the
   provider is asserted to have ANSWERED (no degradation entry), so "empty because broken"
   cannot pass for "empty because enforced".

Findling indexes through Nextcloud background jobs, so the positive half drives the cron
endpoint and polls with a deadline instead of hoping for timing. One-word queries are
answered by Findling's lexical index only (its 06.1-20 operator rule), which is exactly
right here: BL-02 measures permission fidelity of content hits, not embedding quality.

The file skips, with the reason named, when the ``findling`` provider is not installed on
the test instance, so the default integration run stays green without the extra topology.

Run it against the running HaRP topology with Findling installed::

    export HP_SHARED_KEY="$(openssl rand -hex 32)"
    docker compose -p nc-mcp-exapp -f compose.exapp.yml up -d --wait
    bash scripts/bootstrap_exapp.sh
    bash scripts/install_findling.sh          # PHP half + backend over the AppAPI daemon
    set -a && . ./.env.exapp && set +a
    uv run pytest tests/integration/test_content_hit_fidelity.py -m integration -q
"""

import base64
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

# The app id is frozen (docs/app-id-freeze.md); the HaRP route never changes.
EXAPP_MCP_PATH = "/exapps/mcp_connector/mcp"

# Findling's provider id, from its PHP half (SearchProvider::getId). A rename over there
# would surface here as a skip, which is the honest failure shape for a foreign id.
FINDLING_PROVIDER = "findling"

# How long the positive half may take. Findling needs a crawl round and an index round of
# the background jobs, driven below through the cron endpoint; five minutes is generous on
# a warm topology and still ends a broken index run with a named failure.
INDEX_DEADLINE_SECONDS = float(os.environ.get("NC_MCP_FINDLING_DEADLINE") or "300")

# One cron drive plus one query per round; the sleep keeps the loop polite.
_POLL_PAUSE_SECONDS = 5.0


def _basic(user: str, secret: str) -> str:
    """A Basic header, exactly what a client hands to HaRP; HaRP resolves the identity."""
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


@asynccontextmanager
async def _mcp_session(base: str, user: str, secret: str) -> AsyncIterator[Client]:
    """An MCP session over Streamable HTTP against the ExApp, authenticated as one user."""
    url = base.rstrip("/") + EXAPP_MCP_PATH
    async with httpx2.AsyncClient(
        headers={"Authorization": _basic(user, secret)},
        timeout=httpx2.Timeout(30.0, read=300.0),
    ) as http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with Client(transport) as client:
            yield client


def _texts(result: Any) -> list[str]:
    return [c.text for c in result.content if getattr(c, "text", None) is not None]


def _payload(result: Any) -> dict[str, Any]:
    """Decode the compact JSON a tool answers with (structured_output=False)."""
    assert not result.is_error, f"the tool call ended in an error: {_texts(result)!r}"
    texts = _texts(result)
    assert texts, f"the tool answered without any text content: {result!r}"
    data = json.loads(texts[0])
    assert isinstance(data, dict), f"the tool did not answer with an object: {data!r}"
    return data


@pytest.fixture
def chain_env() -> dict[str, str]:
    """The values scripts/bootstrap_exapp.sh writes into .env.exapp for the full chain test.

    Same shape and same skip behaviour as the sibling fidelity file, so the default run
    stays green without the topology and names what is missing.
    """
    required = {
        "base": "NC_MCP_URL",
        "app_id": "APP_ID",
        "alice": "NC_MCP_TEST_USER",
        "alice_pw": "NC_MCP_TEST_APP_PASSWORD",
        "bob": "NC_MCP_TEST_USER2",
        "bob_pw": "NC_MCP_TEST_APP_PASSWORD2",
    }
    values = {key: (os.environ.get(name) or "").strip() for key, name in required.items()}
    missing = sorted(required[key] for key, value in values.items() if not value)
    if missing:
        pytest.skip(f"no ExApp topology configured (missing: {', '.join(missing)})")
    assert values["app_id"] == "mcp_connector", (
        f"the app id is frozen as mcp_connector but APP_ID is {values['app_id']!r}"
    )
    assert values["alice"] != "admin", "the chain test runs as normal users, never as admin"
    return values


async def _findling_answers(client: Client, query: str) -> dict[str, Any]:
    """Ask unified_search for the one provider this file is about."""
    return _payload(
        await client.call_tool("unified_search", {"query": query, "providers": FINDLING_PROVIDER})
    )


def _findling_degradation(payload: dict[str, Any]) -> str | None:
    """The reason Findling did not answer, or None when it answered."""
    for entry in payload.get("degraded") or []:
        if entry.get("provider") == FINDLING_PROVIDER:
            return str(entry.get("reason") or "an unnamed degradation")
    return None


async def _drive_cron(base: str) -> None:
    """One round of Nextcloud background jobs, the way webcron drives them.

    Findling's crawl and index run as background jobs. The test instance may sit on AJAX
    cron, where jobs only run while somebody uses the web interface, so the loop below
    drives them explicitly instead of depending on that somebody.
    """
    async with httpx2.AsyncClient(timeout=httpx2.Timeout(30.0, read=120.0)) as web:
        answer = await web.get(base.rstrip("/") + "/cron.php")
        assert answer.status_code == 200, (
            f"the cron endpoint answered {answer.status_code}; without background jobs "
            "Findling never indexes and this test would time out for the wrong reason"
        )


async def test_a_content_hit_reaches_alice_and_never_bob(chain_env: dict[str, str]) -> None:
    """BL-02: the content-level permission fidelity of the Findling synergy, measured."""
    base = chain_env["base"]

    # 1. Guard: two accounts, or every negative below is empty theatre.
    assert chain_env["alice"] != chain_env["bob"], (
        "the negative proof needs two accounts; NC_MCP_TEST_USER2 points at the same user"
    )
    assert chain_env["alice_pw"] != chain_env["bob_pw"], (
        "both accounts carry the same app password; the chain would resolve the same identity"
    )

    marker = f"inhaltsmarker{uuid.uuid4().hex[:10]}"
    file_path = f"/besprechungsnotiz-{uuid.uuid4().hex[:8]}.md"
    # 2. The marker lives only in the content. Asserted, not assumed: a marker that leaked
    #    into the name would turn every hit below into a name hit and prove nothing.
    assert marker not in file_path, "the file name must not carry the content marker"

    # Skip guard before any content exists: a missing provider is a topology property,
    # not a finding about permissions. The skip is raised outside the MCP session, because
    # inside it the task group of the transport wraps the Skipped exception into an
    # exception group and pytest loses the reason.
    async with _mcp_session(base, chain_env["alice"], chain_env["alice_pw"]) as alice:
        probe = await _findling_answers(alice, "findlingprobe")
    degraded = _findling_degradation(probe)
    if degraded is not None:
        pytest.skip(f"the findling provider is not usable on this instance: {degraded}")

    async with _mcp_session(base, chain_env["alice"], chain_env["alice_pw"]) as alice:
        uploaded = _payload(
            await alice.call_tool(
                "files_upload",
                {
                    "path": file_path,
                    "content": (
                        "Notiz zur Besprechung.\n\n"
                        f"Der vertrauliche Inhalt traegt die Kennung {marker} und steht in "
                        "keinem Dateinamen.\n"
                    ),
                },
            )
        )
        assert uploaded.get("path") == file_path, f"alice's upload did not land: {uploaded!r}"

        # 3. Positive control: drive the background jobs and poll until the content hit
        #    arrives, with a deadline so a broken index fails loudly instead of hanging.
        deadline = time.monotonic() + INDEX_DEADLINE_SECONDS
        answer: dict[str, Any] = {}
        while True:
            await _drive_cron(base)
            answer = await _findling_answers(alice, marker)
            assert _findling_degradation(answer) is None, (
                f"the findling provider degraded during indexing: {answer!r}"
            )
            if answer["count"] >= 1:
                break
            if time.monotonic() >= deadline:
                pytest.fail(
                    f"alice's content hit did not arrive within {INDEX_DEADLINE_SECONDS:g}s; "
                    f"last answer: {answer!r}"
                )
            await anyio.sleep(_POLL_PAUSE_SECONDS)

        hits = [hit for hit in answer["results"] if hit.get("provider") == FINDLING_PROVIDER]
        assert hits, f"the hit did not come from the findling provider: {answer!r}"
        # The proof that this is a content hit and not a name hit: no title carries the
        # marker (the name never did), and at least one excerpt does, because the excerpt
        # is cut from the indexed content.
        assert all(marker not in hit.get("title", "") for hit in hits), (
            f"a title carries the marker, so this would be a name hit: {hits!r}"
        )
        assert any(marker in hit.get("subline", "") for hit in hits), (
            f"no excerpt carries the marker, so the hit is not proven to be content: {hits!r}"
        )

    # 4. Leak test: same marker, same provider, bob's identity. The provider has to have
    #    ANSWERED emptily; a degradation entry would mean "empty because broken" and must
    #    not pass for an enforced boundary.
    async with _mcp_session(base, chain_env["bob"], chain_env["bob_pw"]) as bob:
        foreign = await _findling_answers(bob, marker)

    assert _findling_degradation(foreign) is None, (
        f"the findling provider did not answer for bob, so his empty result proves "
        f"nothing: {foreign!r}"
    )
    assert foreign["results"] == [], (
        f"findling leaked alice's content hit to bob over the chain: {foreign!r}"
    )
    assert foreign["count"] == 0
