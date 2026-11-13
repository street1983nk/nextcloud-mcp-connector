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

**A hit that carries a file passes the sandbox and the tag (EXCL-03, SBX-01).** Every
provider counts, not only files: Findling, comments and notes hits name their file by id
only, so that id is resolved into a path when the sandbox or a tagged folder needs it
(:func:`_screen`). A sandbox drop is counted in ``skipped``; a ``kein-ki`` drop leaves no
trace at all. When the exclusion check cannot be answered, every file-bearing hit is held
back and ``degraded`` names that once.

**A hit of a shared task list names nobody (D-32-17).** The provider ``tasks`` writes the
display name of the list into the subline, and for a shared list that name ends with its
owner. Such a subline is held back, compared with the task discovery of the account (one
PROPFIND per call, only when such a hit exists) and passed on without the owner; when that is
not certain, the hit keeps id, title and link and loses only its subline.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from .. import ids, provider_map
from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav, ocs
from ..nextcloud.clients import talk as talk_client
from ..nextcloud.clients import tasks as tasks_client
from ..nextcloud.exclusion import TagScope
from . import talk as talk_tools
from . import withhold

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

#: The Talk message providers, classified by measurement and not by guess. The live probe
#: of plan 27-03 (``.planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/
#: 27-03-provider-probe.txt``, nc35 with Nextcloud 35.0.0 and spreed 25.0.0) shared a file
#: into a conversation and searched for its name and its stem: neither provider answered
#: with a single entry (``KLASSE=kein-leak``), while a plain text message was found with
#: title "<actor> in <conversation>", its text as subline and a ``/call/<token>#message_<id>``
#: link (``UNTERSCHEIDUNG=keine``). Their hits therefore carry no file and are treated as
#: not file-bearing in the sense of :func:`withhold.file_refs`. That probe only shared a file
#: *into* an ordinary room, though: a message *written in* the conversation Talk opens for a
#: file (the Files sidebar chat) carries that conversation, and so the file name, in its
#: title. Their hits are therefore decided against the conversation list exactly like the
#: conversation hits below (review CR-01 of phase 28, the rule of D-28-21).
_FILE_SHARE_PROVIDERS = ("talk-message", "talk-message-current")

#: The Talk conversation provider. Its hit is a conversation, and the conversation Talk opens
#: for a file carries the file name as its name: the canary of plan 28-10 found the tagged
#: file name in ``unified_search``, ``prepare_context`` and ``search`` through it, in the
#: normal state and in the outage (``raw/28-10-befund-diagnose.txt``, nc35). Its hits are
#: therefore decided against the conversation list like ``talk_browse`` does (D-28-21).
_CONVERSATIONS_PROVIDER = "talk-conversations"

#: Every provider whose hit names a conversation, through its title and its ``/call/<token>``
#: link, and is therefore screened with the room rule of :func:`_screen_conversations`.
_ROOM_SCREENED_PROVIDERS = frozenset({_CONVERSATIONS_PROVIDER, *_FILE_SHARE_PROVIDERS})

