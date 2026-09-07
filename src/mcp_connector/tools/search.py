"""Cloud wide search over every installed search provider (D-08, TOOL-06).

The permission check is not ours. Nextcloud runs each provider in the context of the
authenticated user and returns only what that user may see, which is why this tool keeps
no index and caches nothing (threat T-01-70). Our job is the fan-out and the honesty.

Four properties are contract, not implementation detail.

**The provider list is read at runtime.** It depends on the installed apps, so hardcoding
it would either miss an app or invent one. It is fetched per call, without a cache: an app
enabled a minute ago must be searchable without restarting this server.

**The fan-out is parallel and bounded.** ``asyncio.gather(return_exceptions=True)`` plus a
hard timeout per provider means one stalling app costs seconds, not the whole answer
(threat T-01-71). Every provider that fails or stalls appears under ``degraded`` with its
name and a reason, so a partial answer is always labelled as one.

**Every hit carries an id or admits that it does not.** Files hits become ``file:<id>``,
notes ``note:<id>``, deck cards the short ``card:<cardId>`` form, and everything else
``url:<absolute-url>``. The last two are marked ``resolvable: false``, because neither can
be handed to a read tool as it stands (pitfall 10).

**The expectation is managed in the answer.** ``note`` says out loud what this answer
matched: names and metadata only, or file contents too, when a content provider such as
findling answered (BL-15). Without it a model concludes "the document does not exist"
from a search that never looked inside a single file, or distrusts a real content hit
because the payload claims contents are not indexed (pitfall 5, both directions).
"""

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx

from .. import provider_map
from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import ocs

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

#: Wall clock budget for one provider. Nextcloud's own unified search runs providers in
#: parallel in the web UI for the same reason: one slow app is normal, a slow answer is not.
PER_PROVIDER_TIMEOUT = 15.0

#: One sentence against a whole class of wrong model statements (pitfall 5). Until
#: 2026-09-07 it was unconditional and became false the day a content provider was
#: installed (BL-15): findling answers with real content hits, scanned PDFs included,
#: and this very sentence taught the model to distrust them. The note now describes
#: the answer in hand, not the installation: this constant stays the truth for an
#: answer no content provider contributed to, and :func:`_note` builds the truth for
#: the other case. Ships with release 0.1.12.
SEARCH_NOTE = "matched on names and metadata; file contents are not indexed"

#: The providers that search inside file contents. Grown by proof and never by guess:
#: a name enters this set when the content hit fidelity test of BL-02
#: (tests/integration/test_content_hit_fidelity.py) has seen it answer with a content
#: hit behind this connector's impersonation and with bob's empty counter proof.
CONTENT_PROVIDERS = frozenset({"findling"})

_TERM_HINT = (
    "Give at least one word, for example 'budget'. Nextcloud rejects a search without a "
    "term. Whether words inside documents are found depends on the installed providers; "
    "the note of every answer says what this search actually matched."
)

_UNKNOWN_PROVIDER_REASON = "This Nextcloud has no search provider with that id."


