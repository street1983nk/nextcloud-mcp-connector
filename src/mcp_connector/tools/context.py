"""One bundle for one question: ``prepare_context`` (D-52 to D-57, TOOL-08, CTX-01).

This tool owns no data source. It composes the fan-outs that already exist, and every
property that makes it trustworthy comes from that decision.

**Four ways, by the kind of question.** Content comes from the unified search, appointments
from the calendar with a computed window, what is waiting from the conversation list of
Talk, and how much is unread from the mailbox list of Mail: "this week" is not a full text
question, and a bundle without the next appointments misses its purpose (D-52).

**The Talk digest costs one request.** The conversation list carries ``unread``,
``unread_mention``, ``unread_mention_direct``, ``last_activity`` and the preview of the last
message in one answer, so the digest is a projection of that one read and never a walk over
conversations (CTX-01). It is asked through :mod:`mcp_connector.tools.talk` and not through a
client of its own, which is what makes it inherit the marker filter and the sorting rule of
that module instead of building either a second time.

**The mail counters cost one account list plus N mailbox lists.** Literally: 1 account list
plus N mailbox lists (N at most :data:`MAX_MAIL_ACCOUNTS`), plus the detection requests of a
cold cache, because ``mail_tools.browse`` asks ``capabilities.require_app("mail")`` first and
Mail is the one optional app that is recognised through the navigation of the signed in
account instead of through the capabilities document. Two of those belong to this leg, and a
whole bundle pays **three** on a cold cache, because the Talk leg starts at the same moment
and races this one for the same empty cache entry, so the capabilities document is fetched
twice. Every one of them lives in one cache entry for ``capabilities.TTL_SECONDS`` seconds
afterwards, so a second bundle inside a minute pays none of them again: three cold, zero
warm, measured on 2026-08-24 (see ``11-06-MEASUREMENTS.md``). This paragraph is measured and
not estimated, and the third request is exactly what that difference is worth: the estimate
said two.

**The counters are numbers, and nothing anybody wrote.** No subject, no sender, no message
body and no mailbox name beyond the role: a counter is what CTX-02 asks for, and a subject in
the standard bundle would be the cheapest reach extension this project has to give away,
foreign text from somebody who needs no account on this Nextcloud to write it. The counters
come from the mailbox list of each account and never from the ``unread`` field of the
navigation entry of the Mail app: that field was measured as 0 while six messages were
unread, and while the meaning of the field stays unclear, the measurement does not.

**The keys ``talk`` and ``mail`` are always there, and always lists.** A key that appears
only sometimes would depend on foreign text. An empty list without an entry under
``degraded`` means "nothing is waiting"; an empty list with one means "this could not be
read". The two statements stay distinguishable, because a model that reads the first where
the second is true reports that there are no messages.

**The search is asked without a provider restriction.** Naming ``files,notes,deck`` here
would lock out an installed Findling and every future provider, and with it the one side
effect that carries D-53: the provider list is read at runtime, so a newly installed search
app is part of the bundle without a line of code here. Hits are grouped by their ``kind``
and never by the provider id, because the Deck provider is called
``search-deck-card-board`` and a grouping by name would silently never see a card.

**The grouping stays at three named kinds.** Since TOOL-16 a Talk message and a Tables table
are resolvable hits, and they are still grouped with the rest instead of getting a bucket of
their own. The reason is not economy: the Talk digest of this bundle is its one statement
about that app, and two statements about the same app in one answer, a bucket and a digest,
would leave a model to decide which of them is the truth. What a hit says about itself is
therefore the only source of ``resolvable`` (:func:`_short`), and what this server reads
unasked is a list of its own (:data:`EXCERPT_KINDS`).

**Each source has its own budget, the bundle has none.** A global ``asyncio.timeout``
around the ``gather`` would throw away the answer that was already finished, so every
source carries its own ceiling and a source that misses it becomes a named entry under
``degraded``. The wall clock of the whole call is therefore the maximum of the parts, not
their sum.

**A shortened answer says that it is shortened.** Buckets are capped for predictable
tokens (D-54), and every cap writes its own ``degraded`` entry: a list that is quietly five
entries long is the one outcome a model reports as "that is everything" (SC 4).

**Foreign text stays data (D-57).** A hit carries its origin as fields (``id``,
``provider``, ``kind``), never as prose, and an excerpt is a plain data field. Nothing in
this module frames a hit as an instruction or as a wish of the user. There is no content
filtering and no masking: masking is security theatre, the defence here is structure and
labelling.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ..errors import ToolError
from ..nextcloud import NcClients
from . import calendar as calendar_tools
from . import chatgpt as chatgpt_tools
from . import mail as mail_tools
from . import marks
from . import search as search_tools
from . import talk as talk_tools

#: Hits requested from the search. Wider than any single bucket cap on purpose: the
#: grouping below can only distribute what it was given.
SEARCH_LIMIT = 25

#: "This week" without a schema field. The window is named in the answer, so the model
#: knows which days it is talking about (D-56: no budget parameter, no window parameter).
WINDOW_DAYS = 7

#: Own, tighter ceiling for the calendar leg. ``calendar.PER_CALENDAR_TIMEOUT`` is 20 s and
#: right for the standalone tool, but one stalling collection would fill the budget of the
#: whole bundle alone (pitfall 5). The cap belongs here; ``calendar.py`` stays untouched.
#:
#: Measured on the live topology on 2026-08-17 (plan 04-04, live proof 5, one MCP session
#: over client, proxy, HaRP, container and Nextcloud): ``detail="short"`` answered in
#: **0.84 s**, ``detail="full"`` with three excerpts in **0.99 s**, both with an empty
#: ``degraded`` list. That closes assumption A2 of 04-RESEARCH from the other side: the
#: healthy case is two orders of magnitude away from the thirty seconds a client grants, so
#: these budgets only ever bite when a source is actually stalling, which is what they are
#: for.
#:
#: Measured again on 2026-08-24 with four legs (Nextcloud 34.0.3, mail 5.11.1, spreed 24.0.4,
#: tables 2.2.2, three runs of three calls each): this leg alone answered in a median of
#: **0.07 s to 0.08 s**, a factor of more than 100 below this ceiling, and the whole bundle
#: stayed at a median of 0.65 s to 1.13 s short and 0.85 s to 1.83 s full. Unchanged at 10.0:
#: a ceiling that never bites in the healthy case is doing its job.
#: Reproduce with the command in 11-06-MEASUREMENTS.md.
CALENDAR_BUDGET = 10.0

#: Token predictability over completeness (D-54): five hits per kind are enough for a model
#: to decide what to load, and the sixth costs every session that never needed it. Both caps
#: are named in ``degraded`` when they bite, so "five" is never mistaken for "all".
MAX_PER_BUCKET = 5
MAX_EVENTS = 10

#: Own ceiling for the Talk leg. Tighter than the calendar on purpose: the digest is **one**
#: request against one route, where the calendar fans out over every collection of the
#: account, so five seconds are already generous for it.
#:
#: Measured on 2026-08-24 on the live topology (Nextcloud 34.0.3, spreed 24.0.4, three runs of
#: three calls each, one account with five conversations): this leg answered in a median of
#: **0.04 s**, a factor of about 130 below this ceiling, and it is the fastest of the four.
#: Unchanged at 5.0: the number was a setting until this line, and the measurement says the
#: setting was right. Reproduce with the command in 11-06-MEASUREMENTS.md.
TALK_BUDGET = 5.0

#: CTX-01, literally: at most three conversations reach the digest. The fourth costs every
#: session that never needed it, and the cap names itself under ``degraded`` when it bites,
#: so "three" is never mistaken for "all".
MAX_DIGEST = 3

#: Upper bound of one preview inside the digest, in **bytes**. CTX-01 says "~200 characters",
#: and this is the one place where the wording is not followed to the letter: this project
#: budgets in bytes everywhere (``MAX_MESSAGE_BYTES``, ``EXCERPT_MAX_BYTES``), a German
#: preview with umlauts is fewer characters than bytes rather than the other way round, and
#: the cheaper connection is the byte cut with tolerant decoding that ``talk.py`` already
#: makes. Hence the name ``..._BYTES`` and not ``..._CHARS``: the unit is part of the promise.
DIGEST_PREVIEW_BYTES = 200

#: Own ceiling for the Mail leg. Wider than the Talk budget on purpose, and the reason is the
#: shape of the leg rather than the speed of the app: the digest is **one** request against one
#: route, while this leg is 1 plus N, one account list plus one mailbox list per account, and N
#: belongs to the account of a stranger.
#:
#: Measured on 2026-08-24 on the live topology (Nextcloud 34.0.3, mail 5.11.1, three runs of
#: three calls each, one mail account with one mailbox, so N is 1): this leg answered in a
#: median of **0.06 s**, a factor of about 150 below this ceiling. Unchanged at 10.0, and the
#: width stays justified by the shape rather than by this number: N is one on the measured
#: instance and may be :data:`MAX_MAIL_ACCOUNTS` on somebody else's.
#: Reproduce with the command in 11-06-MEASUREMENTS.md.
MAIL_BUDGET = 10.0

#: How many mail accounts of an account reach the counters, and the cap is the point rather
#: than the number: without it the wall clock of every bundle call hangs on how many mail
#: accounts somebody else set up, and a tool whose answer time a user can extend by adding an
#: account is a tool a client aborts. Three, like :data:`MAX_DIGEST`, and the cap writes its
#: own ``degraded`` entry with the total, so "three" is never mistaken for "all".
#:
#: Measured on 2026-08-24 on the live topology: the account of the measurement owns **one**
#: mail account, so the cap did not bite and the leg cost 1 account list plus **1** mailbox
#: list, both on a cold and on a warm cache. Unchanged at 3, and the measurement is a lower
#: bound rather than a confirmation: this instance cannot tell what three accounts cost, which
#: is why the number keeps its reasoning above and does not lean on this line.
#: Reproduce with the command in 11-06-MEASUREMENTS.md.
MAX_MAIL_ACCOUNTS = 3

#: The three kinds this answer groups by name. Everything else lands in one bucket together,
#: and since TOOL-16 that bucket is no longer the same thing as "cannot be read": a Talk
#: message and a Tables table are resolvable and stay in there anyway, for the reason named
#: in the module docstring.
KIND_BUCKETS = ("file", "note", "card")
OTHER_BUCKET = "other"
BUCKETS = (*KIND_BUCKETS, OTHER_BUCKET)

#: How much of a document reaches the answer in the full form. Three excerpts of two
#: kilobytes each are a paragraph of context per source, not a document dump: the model
#: decides from them whether it is worth calling ``fetch`` for the whole text (D-54).
MAX_EXCERPTS = 3
EXCERPT_MAX_BYTES = 2000

#: What the reader is allowed to transfer for one excerpt (LO-06). Without it a hit read up
#: to ``files.DEFAULT_MAX_BYTES``, 512 kilobytes, to keep two of them: at ``detail="full"``
#: up to 1.5 megabytes of Nextcloud transfer per bundle call, bounded in time by
#: :data:`EXCERPT_TIMEOUT` and in volume not at all. Twice the ceiling and not exactly the
#: ceiling, because the cap counts encoded bytes after decoding and a read that ends inside
#: a multi byte character loses that character: the wider window makes the excerpt byte for
#: byte the one a full read produced, and still saves the factor.
EXCERPT_READ_BYTES = EXCERPT_MAX_BYTES * 2

#: Own budget per excerpt, for the same reason the calendar has one: three reads that
#: cannot be finished must cost three sentences under ``degraded``, never the bundle.
EXCERPT_TIMEOUT = 5.0

#: Which kinds this server opens unasked at ``detail="full"``. The same three names as
#: :data:`KIND_BUCKETS` today, and a tuple of its own on purpose: that one groups the answer,
#: this one decides whose content is read without anybody asking for it. A mail body and a
#: chat message are the texts an outsider can place into this account most easily, so the
#: reach of the excerpts is a decision with a name instead of a side effect of a decision
#: about buckets (T-11-24).
EXCERPT_KINDS = ("file", "note", "card")

#: Marked inside the text and not only beside it, exactly as ``chatgpt.fetch`` does it: a
#: model that only reads the excerpt must still be able to tell it from a whole document.
#: Defined in :mod:`mcp_connector.tools.marks` together with the filter that keeps the
#: sequence this server's own (BL-09, ME-03), and re-exported here under its own name.
EXCERPT_TRUNCATION = marks.EXCERPT_TRUNCATION

SHORT = "short"
FULL = "full"
DETAILS = (SHORT, FULL)

_DETAIL_HINT = f"Use detail={SHORT!r} for titles and ids, or detail={FULL!r} to add excerpts."

_QUERY_HINT = (
    "Give at least one word, for example 'budget'. Without a term the search has nothing "
    "to match and the window has nothing to be about."
)


async def prepare_context(clients: NcClients, query: str, detail: str = SHORT) -> dict[str, Any]:
    """Bundle the hits, the upcoming appointments, the digest and the counters for one question.

    Four legs, four ceilings, one wall clock: the cost of the two composed legs is one request
    for the digest and, for the counters, 1 account list plus N mailbox lists (N at most
    :data:`MAX_MAIL_ACCOUNTS`), plus the detection requests of a cold cache, measured as three
    for a whole bundle and zero inside ``capabilities.TTL_SECONDS`` afterwards
    (``11-06-MEASUREMENTS.md``).
    """
    term = (query or "").strip()
    if not term:
        raise ToolError(message="The query is empty.", hint=_QUERY_HINT)

    mode = (detail or "").strip().lower() or SHORT
    if mode not in DETAILS:
        raise ToolError(message=f"{detail!r} is not a known detail level.", hint=_DETAIL_HINT)

    start, end = _window()
    search_out, calendar_out, talk_out, mail_out = await asyncio.gather(
        search_tools.unified_search(clients, query=term, limit=SEARCH_LIMIT),
        _events(clients, start, end),
        _talk(clients),
        _mail(clients),
        return_exceptions=True,
    )

    degraded: list[dict[str, str]] = []
    results = _bundle(_hits(search_out, degraded), degraded)
    events = _schedule(calendar_out, degraded)
    talk = _digest(talk_out, degraded)
    mail = _counters(mail_out, degraded)

    # The rule names the search and the calendar and neither of the two composed legs, and
    # that is a decision rather than an oversight: a bundle in which only Talk answered is not
    # a success, and a bundle without Talk or without Mail on an instance without either is
    # not a failure. A leg added later belongs under ``degraded`` and not into this condition.
    if isinstance(search_out, BaseException) and isinstance(calendar_out, BaseException):
        # Neither source answered. An empty bundle here would be read as "there is
        # nothing", which is the one statement this situation does not support.
        raise ToolError(
            message="Neither the search nor the calendar could be read.",
            hint="; ".join(item["reason"] for item in degraded),
        )

    if mode == FULL:
        await _excerpts(clients, results, degraded)

    result: dict[str, Any] = {
        "query": term,
        "window": {"start": start, "end": end},
        "events": events,
        "results": results,
        "talk": talk,
        "mail": mail,
    }
    if degraded:
        result["degraded"] = degraded
    # The note travels from the inner search answer, so it stays true the day a content
    # provider answers (BL-15). When the search leg itself failed, nothing in this bundle
    # is a content hit and the conservative sentence is the honest one.
    result["note"] = (
        search_out.get("note", search_tools.SEARCH_NOTE)
        if isinstance(search_out, dict)
        else search_tools.SEARCH_NOTE
    )
    return result


def _window() -> tuple[str, str]:
    """Now until now plus a week, in UTC and in the form the calendar tool parses."""
    now = datetime.now(UTC).replace(microsecond=0)
    return now.isoformat(), (now + timedelta(days=WINDOW_DAYS)).isoformat()


async def _events(clients: NcClients, start: str, end: str) -> dict[str, Any]:
    """The calendar leg, under the ceiling of this tool instead of the one of that tool."""
    async with asyncio.timeout(CALENDAR_BUDGET):
        return await calendar_tools.list_events(clients, start=start, end=end, limit=MAX_EVENTS)


async def _talk(clients: NcClients) -> dict[str, Any]:
    """The conversation list, under the ceiling of this tool and through the tool layer."""
    async with asyncio.timeout(TALK_BUDGET):
        return await talk_tools.browse(
            clients, level="conversations", limit=talk_tools.MAX_CONVERSATIONS
        )


async def _mail(clients: NcClients) -> dict[str, Any]:
    """The unread counters of the mail accounts, under one ceiling and through the tool layer.

    The cost is 1 plus N: one account list, then one mailbox list per account, plus up to two
    detection requests on a cold cache, because ``mail_tools.browse`` asks
    ``capabilities.require_app("mail")`` first and Mail is recognised through the navigation of
    the signed in account (``capabilities.TTL_SECONDS`` is how long both answers are reused).
    Two is this leg's own share; a whole bundle was measured at three, because the Talk leg
    races this one for the same empty cache entry and the capabilities document goes out twice
    (2026-08-24, ``11-06-MEASUREMENTS.md``). Measured on this instance: 1 account list plus 1
    mailbox list for one account, identical cold and warm.

    The mailbox lists run in an inner ``gather`` under the same outer ceiling. A sequential
    round over three accounts would be three times the time of one, and the rule of this module
    is "wall clock equals the maximum of the parts, never their sum".

    Both calls ask for ``mail_tools.MAX_LIMIT`` because both lists are capped in the envelope
    of that tool, at 20 without a limit: an account with more than twenty folders can lose its
    inbox when the inbox is not near the front. The account list is asked the same way for the
    same reason, and :data:`MAX_MAIL_ACCOUNTS` is far below that ceiling, so the cut over the
    **kept** accounts is always this module's own. The ceiling of the tool layer itself can
    still bite, at 50, and a cut this leg did not make must not become a silent one (review
    finding WR-02): the ``truncated`` flag of the account envelope travels onwards as
    ``accounts_truncated``, the one of a cut mailbox list as ``boxes_truncated`` on the
    account that lost its inbox to it, and :func:`_counters` turns both into sentences
    instead of a wrong "has no inbox" or an understated total.

    ``account_id`` is explicit for every single mailbox list, never the first account of the
    list and never a default: "the first account of the list is not the account somebody
    meant", which is the sentence ``mail_tools._mailboxes`` refuses without one for.

    What this leg does **not** ask for is the point of it: no message level, no subject, no
    sender, no body. CTX-02 asks for numbers, and foreign text in the standard bundle is text
    from somebody who needed no account here to write it.

    The counters come from the mailbox list of every account. The ``unread`` field of the
    navigation entry of the Mail app is **not** read and must not be: it was measured as 0
    while six messages were unread, and a counter that reads 0 when something is waiting is
    worse than no counter at all.
    """
    async with asyncio.timeout(MAIL_BUDGET):
        listed = await mail_tools.browse(clients, level="accounts", limit=mail_tools.MAX_LIMIT)
        # An account without a usable number is dropped rather than asked about: a mailbox
        # list for the account 0 would be a request about an account nobody has. It is the
        # same decision ``mail_tools._messages`` makes for an envelope without a database id.
        accounts = [item for item in _entries(listed) if _count(item.get("id")) > 0]
        kept = accounts[:MAX_MAIL_ACCOUNTS]
        # The order of the app is the order of the user. Sorting here would be a statement
        # about which of somebody's mail accounts matters more, and this module has nothing
        # to base such a statement on.
        boxes = await asyncio.gather(
            *(
                mail_tools.browse(
                    clients,
                    level="mailboxes",
                    account_id=str(_count(account.get("id"))),
                    limit=mail_tools.MAX_LIMIT,
                )
                for account in kept
            )
        )
    return {
        "results": [_counter(account, answer) for account, answer in zip(kept, boxes, strict=True)],
        "total": len(accounts),
        "accounts_truncated": bool(listed.get("truncated")),
    }


def _counter(account: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """One account as its number, its address and the counter of its inbox.

    ``inbox_unread`` appears only when a mailbox with the inbox role is actually in the list.
    Reporting a missing inbox as 0 would be a number that looks like a measurement and is
    none; the missing field plus the sentence :func:`_counters` writes for it are the honest
    pair.

    A missing inbox has two different reasons with two different sentences, and this is where
    they are told apart (review finding WR-02): when the mailbox list arrived ``truncated``
    from the envelope of the tool layer, the inbox may simply be behind that cut, so the entry
    carries ``boxes_truncated`` for :func:`_counters` to read, and "has no mailbox with the
    inbox role" would be a claim this leg cannot make. The flag is internal to this leg and
    never reaches the answer: :func:`_counters` pops it.

    The role is read with ``get`` and not with an index, because ``mail_tools._special_role``
    answers the number zero with an empty string and leaves the field out entirely, so an
    ``entry["special_role"]`` would raise on an ordinary mailbox without a role.
    """
    entry: dict[str, Any] = {
        "account_id": _count(account.get("id")),
        "email": str(account.get("email") or ""),
    }
    inbox = next(
        (box for box in _entries(answer) if box.get("special_role") == "inbox"),
        None,
    )
    if inbox is not None:
        entry["inbox_unread"] = _count(inbox.get("unread"))
    elif answer.get("truncated"):
        entry["boxes_truncated"] = True
    return entry


def _counters(
    outcome: dict[str, Any] | BaseException, degraded: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """The counters of the accounts, or nothing plus one sentence about why.

    A failure of this leg, and that includes an instance without Mail, is exactly one entry
    under ``degraded`` and an empty list. The missing app arrives as a ``ToolError`` from
    ``capabilities.require_app``, so it takes the first branch of :func:`_reason` and keeps the
    sentence of that layer instead of getting a second one here.

    An empty account list is a success with zero accounts and explicitly **not** the same
    statement as a missing Mail app: one is answered by setting up an account in Mail, the
    other by asking an administrator, and neither of them writes an entry that claims the
    counters could not be read.

    Four caps of this leg name themselves, each with a number: the account cap of this
    module, every account whose inbox is not in its mailbox list, and the two envelope cuts
    of the tool layer that :func:`_mail` carries onwards as flags (review finding WR-02). A
    cut account list makes ``total`` a lower bound and says so; a cut mailbox list without a
    found inbox gets "may be behind the cut" instead of "has no mailbox with the inbox role",
    because the second sentence is a claim about a list this leg has not seen to the end. The
    ``boxes_truncated`` flag is popped either way, so it never leaves this leg as data.
    """
    if isinstance(outcome, BaseException):
        degraded.append({"source": "mail", "reason": _reason(outcome, "mail", MAIL_BUDGET)})
        return []

    degraded.extend(_degraded_of(outcome))
    entries = _entries(outcome)
    total = _count(outcome.get("total"))
    if outcome.get("accounts_truncated"):
        degraded.append(
            {
                "source": "mail",
                "reason": (
                    f"The account list was cut at {mail_tools.MAX_LIMIT} by the mail tool, "
                    f"so the total of {total} mail accounts is a lower bound."
                ),
            }
        )
    if total > MAX_MAIL_ACCOUNTS:
        degraded.append(
            {
                "source": "mail",
                "reason": (
                    f"Only the first {MAX_MAIL_ACCOUNTS} of {total} mail accounts are counted."
                ),
            }
        )
    for entry in entries:
        cut = bool(entry.pop("boxes_truncated", False))
        if "inbox_unread" in entry:
            continue
        label = str(entry.get("email") or "") or f"#{entry.get('account_id')}"
        if cut:
            degraded.append(
                {
                    "source": "mail",
                    "reason": (
                        f"The mailbox list of the account {label} was cut at "
                        f"{mail_tools.MAX_LIMIT}, so its inbox may be behind the cut and it "
                        "carries no counter here."
                    ),
                }
            )
            continue
        degraded.append(
            {
                "source": "mail",
                "reason": (
                    f"The mail account {label} has no mailbox with the inbox role, so it "
                    "carries no counter here."
                ),
            }
        )
    return entries


def _entries(answer: dict[str, Any]) -> list[dict[str, Any]]:
    """The ``results`` list of a composed answer, and an empty list for anything else.

    One reader for the account level, the mailbox level and the account list of this leg: all
    three are the same envelope, and the key is ``results`` on every level of that family.
    """
    raw = answer.get("results")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _hits(
    outcome: dict[str, Any] | BaseException, degraded: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """The raw hits of the search leg, or nothing plus one sentence about why."""
    if isinstance(outcome, BaseException):
        degraded.append({"source": "search", "reason": _reason(outcome, "search", None)})
        return []

    # The search writes its own degraded entries and they arrive unchanged: one form for
    # one problem, and rewording them here would be a second answer to the same question.
    degraded.extend(_degraded_of(outcome))
    raw = outcome.get("results")
    return [hit for hit in raw if isinstance(hit, dict)] if isinstance(raw, list) else []


def _bundle(
    hits: list[dict[str, Any]], degraded: list[dict[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Group by ``kind``, cap each group, and say out loud where the cap bit."""
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS}
    matched = dict.fromkeys(BUCKETS, 0)

    for hit in hits:
        kind = str(hit.get("kind") or "")
        bucket = kind if kind in KIND_BUCKETS else OTHER_BUCKET
        matched[bucket] += 1
        if len(grouped[bucket]) < MAX_PER_BUCKET:
            grouped[bucket].append(_short(hit))

    for name in BUCKETS:
        if matched[name] > MAX_PER_BUCKET:
            found = matched[name]
            degraded.append(
                {
                    "source": name,
                    "reason": f"Only the first {MAX_PER_BUCKET} of {found} hits are listed.",
                }
            )
    return grouped


