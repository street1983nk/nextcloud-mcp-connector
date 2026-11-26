"""The exclusion guard core: is anything tagged ``kein-ki``, and if so, what (EXCL-02, EXCL-04).

This module turns the two calls of ``clients.systemtags`` into one value, a :class:`TagScope`,
and holds the policy the client deliberately does not know. It withholds nothing itself and
shapes no message; the tool layer of phase 27 does that with the value it gets from here.

Why three states and not a boolean (EXCL-04): "nothing is tagged" and "the question could not
be answered" must never collapse into the same value. ``untagged`` leaves every answer exactly
as it was, ``active`` carries the tagged set, and ``unverifiable`` carries a reason code and
refuses to be read as "allowed": :meth:`TagScope.excludes` raises in that state, so a caller
cannot filter with it by accident.

Why the REPORT outcome decides and not the ``systemtags`` capability (D-25-05): on Nextcloud
32 to 34 the capability is cached in APCu and wrong in both directions for a while after the
app is switched. The answer to the question itself is the only one that counts: 207 is a set,
412 means the id went stale and is looked up exactly once more, everything else is
``unverifiable``.

Why the tagged set is never cached beyond one call and only name to id is (E3, EXCL-02): a
tag added a second ago has to take effect on the next call, so the set is asked for anew by
every guard instance, and a guard lives exactly as long as one tool call. What survives is the
mapping from the tag name to its ids, per ``(base_url, user, account)``, positive results only: an
account without the tag lists again on every call, so a freshly created tag is never hidden
behind a cached "nothing". The key carries the user because visibility differs: an admin sees
restricted and invisible tags that alice does not, and an admin id handed to alice would only
ever answer 412.

Why one REPORT per spelling: Nextcloud intersects several ``oc:systemtag`` rules in one REPORT
(``array_uintersect``), so two ids in one body ask for "carries both", which silently answers
"nothing" for a node carrying only one of them. Each distinct exact spelling of the name
therefore gets its own REPORT with exactly one id, and the sets are united.

How to read success criterion 2 ("exactly one REPORT per tool call"): per tool call, that is
per guard instance, there is exactly one flight however many parts ask concurrently. Within
it one REPORT goes out per distinct spelling, which on any Nextcloud from 32 on is one unless
old duplicates exist, none goes out when nothing is tagged, plus at most the one re-listing
after a 412.

Known limit: on SQLite with about 140k tag assignments the REPORT takes longer than
``TAG_BUDGET``, so the guard is ``unverifiable`` there by construction (documented in phase 29).

What this module does not have, on purpose: no admin switch and no second path list (D-26-01,
D-26-02), and no configurable tag name. The name is ``kein-ki``, compared case-insensitively
after trimming blanks, and nothing else.
"""

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import httpx

from ..errors import ToolError
from .clients import systemtags

if TYPE_CHECKING:
    # Annotations only: ``NcClients`` carries a guard of this module as a field, so a
    # runtime import here would be a cycle (the package imports this module first).
    from . import NcClients

__all__ = [
    "EXCLUDE_TAG",
    "TAG_BUDGET",
    "TTL_SECONDS",
    "UNTAGGED",
    "ExclusionGuard",
    "State",
    "TagScope",
    "Why",
    "ancestors",
    "clear_cache",
    "exclude_tag_ids",
    "is_exclude_name",
    "load_scope",
]

EXCLUDE_TAG = "kein-ki"

#: Lifetime of a name-to-id entry in seconds. Nextcloud from 32 on refuses to create a second
#: spelling that differs only in case, so a new spelling can only appear through direct
#: database access; this is the longest it stays unseen (assumption A4 of phase 25).
TTL_SECONDS = 60.0

#: The whole flight (listing, REPORTs, one re-listing) has this many seconds. It covers the
#: measured SQLite worst case of 5000 hits (8.1 to 10.6 s) with room to spare, and both ways
#: of being wrong about it end fail-closed: too short is ``unverifiable``, never ``untagged``.
TAG_BUDGET = 15.0

type State = Literal["untagged", "active", "unverifiable"]

#: Internal reason codes of the ``unverifiable`` state. They are not error reasons of the
#: tool contract (``errors.REASONS`` stays frozen); phase 27 decides what the model reads.
type Why = Literal["timeout", "unreachable", "status", "stale_twice", "unparsable", "foreign_href"]

#: (base_url, user, account) -> (stored_at, one id per distinct spelling). Positive only.
_tag_ids: dict[tuple[str, str, str], tuple[float, tuple[str, ...]]] = {}


def clear_cache() -> None:
    """Drop every entry. Safe at any time, by construction (D-20)."""
    _tag_ids.clear()


def _cached_ids(key: tuple[str, str, str]) -> tuple[str, ...] | None:
    """The ids stored for ``key`` if the entry is younger than ``TTL_SECONDS``."""
    cached = _tag_ids.get(key)
    if cached is not None and time.monotonic() - cached[0] < TTL_SECONDS:
        return cached[1]
    return None