async def unified_search(
    clients: NcClients,
    query: str,
    limit: int = DEFAULT_LIMIT,
    providers: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Search the whole Nextcloud and return compact, normalised hits."""
    term = (query or "").strip()
    if not term:
        raise ToolError(message="The search term is empty.", hint=_TERM_HINT)

    # A limit outside the range is capped instead of refused: the model asked a legitimate
    # question with an unhelpful number, and an error would only cost a round trip.
    capped = min(max(limit, 1), MAX_LIMIT)

    installed = [
        str(provider.get("id"))
        for provider in await ocs.list_search_providers(clients.client, clients.creds)
        if provider.get("id")
    ]
    if not installed:
        raise ToolError(
            message="This Nextcloud reports no search provider at all.",
            hint=(
                "Zero providers is a server side problem, not an empty result. Ask an "
                "administrator to check the unified search of that instance."
            ),
        )

    degraded: list[dict[str, str]] = []
    selected = _select(installed, providers, degraded)

    outcomes = await asyncio.gather(
        *(_ask(clients, provider_id, term, capped) for provider_id in selected),
        return_exceptions=True,
    )

    results: list[dict[str, Any]] = []
    cursors: dict[str, Any] = {}
    skipped = 0
    for provider_id, outcome in zip(selected, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            degraded.append({"provider": provider_id, "reason": _reason(outcome)})
            continue
        hits, unusable = _normalise(clients, provider_id, outcome)
        results.extend(hits)
        skipped += unusable
        cursor = outcome.get("cursor")
        if cursor is not None and cursor != "":
            cursors[provider_id] = cursor

    result: dict[str, Any] = {
        "query": term,
        "count": len(results),
        "results": results,
        "note": _note(selected, degraded),
    }
    if degraded:
        result["degraded"] = degraded
    if cursors:
        result["cursors"] = cursors
    if skipped:
        # Named, not swallowed: "some hits were unusable" is a sentence the model can pass
        # on, a shorter list without a word about it is not.
        result["skipped"] = skipped
    return result


def _note(selected: Sequence[str], degraded: list[dict[str, str]]) -> str:
    """The sentence a model may trust, about this answer and not about the instance.

    A content provider that was asked and answered makes the answer include content
    hits, so the old blanket sentence would be a lie in exactly the direction pitfall
    5 guards against. A content provider that is installed but degraded contributed
    nothing, so for that answer the conservative sentence stays the honest one.
    """
    broken = {item["provider"] for item in degraded}
    content = sorted(name for name in selected if name in CONTENT_PROVIDERS and name not in broken)
    if not content:
        return SEARCH_NOTE
    return (
        "matched on names, metadata and file contents; "
        + " and ".join(content)
        + " searched inside documents"
    )


def _select(
    installed: list[str],
    providers: str | Sequence[str] | None,
    degraded: list[dict[str, str]],
) -> list[str]:
    """Return the providers to ask, and record every requested name that does not exist.

    An unknown name is a degradation and never an error: the other providers still have
    real answers, and an empty result without a reason is the one outcome a model
    misreports as "nothing found".
    """
    wanted = _wanted(providers)
    if not wanted:
        return installed

    known = set(installed)
    degraded.extend(
        {"provider": name, "reason": _UNKNOWN_PROVIDER_REASON}
        for name in wanted
        if name not in known
    )
    return [name for name in installed if name in set(wanted)]


def _wanted(providers: str | Sequence[str] | None) -> list[str]:
    """Accept ``"files,notes"`` from the tool layer and a list from Python callers."""
    if providers is None:
        return []
    names = providers.split(",") if isinstance(providers, str) else list(providers)
    seen: list[str] = []
    for raw in names:
        name = str(raw).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


async def _ask(clients: NcClients, provider_id: str, term: str, limit: int) -> dict[str, Any]:
    async with asyncio.timeout(PER_PROVIDER_TIMEOUT):
        return await ocs.provider_search(clients.client, clients.creds, provider_id, term, limit)


def _normalise(
    clients: NcClients, provider_id: str, payload: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Turn one provider answer into compact hits, counting the unusable entries."""
    raw_entries = payload.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []

    hits: list[dict[str, Any]] = []
    skipped = 0
    for entry in entries:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        resolved = provider_map.extract_id(provider_id, entry, clients.creds.base_url)
        if resolved is None:
            skipped += 1
            continue

        kind, identifier, canonical = resolved
        hit: dict[str, Any] = {
            "id": identifier,
            "title": str(entry.get("title") or ""),
        }
        subline = str(entry.get("subline") or "")
        if subline:
            hit["subline"] = subline
        hit["url"] = provider_map.hit_url(clients.creds.base_url, kind, identifier, entry)
        hit["provider"] = provider_id
        hit["kind"] = kind
        if not canonical:
            # The honest half of pitfall 10: this id needs a lookup or cannot be fetched.
            hit["resolvable"] = False
        hits.append(hit)
    return hits, skipped


def _reason(exc: BaseException) -> str:
    """One sentence per failed provider: what happened, never who we are."""
    if isinstance(exc, ToolError):
        return exc.message
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return f"The provider did not answer within {PER_PROVIDER_TIMEOUT:g} seconds."
    if isinstance(exc, httpx.RequestError):
        return "The provider could not be reached."
    raise exc
