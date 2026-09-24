"""Error format of the whole connector: one message plus one actionable hint (D-15).

No exception class in this package ever carries credentials or a URL that contains
credentials. The server layer turns these errors into ordinary tool errors so the model
can correct itself; tracebacks are suppressed there on purpose (threat T-01-07).

The ``reason`` of an error is the only part of it that may ever leave for a log
(threat T-18-01). ``message`` and ``hint`` are written for the model and are therefore
concrete: ``dav.py`` says ``f"No permission to write to {path}."`` and names a real path,
``caldav.py`` names a real calendar. That is result content, it belongs in the tool answer
and in no log. A fixed identifier carries the reason without carrying the case.

For the six ``exchange_`` identifiers below, "leave" is narrower still and is named here
once: the only place they may leave this process is the audit line of AUDIT-07, never an
HTTP answer and never a log line above DEBUG. The exchange path is reachable before any
authentication, so a 401 that says which rule fell hands a stranger an oracle he ordered
with one request (threat T-24-03).
"""

# Twelve identifiers in two groups, and the grouping is the readable part of an audit line.
# The first six are the ways a tool call can end: they say what Nextcloud answered or that a
# guard of this server stepped in. The second six are the ways the exchange token checker
# turns a foreign token down, one per group of check steps, never per single rule.
#
# The second group carries a prefix because it needs one. ``guard_tripped`` could have come
# from any guard of this server, ``exchange_claims`` could not, and a reader of a line in the
# hash-chained trail should not have to look the path up. And it stays a group on purpose:
# ``oauth/exchange.py`` refuses through eighteen fixed phrases, and one identifier per phrase
# would resolve a refusal down to the exact rule that fell. In a trail an operator reads,
# that resolution is one copy away from the answer the checker exists not to give, so the
# phrases stay in the DEBUG line of ``_refused`` and the audit line carries the group.
#
# Each line below says which case sets it.
REASON_UNSPECIFIED = "unspecified"  # not determined; honest instead of guessed
REASON_PERMISSION_DENIED = "permission_denied"  # Nextcloud answered 403
REASON_UNKNOWN_ID = "unknown_id"  # Nextcloud answered 404, 409 or 998
REASON_TIMEOUT = "timeout"  # Nextcloud did not answer in time
REASON_UNREACHABLE = "unreachable"  # Nextcloud could not be reached at all
REASON_GUARD_TRIPPED = "guard_tripped"  # a guard of this server stopped the call

# The exchange groups (AUDIT-07). ``oauth/exchange.py`` hands one of these to every refusal.
# empty, longer than allowed, not text, header or payload unreadable, a foreign header type
REASON_EXCHANGE_MALFORMED = "exchange_malformed"
# algorithm not configured, no key named, key set unreachable or unusable, signature broken
REASON_EXCHANGE_KEY = "exchange_key"
# the pre-filter on the unverified ``iss``, and nothing else
REASON_EXCHANGE_ISSUER = "exchange_issuer"
# standard claims, audience, azp allowlist, typ, non-numeric times, lifetime, age, sub
REASON_EXCHANGE_CLAIMS = "exchange_claims"
# the mapping yields no principal, there is no account source, or the source says no
REASON_EXCHANGE_ACCOUNT = "exchange_account"
# an unexpected exception in the checking branch: the case where the reason is unknown
REASON_EXCHANGE_FAILED = "exchange_failed"

# Frozen on purpose: a thirteenth reason is a decision and belongs into a review, not into a
# diff. ``tests/unit/test_errors_reason.py`` walks src/ and fails on any ``reason=`` that is
# not one of these names.
REASONS: frozenset[str] = frozenset(
    {
        REASON_UNSPECIFIED,
        REASON_PERMISSION_DENIED,
        REASON_UNKNOWN_ID,
        REASON_TIMEOUT,
        REASON_UNREACHABLE,
        REASON_GUARD_TRIPPED,
        REASON_EXCHANGE_MALFORMED,
        REASON_EXCHANGE_KEY,
        REASON_EXCHANGE_ISSUER,
        REASON_EXCHANGE_CLAIMS,
        REASON_EXCHANGE_ACCOUNT,
        REASON_EXCHANGE_FAILED,
    }
)


def known_reason(reason: str | None) -> str | None:
    """A rejection identifier out of the frozen set above, or the honest "not determined".

    The rule of D-07, and it lives here because the set it guards lives here. It used to
    stand in ``audit/record.py`` as a private helper of the recording path; the moment a
    second writer of a ``reason`` column arrived (``audit/refusals.py``, AUDIT-07), the
    choice was between a second copy of four lines and one function both callers reach, and
    R-18-06 of phase 18 is the measured answer to that question: three versions of the
    cleaning rule for a client name ended up with two different ideas of what is printable,
    and the narrow one let a right-to-left override into an output line.

    A reason travels from an exception into a row, and an exception is not a place this
    module controls: anything that is not one of :data:`REASONS` would be free text in a
    column that exists in order to have none. ``None`` stays ``None``, because a row that
    records no refusal names no reason either.
    """
    if reason is None:
        return None
    return reason if reason in REASONS else REASON_UNSPECIFIED


class ToolError(Exception):
    """A failure a caller can act on: what went wrong plus what to do about it."""

    def __init__(self, message: str, hint: str, *, reason: str = REASON_UNSPECIFIED) -> None:
        # The default is the reason why the roughly 223 other raise sites stay untouched
        # (D-17): this phase puts a module next to the error handling, it does not tidy the
        # error handling up. Everything without a reason reads as "not determined", which is
        # honest, and not as a guessed cause.
        super().__init__(f"{message} Hint: {hint}")
        self.message = message
        self.hint = hint
        self.reason = reason


class AppMissingError(ToolError):
    """A Nextcloud app the tool needs (Notes, Deck, ...) is not installed."""


class ConflictError(ToolError):
    """The target already exists. This server never overwrites (TOOL-09)."""


class IssuerRefused(ToolError):
    """The configured public address cannot be the issuer of the authorization server.

    Raised in ``oauth/provider.auth_routes`` when the SDK refuses the issuer, and caught in
    ``entry_exapp.main``, which answers it by dropping the address and building once more
    with the documented default, so the admin form stays reachable (the rescue half of
    CR-01).

    It has a type of its own because that rescue used to catch every :class:`ToolError` of
    the build, which was true about today and an assumption about tomorrow (IN-06): a second
    build time failure would have been logged as an address problem, would have had a
    possibly perfectly good address dropped and would have ended in a second build with a
    confusing double message. Everything else stays what it is and ends the start.
    """
