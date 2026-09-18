"""The throttle of our own authorization paths, and the measure it really answers to.

**What is being protected, and it is not this process.** The finding of the phase research
that decides this module comes out of the HaRP source: HaRP asks Nextcloud who the caller
is for *every* request that carries an ``Authorization`` header, on public routes as well,
and it caches that answer for cookie sessions only (pitfall 5). Every such request is a
full Nextcloud PHP round trip that this application cannot switch off. The good half of the
same finding is that an unknown bearer produces no brute force entry in Nextcloud
(``Session::tryTokenLogin`` returns false without registering an attempt) and no HaRP
blacklist entry either, which means Nextcloud will not defend itself here. So the ceiling
is ours to set, and success criterion 5 is measured in Nextcloud round trips rather than in
our own response times.

**What is throttled and what is not.** The authorization paths of this application:
``/token``, ``/register``, ``/revoke``, ``/authorize`` with the consent surface behind it,
and the browser onboarding of AUTH-02. The two of them that make this server start a
Nextcloud login flow, ``/authorize`` and ``POST /connect``, are the reason this module
exists at all (SC 5). The MCP route is deliberately not among them: a tool call arrives
with a verified bearer, is answered from the process cache of the
verifier, and rate limiting the actual work of this server would be a denial of service
with our own name on it (D-37).

**What is counted, and why it is not the status of the answer (CR-02).** Two kinds of
request are counted, and the difference is what each of them costs. On the endpoints whose
work is a refusal, the counted event is a refusal: an answer of 400 or more, which covers
every rejection of every endpoint behind this wrapper without this module knowing a single
one of them. On the two routes that make this server *open a Nextcloud login flow*, the
counted event is the request itself, before the work, because that is the request that
costs the round trip. Those are ``POST /connect`` and ``/authorize``, and they answer 200
and 302 when they succeed, so counting the status would have counted exactly nothing on
the one path SC 5 exists for. They carry their own path classes and their own limit for
that reason: a person who connects a second assistant is not an attacker, and the ceiling
has to sit far above one honest connection and far below a flood.

A successful answer on a refusal counting class pays back one failure instead of clearing
the counter (WR-03). Clearing it handed a guessing loop the switch that turns the throttle
off: the path classes are shared surfaces, so one harmless successful request every ninth
attempt kept the counter at zero forever. Paying back one keeps the ordinary case (a person
who mistypes something and then succeeds does not carry it around for five minutes) without
buying an attacker more than the one attempt they actually spent.

Nothing of a request is kept: the counter is keyed by the SHA-256 digest of the path class
and the source together, so the dictionary of this object contains digests, integers and
deadlines and nothing that could identify anybody (T-03-65).

**Why there are two limits.** The per source limit is the useful one and the forgeable one:
behind HaRP the peer address of every request is the proxy, so the source has to be taken
from ``X-Forwarded-For`` when it is there, and anybody who can send a request can write
that header. Splitting the counter that way is exactly what an attacker would do, which is
why the second limit exists: a ceiling per path class that no header can escape. Without it
a forged header would buy an unbounded number of Nextcloud round trips; without the first
limit a single flood behind one proxy would lock out every legitimate user of the instance.

**And why one surface has neither of them in that shape (HI-01).** A ceiling per path class
is shared fate: whoever fills it closes the class for everybody. That is the right trade on
the endpoints an assistant app talks to, and the wrong one on the page a person opens to
pull the brake on their own account, because the flood that fills it needs no credential at
all. Where the counter can be keyed by the account the proxy signed, the forgeable source is
gone and with it the reason for the ceiling, so ``/connections`` counts per account, without
the class ceiling, and does not count the requests that carry no account.

The state is process local, has a hard ceiling on how many counters it keeps, and losing it
is harmless: a restart forgets who was attempting what, which costs one window of counting
and nothing else. Two workers count separately, which makes the effective limit twice the
number below, and that is a deliberate simplification: a shared counter would need a shared
store in the hot path of every authorization request, which is precisely what D-37 keeps
out of it.
"""

import hashlib
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import config
from ..exapp.responses import json_response
from ..exapp.ui import errors

__all__ = [
    "CLASS_AUTHORIZE",
    "CLASS_AUTHORIZE_START",
    "CLASS_CONNECT",
    "CLASS_CONNECTIONS",
    "CLASS_CONNECT_START",
    "CLASS_OIDC_CALLBACK",
    "CLASS_OIDC_START",
    "CLASS_REGISTER",
    "CLASS_REVOKE",
    "CLASS_TOKEN",
    "FAILURE_LIMIT",
    "FLOW_LIMIT",
    "PATH_CEILING",
    "SOURCE_LIMIT",
    "WINDOW",
    "Throttle",
    "Throttled",
    "source_of",
]