def _store_ids(key: tuple[str, str, str], ids: tuple[str, ...]) -> None:
    """Remember ``ids`` for ``key``, but never an empty result (a new tag must show at once)."""
    if ids:
        _tag_ids[key] = (time.monotonic(), ids)


def _drop_ids(key: tuple[str, str, str]) -> None:
    """Forget the ids of ``key``; a 412 has just shown them stale."""
    _tag_ids.pop(key, None)


def is_exclude_name(name: str) -> bool:
    """Whether ``name`` spells the exclusion tag, ignoring case and surrounding blanks."""
    return name.strip().casefold() == EXCLUDE_TAG


def exclude_tag_ids(tags: Iterable[systemtags.Tag]) -> tuple[str, ...]:
    """One id per distinct exact spelling of the tag name, sorted by number.

    The spelling is kept exactly as listed, because Nextcloud looks tags up by their exact
    name and already unites tags of identical name there; per spelling the numerically
    lowest id stands for it.
    """
    lowest: dict[str, int] = {}
    for tag in tags:
        if not is_exclude_name(tag.name):
            continue
        number = int(tag.id)
        if tag.name not in lowest or number < lowest[tag.name]:
            lowest[tag.name] = number
    return tuple(str(number) for number in sorted(lowest.values()))


def ancestors(path: str) -> tuple[str, ...]:
    """The path itself and every parent up to ``/``, nearest first.

    ``a in tagged for a in ancestors(p)`` draws the same boundary as ``dav.within(p, t)`` for
    every tagged ``t``, which the unit tests prove; the set lookup only makes it cheap.
    """
    result = [path]
    while path not in ("", "/"):
        path = path.rsplit("/", 1)[0] or "/"
        result.append(path)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class TagScope:
    """The answer to "what is tagged ``kein-ki``" for one tool call, as a value.

    ``has_folders`` says whether a folder is among the tagged nodes. Without a tagged
    folder the file id alone decides, so a family can skip resolving ids into paths
    when nothing but files carries the tag (and the sandbox is off).
    """

    state: State
    paths: frozenset[str] = frozenset()
    fileids: frozenset[str] = frozenset()
    has_folders: bool = False
    reason: Why | None = None

    def excludes(self, path: str | None = None, fileid: str | None = None) -> bool:
        """Whether the node at ``path`` or with ``fileid`` has to be withheld.

        ``path`` is an absolute home path as dav entries carry it, not the virtual view
        inside ``NC_MCP_FILES_ROOT``. In the ``unverifiable`` state this raises instead of
        answering, so "could not check" can never be read as "allowed". In the ``active``
        state a misuse raises as well instead of silently allowing: asking about nothing
        (both arguments ``None``) and a relative path would otherwise never match anything,
        and a caller that pulls its values from the wrong keys would filter nothing, ever.
        Only ``untagged`` keeps answering ``False`` unconditionally: that state excludes
        nothing whatever the question, so no misuse can open a way past a tag.
        """
        if self.state == "unverifiable":
            raise ValueError(
                "the exclusion scope is unverifiable; the caller must withhold, not ask"
            )
        if self.state == "untagged":
            return False
        if path is None and fileid is None:
            raise ValueError("excludes needs a path or a fileid; asking nothing is not allowed")
        if path is not None and not path.startswith("/"):
            raise ValueError(f"excludes takes an absolute home path, got {path!r}")
        if fileid is not None and fileid in self.fileids:
            return True
        return path is not None and any(a in self.paths for a in ancestors(path))


#: The one value every "nothing is tagged" answer shares. Immutable, so not module state.
UNTAGGED = TagScope("untagged")


def _unverifiable(reason: Why) -> TagScope:
    return TagScope("unverifiable", reason=reason)


async def load_scope(clients: "NcClients") -> TagScope:
    """Ask Nextcloud what is tagged ``kein-ki`` for this user and return it as a value.

    Every Nextcloud outcome ends in one of the three states and nothing raises for it: the
    whole flight runs under ``TAG_BUDGET``, and a timeout, a transport failure, an
    unparsable body or data that cannot be what Nextcloud sends all become
    ``unverifiable`` with their reason. A cancellation is deliberately not caught: it is not
    an answer and must never be stored as one.
    """
    try:
        async with asyncio.timeout(TAG_BUDGET):
            return await _flight(clients)
    except TimeoutError:
        return _unverifiable("timeout")
    # The httpx timeouts are HTTPErrors as well, so they have to be told apart first.
    except httpx.TimeoutException:
        return _unverifiable("timeout")
    except httpx.HTTPError:
        return _unverifiable("unreachable")
    except ToolError:
        return _unverifiable("unparsable")
    except ValueError:
        return _unverifiable("unparsable")