_ROOM_LIST_REASON = "The conversation list could not be read, so conversation hits are withheld."


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

    # The guard is the first member of its own, outside every provider timeout (pattern 6):
    # a provider that runs into its 15 s must never cancel the flight the others wait on.
    scope_out, *outcomes = await asyncio.gather(
        clients.exclusion.scope(clients),
        *(_ask(clients, provider_id, term, capped) for provider_id in selected),
        return_exceptions=True,
    )
    if isinstance(scope_out, BaseException):
        raise scope_out
    if not isinstance(scope_out, TagScope):
        raise TypeError("the exclusion guard answered without a scope")
    scope = scope_out

    screened: list[tuple[str, _Screened]] = []
    cursors: dict[str, Any] = {}
    skipped = 0
    withheld = False
    for provider_id, outcome in zip(selected, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            degraded.append({"provider": provider_id, "reason": _reason(outcome)})
            continue
        if not isinstance(outcome, dict):
            continue
        raw_entries = outcome.get("entries")
        part = _screen(
            clients, provider_id, raw_entries if isinstance(raw_entries, list) else [], scope
        )
        screened.append((provider_id, part))
        skipped += part.skipped
        withheld = withheld or part.withheld
        cursor = outcome.get("cursor")
        if cursor is not None and cursor != "":
            cursors[provider_id] = cursor

    withheld = await _screen_conversations(clients, screened, scope, degraded) or withheld

    paths, lookup_failed = await _resolve(
        clients, {fid for _, part in screened for fid in part.pending}
    )
    withheld = withheld or lookup_failed

    results: list[dict[str, Any]] = []
    held: list[tuple[dict[str, Any], str]] = []
    for provider_id, part in screened:
        kept, dropped = _settle(part.kept, paths, lookup_failed, scope)
        skipped += dropped
        hits, unusable = _normalise(clients, provider_id, kept, held)
        results.extend(hits)
        skipped += unusable
    await _clean_task_sublines(clients, held)

    if withheld:
        degraded.append(withhold.degraded_entry("provider"))

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


@dataclass(slots=True)
class _Screened:
    """What :func:`_screen` made of one provider answer.

    ``kept`` are the entries still in the race, each with its file reference; ``pending``
    the file ids that have to be resolved into paths before they are decided; ``skipped``
    the counted drops (unusable or outside the sandbox); ``withheld`` whether an entry was
    held back because the exclusion check could not be answered.
    """

    kept: list[tuple[dict[str, Any], withhold.FileRef]] = field(default_factory=list)
    pending: set[str] = field(default_factory=set)
    skipped: int = 0
    withheld: bool = False


def _screen(clients: NcClients, provider_id: str, entries: list[Any], scope: TagScope) -> _Screened:
    """Decide every entry of one provider as far as the entry itself allows.

    The order is fixed, because every step that speaks has to come before the ones that
    stay silent (D-27-04): a sandbox drop may be counted, it says nothing about a tag.

    1. Not an object: unusable, counted.
    2. Carries no file (calendar, deck, contacts, a talk message, a systemtags tag entry):
       kept, no tag can apply to it.
    3. The exclusion check could not be answered: withheld silently, and the answer gets
       one ``exclusion`` entry in ``degraded`` (D-27-03).
    4. A plain ``attributes.path``: outside ``NC_MCP_FILES_ROOT`` it is a sandbox drop,
       counted. The files provider sends this path relative to the home; so does the
       file entry of the systemtags provider.
    5. Neither a usable path nor a file id: unusable, counted.
    6. Only a file id (Findling, comments, notes) and the path matters, because a sandbox
       is set or a folder is tagged: the id is queued for one lookup of all providers.
       Before phase 27 such an entry passed the sandbox unchecked, because only the files
       provider was expected to carry a path (SBX-01, SBX-02).
    7. Otherwise kept; the tag stage in :func:`_settle` decides it by its file id.
    """
    screened = _Screened()
    resolve = scope.state != "unverifiable" and withhold.needs_paths(scope)
    base_url = clients.creds.base_url
    for entry in entries:
        if not isinstance(entry, dict):
            screened.skipped += 1
            continue
        ref = withhold.file_refs(base_url, provider_id, entry)
        if provider_id in _FILE_SHARE_PROVIDERS or not ref.file_bearing:
            screened.kept.append((entry, withhold.FileRef(None, None, file_bearing=False)))
            continue
        if scope.state == "unverifiable":
            screened.withheld = True
            continue
        if ref.path is not None:
            if not dav.in_files_root(ref.path):
                screened.skipped += 1
                continue
        elif ref.fileid is None:
            screened.skipped += 1
            continue
        elif resolve:
            screened.pending.add(ref.fileid)
        screened.kept.append((entry, ref))
    return screened


def _conversation_token(entry: dict[str, Any]) -> str | None:
    """The token of one conversation or message hit, read from its ``/call/<token>`` link.

    A message hit links ``/call/<token>#message_<id>``; the fragment is not part of the path.
    """
    try:
        segments = httpx.URL(str(entry.get("resourceUrl") or "")).path.split("/")
    except (httpx.InvalidURL, ValueError):
        return None
    for index, segment in enumerate(segments[:-1]):
        if segment == "call" and segments[index + 1]:
            return segments[index + 1]
    return None


async def _screen_conversations(
    clients: NcClients,
    screened: list[tuple[str, _Screened]],
    scope: TagScope,
    degraded: list[dict[str, str]],
) -> bool:
    """Drop the file conversations the tag hides; ``True`` means the check could not answer.

    The same rule as ``talk_browse`` (D-28-21, ``talk.room_fileid``): a conversation whose
    ``objectType`` is ``file`` stands for that file. A tagged one leaves silently (D-27-04);
    when the check cannot be answered, every file conversation is held back and the caller
    names that once in ``degraded``. A conversation without a file stays. A hit whose token
    is not in the list of this account resolves to the id ``"-"``, which no file carries, and
    is withheld whenever anything is tagged (fail-closed). The message providers follow the
    same rule by the conversation their hit was written in (review CR-01 of phase 28).

    The list is read only when there are such hits and something is tagged, so every other
    search costs no request more. The guard answers from the scope of this call: no second
    REPORT. A list that cannot be read withholds the conversation hits under their provider.
    """
    named = [
        (provider_id, part)
        for provider_id, part in screened
        if provider_id in _ROOM_SCREENED_PROVIDERS
    ]
    parts = [part for _, part in named]
    if scope.state == "untagged" or not any(part.kept for part in parts):
        return False
    try:
        rooms = await talk_client.get_rooms(
            clients.client, clients.creds, include_last_message=False
        )
    except (ToolError, httpx.HTTPError):
        for provider_id, part in named:
            if part.kept:
                degraded.append({"provider": provider_id, "reason": _ROOM_LIST_REASON})
            part.kept.clear()
        return False

    by_token = {
        str(room.get("token") or ""): talk_tools.room_fileid(room)
        for room in rooms
        if isinstance(room, dict)
    }
    fileid_of = {
        id(entry): by_token.get(_conversation_token(entry) or "", "-")
        for part in parts
        for entry, _ in part.kept
    }
    screen = await talk_tools.file_screen(
        clients, (), room_fileids=[fileid for fileid in fileid_of.values() if fileid]
    )
    for part in parts:
        part.kept[:] = [
            (entry, ref)
            for entry, ref in part.kept
            if not ((fileid := fileid_of[id(entry)]) and screen.hides_room(fileid))
        ]
    return screen.unavailable


async def _resolve(clients: NcClients, fileids: set[str]) -> tuple[dict[str, str], bool]:
    """Resolve the queued file ids with one lookup; ``True`` means the lookup itself failed.

    A failed lookup is "could not check", never "not found" (fail-closed): the caller
    withholds every queued entry and names the check in ``degraded``.
    """
    if not fileids:
        return {}, False
    try:
        return await dav.paths_of_fileids(clients.client, clients.creds, sorted(fileids)), False
    except (ToolError, httpx.HTTPError, ValueError):
        return {}, True


def _settle(
    kept: list[tuple[dict[str, Any], withhold.FileRef]],
    paths: dict[str, str],
    lookup_failed: bool,
    scope: TagScope,
) -> tuple[list[dict[str, Any]], int]:
    """Apply the resolved paths and then the tag, returning the survivors and the count.

    A queued id that did not come back lies outside the sandbox or is gone: a sandbox
    drop, counted. A queued id after a failed lookup is withheld silently; the caller
    names that once in ``degraded``. A tagged entry disappears without any counter
    (D-27-04, D-v1.7-02).
    """
    survivors: list[dict[str, Any]] = []
    counted = 0
    queued = scope.state != "unverifiable" and withhold.needs_paths(scope)
    for entry, ref in kept:
        if not ref.file_bearing:
            survivors.append(entry)
            continue
        path = ref.path
        if path is None and ref.fileid is not None and queued:
            if lookup_failed:
                continue
            if ref.fileid not in paths:
                counted += 1
                continue
            path = paths[ref.fileid]
        if scope.state == "active" and scope.excludes(path=path, fileid=ref.fileid):
            continue
        survivors.append(entry)
    return survivors, counted


def _normalise(
    clients: NcClients,
    provider_id: str,
    entries: list[dict[str, Any]],
    held: list[tuple[dict[str, Any], str]],
) -> tuple[list[dict[str, Any]], int]:
    """Turn the surviving entries of one provider into compact hits, counting the unusable.

    The subline of a task from a shared list goes into ``held`` instead of the hit; the same
    test as the link of :func:`provider_map.hit_url` decides what is shared (D-32-17).
    """
    hits: list[dict[str, Any]] = []
    skipped = 0
    for entry in entries:
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
        raw_url = provider_map.absolute_url(clients.creds.base_url, entry.get("resourceUrl"))
        if subline and kind == "task" and ids.SHARED_BY_MARKER in raw_url:
            held.append((hit, subline))
        elif subline:
            hit["subline"] = subline
        hit["url"] = provider_map.hit_url(clients.creds.base_url, kind, identifier, entry)
        hit["provider"] = provider_id
        hit["kind"] = kind
        if not canonical:
            # The honest half of pitfall 10: this id needs a lookup or cannot be fetched.
            hit["resolvable"] = False
        hits.append(hit)
    return hits, skipped


async def _clean_task_sublines(clients: NcClients, held: list[tuple[dict[str, Any], str]]) -> None:
    """Give each held task hit its subline without the owner, or none at all (D-32-17).

    One discovery for all of them, and none when nothing is held. The discovery is the one
    of ``tasks_search``, without a budget of its own. Any failure of it only costs these
    sublines: the hits stay, the call does not fail, and nothing is added to ``degraded``.
    """
    if not held:
        return
    try:
        lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    except (ToolError, httpx.HTTPError, TimeoutError):
        return
    by_key = {task_list.key: task_list for task_list in lists}
    for hit, subline in held:
        try:
            kind, parts = ids.parse(str(hit["id"]))
        except ToolError:
            continue
        task_list = by_key.get(parts[0]) if kind == "task" and parts else None
        cleaned = tasks_client.clean_subline(subline, task_list) if task_list else None
        if cleaned:
            ordered = {"id": hit.pop("id"), "title": hit.pop("title"), "subline": cleaned}
            ordered.update(hit)
            hit.clear()
            hit.update(ordered)


def _reason(exc: BaseException) -> str:
    """One sentence per failed provider: what happened, never who we are."""
    if isinstance(exc, ToolError):
        return exc.message
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return f"The provider did not answer within {PER_PROVIDER_TIMEOUT:g} seconds."
    if isinstance(exc, httpx.RequestError):
        return "The provider could not be reached."
    raise exc