def _short(hit: dict[str, Any]) -> dict[str, Any]:
    """One hit as origin plus title: the four fields a follow up call needs (D-54, D-57).

    Whether a hit can be read is the hit's own statement, and the bucket it was grouped into
    says nothing about it any more. The grouping is a matter of presentation, the
    resolvability a matter of the id, and TOOL-16 is what pulled the two apart.
    """
    entry: dict[str, Any] = {
        "id": str(hit.get("id") or ""),
        "title": str(hit.get("title") or ""),
        "provider": str(hit.get("provider") or ""),
        "kind": str(hit.get("kind") or ""),
    }
    if hit.get("resolvable") is False:
        # The honest half of pitfall 10: this id cannot be handed to a read tool as it is.
        # "Not one of the three named kinds" used to be the same sentence and is not any
        # more: since TOOL-16 the provider map resolves a Talk message and a Tables table,
        # and ``fetch`` reads both, so a whole bucket can no longer answer this question.
        # The hit answers it, and a hit that says nothing is taken at its word.
        entry["resolvable"] = False
    return entry


def _schedule(
    outcome: dict[str, Any] | BaseException, degraded: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """The events of the window, or nothing plus one sentence about why."""
    if isinstance(outcome, BaseException):
        degraded.append(
            {"source": "calendar", "reason": _reason(outcome, "calendar", CALENDAR_BUDGET)}
        )
        return []

    degraded.extend(_degraded_of(outcome))
    if outcome.get("truncated"):
        degraded.append(
            {
                "source": "calendar",
                "reason": f"Only the first {MAX_EVENTS} events of the window are listed.",
            }
        )
    raw = outcome.get("events")
    events = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return events[:MAX_EVENTS]


def _digest(
    outcome: dict[str, Any] | BaseException, degraded: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """The conversations with something waiting, or nothing plus one sentence about why.

    "Waiting" is unread messages or a mention, and a mention without unread messages counts:
    somebody addressed this account and the conversation was opened afterwards, which is
    still the thing a bundle is supposed to surface.

    The order is by direct mention, then by any mention, then by the last activity, all
    descending. Sorting by activity alone would let a loud group chat push a direct mention
    out of three places, and a direct mention is the entry the account is most likely to be
    the reason for.

    ``unread`` is passed through as the counter of the app and is not a message count. A
    conversation nobody ever opened reports 1 with an empty history, because the web
    interface wants a dot on it; the sentence belongs to
    :func:`mcp_connector.tools.talk._conversation` and is inherited here rather than
    corrected, because correcting it would invent a second truth about somebody else's
    number.

    A failure of this leg, and that includes an instance without Talk, is exactly one entry
    under ``degraded`` and an empty list. The missing app arrives as a ``ToolError`` from
    ``capabilities.require_app``, so it takes the first branch of :func:`_reason` and keeps
    the sentence of that layer instead of getting a second one here.
    """
    if isinstance(outcome, BaseException):
        degraded.append({"source": "talk", "reason": _reason(outcome, "talk", TALK_BUDGET)})
        return []

    degraded.extend(_degraded_of(outcome))
    raw = outcome.get("results")
    entries = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    if outcome.get("truncated"):
        # The cut of the tool layer, said out loud here as well. Without this sentence a
        # digest of three out of fifty read conversations would look like three out of all
        # of them, and the ones behind the cut can be exactly the ones with a mention.
        total = _count(outcome.get("total")) or len(entries)
        degraded.append(
            {
                "source": "talk",
                "reason": (
                    f"Only the first {len(entries)} of {total} conversations of this account "
                    "were read."
                ),
            }
        )
    waiting = sorted((item for item in entries if _waiting(item)), key=_urgency, reverse=True)
    if len(waiting) > MAX_DIGEST:
        found = len(waiting)
        degraded.append(
            {
                "source": "talk",
                "reason": (
                    f"Only the first {MAX_DIGEST} of {found} conversations with something "
                    "unread are listed."
                ),
            }
        )
    return [_digest_entry(item) for item in waiting[:MAX_DIGEST]]


def _waiting(entry: dict[str, Any]) -> bool:
    """Whether this conversation has something unread or a mention in it."""
    return bool(
        _count(entry.get("unread")) > 0
        or entry.get("unread_mention")
        or entry.get("unread_mention_direct")
    )


def _urgency(entry: dict[str, Any]) -> tuple[int, int, int]:
    """The sort key of the digest, read in :func:`_digest`, descending in all three parts."""
    return (
        int(bool(entry.get("unread_mention_direct"))),
        int(bool(entry.get("unread_mention"))),
        _count(entry.get("last_activity")),
    )


def _digest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """One conversation as the four fields a follow up call needs, plus the preview."""
    digest: dict[str, Any] = {
        "token": str(entry.get("token") or ""),
        "name": str(entry.get("name") or ""),
        "unread": _count(entry.get("unread")),
        "unread_mention": bool(entry.get("unread_mention")),
    }
    preview = _preview(str(entry.get("last_message") or ""))
    if preview:
        digest["last_message"] = preview
    return digest


def _preview(text: str) -> str:
    """One preview at :data:`DIGEST_PREVIEW_BYTES`, cut without a marker of its own.

    The second cut of the same text: the tool layer capped it at 800 bytes already, and this
    one brings it down to the size a digest line may cost. Bytes, and a tolerant decode, so a
    character the cut split in half disappears instead of arriving broken.

    No marker is appended, and that follows the module this text comes from: "A cut preview
    carries no marker of its own". A preview is a fragment by definition, the full text is
    one ``talk_browse`` call away, and a marker this server writes next to somebody else's
    sentence could not be told apart from a sentence of that somebody (ME-03).

    A marker the message wrote itself goes first, exactly as in :func:`_capped`. The tool
    layer has already done it, and doing it again is neither a second truth nor expensive: it
    is the same removal at the boundary where the text actually leaves this module, and it
    runs before the measurement, so the ceiling applies to what is handed out.
    """
    text = marks.without_marks(text)
    blob = text.encode("utf-8")
    if len(blob) <= DIGEST_PREVIEW_BYTES:
        return text
    return blob[:DIGEST_PREVIEW_BYTES].decode("utf-8", errors="ignore")


def _count(value: Any) -> int:
    """A counter of a composed answer as a number, and 0 for anything that is not one.

    ``bool`` is excluded on purpose, exactly as in ``talk.py``: a ``True`` where a count
    belongs is a deformed answer and not the number one. The sort key needs numbers of one
    type, so this is also what keeps a foreign string out of :func:`sorted`.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


async def _excerpts(
    clients: NcClients,
    results: dict[str, list[dict[str, Any]]],
    degraded: list[dict[str, str]],
) -> None:
    """Add a short excerpt to the first few resolvable hits, in place and in parallel.

    The order is the documented one: files first, then notes, then cards, and inside a kind
    the order the search returned. It is deliberately fixed rather than clever, because a
    ranking would be a second opinion about relevance next to the one Nextcloud already
    gave, and this tool has no more information than the search it just called.

    The content itself comes from ``chatgpt.fetch``: the id codec, the prefix discipline,
    the refusal to request a foreign url and the readers of the three kinds all live there
    and are tested there (threat T-01-75, T-01-77). A second routing here would be a second
    place to get exactly those decisions wrong. The excerpt is a data field and nothing
    else: no sentence of this module turns it into a request or an instruction (D-57).

    The kinds come from :data:`EXCERPT_KINDS` and deliberately not from the bucket list: a
    later decision about how this answer is grouped must not silently widen what this server
    reads unasked.
    """
    targets = [
        hit
        for name in EXCERPT_KINDS
        for hit in results.get(name, [])
        if hit.get("resolvable") is not False
    ][:MAX_EXCERPTS]

    outcomes = await asyncio.gather(
        *(_excerpt(clients, str(hit["id"])) for hit in targets), return_exceptions=True
    )
    for hit, outcome in zip(targets, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            # The hit was found, and that stays true even when its content cannot be read.
            degraded.append(
                {
                    "source": str(hit["id"]),
                    "reason": _reason(outcome, "excerpt source", EXCERPT_TIMEOUT),
                }
            )
            continue
        hit["excerpt"] = outcome


async def _excerpt(clients: NcClients, identifier: str) -> str:
    """One excerpt, under its own two ceilings, through the routing that already exists.

    The second ceiling is the one on the way in: the reader is told how much it may read,
    instead of reading its own default and having it thrown away here (LO-06).
    """
    async with asyncio.timeout(EXCERPT_TIMEOUT):
        fetched = await chatgpt_tools.fetch(clients, identifier, max_bytes=EXCERPT_READ_BYTES)
    return _capped(str(fetched.get("text") or ""))


def _capped(text: str) -> str:
    """Cut an excerpt to its byte ceiling and say inside the text that it was cut.

    Bytes and not characters, because the ceiling is about the payload and an umlaut is two
    bytes. ``errors="ignore"`` drops a character that the cut split in half, which is the
    right trade for a preview and would be the wrong one for a document.

    The document's own copy of either marker goes first (BL-09, ME-03). The marker stays in
    the text, which is what a model reading only the excerpt needs, but it can no longer
    come from the text: a shared file that writes the sequence itself would otherwise decide
    where the model believes the server excerpt ends, and that is the boundary D-57 rests
    on. Filtering happens before the measurement, so the ceiling applies to what is actually
    handed out.
    """
    body = marks.without_marks(text)
    encoded = body.encode("utf-8")
    if len(encoded) <= EXCERPT_MAX_BYTES:
        return body
    return f"{encoded[:EXCERPT_MAX_BYTES].decode('utf-8', errors='ignore')}\n\n{EXCERPT_TRUNCATION}"


def _degraded_of(answer: dict[str, Any]) -> list[dict[str, str]]:
    """The degraded entries of a composed answer, exactly as that tool wrote them (D-55)."""
    entries = answer.get("degraded")
    return (
        [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []
    )


def _reason(exc: BaseException, subject: str, budget: float | None) -> str:
    """One sentence per failed source: what happened, never who we are.

    The three cases are the ones from ``tools/search.py``, deliberately word for word.
    An unknown failure is a bug and stays loud instead of becoming a soothing sentence.
    """
    if isinstance(exc, ToolError):
        return exc.message
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        if budget is None:
            return f"The {subject} did not answer in time."
        return f"The {subject} did not answer within {budget:g} seconds."
    if isinstance(exc, httpx.RequestError):
        return f"The {subject} could not be reached."
    raise exc