async def _fresh_ids(clients: "NcClients", key: tuple[str, str, str]) -> tuple[str, ...] | TagScope:
    """List the tags and return one id per spelling, or the state the listing already decides."""
    listing = await systemtags.list_tags(clients.client, clients.creds)
    if listing.status != 207:
        return _unverifiable("status")
    ids = exclude_tag_ids(listing.tags)
    if not ids:
        return UNTAGGED
    _store_ids(key, ids)
    return ids


async def _flight(clients: "NcClients") -> TagScope:
    """The D-25-05 automaton: 207 is a set, one 412 re-lists once, anything else is a refusal."""
    key = clients.creds.identity_key
    ids = _cached_ids(key)
    if ids is None:
        fresh = await _fresh_ids(clients, key)
        if isinstance(fresh, TagScope):
            return fresh
        ids = fresh

    first = await _report_all(clients, ids)
    statuses = {answer.status for answer in first}
    if statuses == {207}:
        return _active(first)
    if not statuses <= {207, 412}:
        return _unverifiable("status")

    # At least one id went stale: forget the ids, list exactly once more, ask again.
    _drop_ids(key)
    fresh = await _fresh_ids(clients, key)
    if isinstance(fresh, TagScope):
        return fresh
    second = await _report_all(clients, fresh)
    statuses = {answer.status for answer in second}
    if statuses == {207}:
        return _active(second)
    if statuses <= {207, 412}:
        # Stale right after a fresh listing; keep nothing that is known to be stale.
        _drop_ids(key)
        return _unverifiable("stale_twice")
    return _unverifiable("status")


async def _report_all(clients: "NcClients", ids: tuple[str, ...]) -> list[systemtags.TaggedSet]:
    """One REPORT per id, each with exactly that one id, all at once.

    Every request is allowed to finish before the first failure is raised again, so the
    mapping in :func:`load_scope` never runs while a sibling request is still in flight.
    """
    answers = await asyncio.gather(
        *(systemtags.tagged_nodes(clients.client, clients.creds, tag_id) for tag_id in ids),
        return_exceptions=True,
    )
    sets: list[systemtags.TaggedSet] = []
    for answer in answers:
        if isinstance(answer, BaseException):
            raise answer
        sets.append(answer)
    return sets


def _active(sets: Iterable[systemtags.TaggedSet]) -> TagScope:
    """Unite every set; a single href that did not map makes the whole answer unverifiable.

    The set is not narrowed to ``NC_MCP_FILES_ROOT``: a tagged folder above the sandbox has
    to cover everything below it.
    """
    paths: set[str] = set()
    fileids: set[str] = set()
    has_folders = False
    for tagged in sets:
        for node in tagged.nodes:
            if node.path is None:
                return _unverifiable("foreign_href")
            paths.add(node.path)
            fileids.add(node.fileid)
            has_folders = has_folders or node.is_collection
    return TagScope(
        "active",
        paths=frozenset(paths),
        fileids=frozenset(fileids),
        has_folders=has_folders,
    )


class ExclusionGuard:
    """One flight per tool call: the first caller asks, every concurrent caller shares it.

    One instance belongs to one tool call and dies with it, so the tagged set never
    outlives the call (E3). The constructor takes nothing, which lets phase 27 hang a
    ``field(default_factory=ExclusionGuard)`` onto ``NcClients``.

    An ``unverifiable`` scope is stored like any other: whoever waited shares the failure,
    not the cost. A cancelled flight stores nothing, so the next caller starts a new one;
    that only doubles the cost and stays fail-closed.

    One instance serves exactly one ``(base_url, user, account)``: the first call binds the guard to
    that identity, and a later call with a different one raises instead of handing out the
    scope of a foreign account. The docstring contract alone would rely on the discipline of
    phase 27, and the guard core protects itself against exactly that everywhere else.
    """

    __slots__ = ("_key", "_lock", "_scope")

    def __init__(self) -> None:
        # Created here, not on first use, like the lock of ``oauth.jwks.KeySet``.
        self._lock = asyncio.Lock()
        self._scope: TagScope | None = None
        self._key: tuple[str, str, str] | None = None

    async def scope(self, clients: "NcClients") -> TagScope:
        """The scope of this tool call, asked for at most once however many parts need it."""
        # The identity check runs before the fast path on purpose: a cached scope must never
        # be handed to a caller with different credentials. No await sits between check and
        # bind, so two concurrent first calls cannot interleave here.
        key = clients.creds.identity_key
        if self._key is None:
            self._key = key
        elif self._key != key:
            raise ValueError("one ExclusionGuard serves exactly one (base_url, user, account)")
        known = self._scope
        if known is not None:
            # The fast path takes no lock; nothing is awaited between check and return.
            return known
        async with self._lock:
            # Re-check under the lock: whoever waited takes the outcome of the flight that
            # just finished instead of starting a second one (single-flight).
            known = self._scope
            if known is None:
                known = await load_scope(clients)
                self._scope = known
            return known