#: The path classes of this application. Separate counters, because a person fighting
#: with the consent screen must not close the endpoint a working connector refreshes at.
CLASS_TOKEN = "token"  # noqa: S105 - the name of a path class, not a credential
CLASS_REGISTER = "register"
CLASS_REVOKE = "revoke"
CLASS_AUTHORIZE = "authorize"
CLASS_CONNECT = "connect"

#: The account page of EXAPP-02, and a class of its own since HI-01. It shared
#: ``CLASS_AUTHORIZE`` with the consent screen, which put the emergency brake of every
#: account and every running authorization decision behind one ceiling: two hundred anonymous
#: requests on this public page closed all three for five minutes. This page is also the one
#: surface whose counter is keyed by the account instead of by a forwarded address, see the
#: ``identity`` argument of :class:`Throttled`.
CLASS_CONNECTIONS = "connections"

#: The two classes of the requests that open a Nextcloud login flow: the POST that starts
#: the browser onboarding and the authorization endpoint. Classes of their own, because
#: every request of them is counted and not only the refused ones, so mixing them with the
#: screens behind them would close a waiting page that is doing nothing wrong.
CLASS_CONNECT_START = "connect-start"
CLASS_AUTHORIZE_START = "authorize-start"

#: The standalone OIDC browser routes (``oauth/oidc_routes``). The start counts every
#: request, because each one writes a sign in row; the callback counts refusals, like the
#: consent screen it leads back to.
CLASS_OIDC_START = "oidc-start"
CLASS_OIDC_CALLBACK = "oidc-callback"

#: How many failed attempts one source may make per path class before it has to wait. Ten
#: is generous for every legitimate shape of failure (a mistyped link, a stale tab, a
#: client that retries a rejected grant twice) and short work of a guessing loop.
FAILURE_LIMIT = 10

#: How many login flows one source may open per window, refused or not. Twenty is far above
#: what a person does (one connection is one flow, and a retry after a closed browser window
#: is a second) and far below what makes a Nextcloud work: every one of them is one PHP
#: round trip plus one record that lives for twenty minutes at Nextcloud (SC 5, T-03-35).
FLOW_LIMIT = 20

#: The ceiling of a whole path class, whatever a caller writes into a forwarded header.
#: Two hundred failures in five minutes is far above anything an instance produces by
#: accident and far below a load that a Nextcloud would feel.
PATH_CEILING = 200

#: The window both limits are counted in. Five minutes, the same order of magnitude as the
#: Nextcloud brute force window, so a caller that ran into this one is not surprised twice.
WINDOW = 300

#: How many counters this object keeps at once. Reached only by a caller that varies its
#: source, which is exactly the case the ceiling above already covers, so the reaction is
#: to drop what has run out and then, if that was not enough, to start over (T-03-65).
SOURCE_LIMIT = 4096

#: The counter of a whole path class, the one no request can influence. Not a source and
#: not a valid header value, so no caller can land in it by accident.
_WHOLE_CLASS = "\x00all"

#: What a throttled machine endpoint answers. ``temporarily_unavailable`` is the OAuth
#: error code for "this is not about your request, come back later"; a code that named the
#: throttle would tell a caller which of our defences they reached.
_ERROR = "temporarily_unavailable"

logger = logging.getLogger("mcp_connector.oauth.throttle")


@dataclass(slots=True)
class _Counter:
    """One window: how many failures were seen in it, and when it ends."""

    seen: int
    until: float


class Throttle:
    """The counters of one process, asked before the work and told after it.

    Built once per application and shared by every authorization route, so the five path
    classes are five counters and not five objects with five ceilings.
    """

    def __init__(
        self,
        *,
        limit: int = FAILURE_LIMIT,
        ceiling: int = PATH_CEILING,
        window: int = WINDOW,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._limit = limit
        self._ceiling = ceiling
        self._window = window
        #: Monotonic: a window must not grow or shrink because somebody corrected the
        #: system clock, and nothing here is ever compared against a stored row.
        self._clock = clock if clock is not None else time.monotonic
        self._counters: dict[str, _Counter] = {}

    def __repr__(self) -> str:
        return (
            f"Throttle(limit={self._limit!r}, ceiling={self._ceiling!r}, window={self._window!r})"
        )

    def retry_after(
        self, path_class: str, source: str, *, limit: int | None = None, shared: bool = True
    ) -> int:
        """Seconds this caller has to wait, or ``0`` when it may go ahead.

        Never zero when a limit is reached: a page that promises an immediate retry invites
        exactly the request the throttle exists against, which is why the answer is rounded
        up and floored at one second.

        ``limit`` is the per source ceiling of the route that asks, so the two classes that
        count every request can carry a higher one than the classes that count refusals
        (CR-02). The ceiling of the path class is not a parameter: it is the limit no
        forged header can escape, and one route must not be able to raise it.

        ``shared=False`` leaves the counter of the whole path class out of the question, and
        it is only correct where the source cannot be forged (HI-01). The ceiling exists
        because a forwarded address is written by whoever sends the request, so a caller
        could otherwise split its own counter without bound. Where the source is the account
        id HaRP signs, that escape does not exist, and the ceiling then buys nothing and
        costs the thing it is supposed to protect: shared fate between accounts, so a flood
        of refusals closes a security page for the person who needs it.
        """
        now = self._clock()
        pairs = [(self._key(path_class, source), self._limit if limit is None else limit)]
        if shared:
            pairs.append((self._whole(path_class), self._ceiling))
        for key, limit in pairs:
            counter = self._counters.get(key)
            if counter is None or counter.until <= now:
                continue
            if counter.seen >= limit:
                return max(1, math.ceil(counter.until - now))
        return 0

    def record_attempt(self, path_class: str, source: str, *, shared: bool = True) -> None:
        """Count one attempt, for this source and for the path class as a whole.

        What an attempt is belongs to the caller: a refused request on the classes that
        count refusals, and every request on the two classes that count the cause, because
        there the cost is paid whether the answer is a 200 or a 400 (CR-02).

        ``shared=False`` counts for the source alone, the counterpart of the same argument
        of :meth:`retry_after` and correct under the same condition: the source is signed
        and therefore not forgeable (HI-01).
        """
        now = self._clock()
        self._sweep(now)
        keys = [self._key(path_class, source)]
        if shared:
            keys.append(self._whole(path_class))
        for key in keys:
            counter = self._counters.get(key)
            if counter is None or counter.until <= now:
                self._counters[key] = _Counter(seen=1, until=now + self._window)
            else:
                counter.seen += 1

    def forgive(self, path_class: str, source: str) -> None:
        """Pay back one counted failure of this source, because it just succeeded.

        One, and never the whole window (WR-03). Clearing the counter looked forgiving and
        was an off switch: the path classes are shared surfaces, so a caller guessing flow
        ids on the consent screen only had to interleave one harmless successful request
        every ninth attempt to stay at zero forever. Paying back exactly one keeps the case
        this exists for, a person who mistypes something and then succeeds.

        The ceiling of the path class is deliberately not touched at all: one success among
        a thousand failures is what a guessing loop looks like from the inside.
        """
        counter = self._counters.get(self._key(path_class, source))
        if counter is not None and counter.seen > 0:
            counter.seen -= 1

    def _key(self, path_class: str, source: str) -> str:
        """The digest one counter lives under. Never the source, never the path.

        SHA-256 of the two values with a separator between them: the separator is what
        keeps a source that ends in the name of a path class from colliding with another
        one, and the digest is what keeps this dictionary from being a record of who tried
        what (T-03-65).
        """
        return hashlib.sha256(f"{path_class}\x00{source}".encode()).hexdigest()

    def _whole(self, path_class: str) -> str:
        return self._key(path_class, _WHOLE_CLASS)

    def _sweep(self, now: float) -> None:
        """Keep the number of counters under the ceiling, in the simplest way that holds."""
        if len(self._counters) < SOURCE_LIMIT:
            return
        for key in [key for key, counter in self._counters.items() if counter.until <= now]:
            del self._counters[key]
        if len(self._counters) >= SOURCE_LIMIT:
            # Everything in here is younger than one window and nothing in it is worth more
            # than that window, so starting over is both correct and the rule that cannot
            # leak. It costs an ongoing flood one window of counting, and it is logged.
            logger.warning("the throttle reached its ceiling of counters and starts over")
            self._counters.clear()


class Throttled:
    """One route, with the counter asked before it and told after it.

    An ASGI wrapper and not a decorator on the handlers, for the reason
    :class:`~mcp_connector.oauth.provider.NoStore` is one: the endpoints of the
    authorization server belong to the SDK, and wrapping them leaves their bodies, their
    error shapes and their CORS handling exactly as they are.

    Two ways of counting, and the route decides which one it needs (CR-02).

    By default what counts is the status of the answer: anything from 400 upwards. That
    covers every refusal of every endpoint behind this wrapper without this module having
    to know a single one of them, and it counts nothing that worked, including the
    redirects of the authorization endpoint and the pages of the consent screen.

    With ``count_all`` the request itself is counted, before the work and whatever the
    answer turns out to be. That is the shape the two routes need which make this server
    open a Nextcloud login flow: they answer 200 and 302 when they succeed, so a status
    based counter never counted the one thing SC 5 is about. Counting before the work is
    also the honest moment: the round trip is caused by the request arriving, not by the
    answer being written, and a request that dies halfway must not be free.

    ``identity`` is the third shape, and it exists for exactly one surface: the account page
    of EXAPP-02, which is the emergency brake of an account and must not be closable from
    outside (HI-01). Where it is given, two things change. The counter is keyed by the
    account the proxy signed instead of by a forwarded address, so one account's refusals
    can never send another account away, and the ceiling of the whole path class is left out
    of it, because a signed source cannot be split by whoever sends the request. A request
    without an account is not counted and not throttled at all: it is refused before
    anything is read, it causes no Nextcloud round trip, and counting it was precisely the
    defect, because two hundred anonymous requests then closed the page for its owner.
    """

    def __init__(
        self,
        app: ASGIApp,
        throttle: Throttle,
        path_class: str,
        *,
        machine: bool,
        env: Mapping[str, str] | None = None,
        count_all: bool = False,
        limit: int | None = None,
        identity: Callable[[Request], str] | None = None,
    ) -> None:
        self._app = app
        self._throttle = throttle
        self._path_class = path_class
        self._machine = machine
        self._env = env
        self._count_all = count_all
        self._limit = limit
        self._identity = identity
        #: Read once per application, like every other configuration of this class.
        self._trust_forwarded = config.trust_forwarded_for(env)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover - these routes are HTTP only
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        if self._identity is not None:
            account = self._identity(request)
            if not account:
                # Nothing to bound: this request is refused before a store is opened and it
                # cannot cause a Nextcloud round trip (HI-01).
                await self._app(scope, receive, send)
                return
            source, shared = account, False
        else:
            source, shared = source_of(request, trust_forwarded=self._trust_forwarded), True

        wait = self._throttle.retry_after(
            self._path_class, source, limit=self._limit, shared=shared
        )
        if wait:
            await self._refuse(wait)(scope, receive, send)
            return

        if self._count_all:
            # Before the work, because the work is what it pays for. Nothing below may
            # forgive it either: on this class a successful request is exactly the
            # expensive one.
            self._throttle.record_attempt(self._path_class, source, shared=shared)
            await self._app(scope, receive, send)
            return

        status = 0

        async def watch(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        await self._app(scope, receive, watch)
        if status >= 400:
            self._throttle.record_attempt(self._path_class, source, shared=shared)
        else:
            self._throttle.forgive(self._path_class, source)

    def _refuse(self, wait: int) -> Response:
        """The 429, in the shape the caller of this path can read.

        The same number in the header and in the body, because the two are read by two
        different readers: an assistant app backs off on ``Retry-After``, and a person
        reads the sentence on the page. A page that said something else than its own header
        would make one of the two wrong.

        The wording says "too many attempts" and not which of them were refused: on the
        classes that count every request, most of them worked.
        """
        if self._machine:
            return json_response(
                {
                    "error": _ERROR,
                    "error_description": f"too many attempts, retry in {wait} seconds",
                },
                status_code=429,
                headers={"Retry-After": str(wait)},
            )
        page, _reference = errors.error_page("E6", env=self._env, seconds=wait)
        return page


def source_of(request: Request, *, trust_forwarded: bool = True) -> str:
    """Who is asking, as well as this topology can tell.

    Behind HaRP the peer of every request is the proxy, so the forwarded address is the
    only value that tells two callers apart at all. It is forgeable, and this function does
    not pretend otherwise: it is used to *split* a counter, never to authenticate anything,
    and the ceiling of the path class is what holds when somebody forges it. The first
    entry of the header is taken, because that is the original client in the convention of
    RFC 7239 and because a longer chain is the proxies, not the caller.

    ``trust_forwarded=False`` is the deployment without a proxy in front: there the peer
    address is the real one, and reading a header the caller writes would let one source
    spend the limit of every other. It comes from
    :func:`mcp_connector.config.trust_forwarded_for`, never from a request.
    """
    peer = request.client.host if request.client else ""
    if not trust_forwarded:
        return peer
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or peer or ""
