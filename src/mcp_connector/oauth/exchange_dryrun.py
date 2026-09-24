"""The rule half of the dry run (EXCH-06): a presented token against a handed-in config.

Nothing here reads the environment. The configuration arrives as the validated
:class:`~mcp_connector.oauth.chain.ExchangeConfig` the chain already builds, and the only
thing that ever leaves this process is the key set fetch of the step ``key_available``,
whose price is named in the answer rather than hidden in this docstring. The module opens
no store, creates no authorization, asks Nextcloud nothing and writes no audit line: the
third success criterion of phase 24 forbids the presented token any effect at all, and a
module without a route and without an environment is how that becomes structural instead
of promised.

The console half is plan 24-06 (``exapp/exchange_check.py`` plus one occ command), exactly
as ``audit/store.verify_chains`` holds the rule and ``exapp/audit_verify.py`` holds the
console. The split is also the answer to open question 2 of the research: only the ExApp
operation gets a surface in this phase, the standalone operation gets none, and the border
is written down in ``docs/token-exchange.md`` rather than left silent. Because the rule
lives here and knows nothing about occ, a second surface later is one more file and no
change to this one.

An answer is data and never a finished sentence, in the form of ``audit/store.ChainFinding``:
a step name out of a closed set, one of four outcomes, and the rejection group of the
operating path when the step fell. The wording an administrator reads is built by the
console.

**What no field ever carries: a value out of the presented token** (T-24-09). Not the
``azp``, not the ``iss``, not the ``aud``, not the ``sub``, not the key id and no fragment
of the token itself. A step says which rule fell, never which value it saw; the token comes
from a foreign realm and an answer that echoed it would print that realm's text onto an
administrator's terminal.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

import jwt

from ..errors import (
    REASON_EXCHANGE_ISSUER,
    REASON_EXCHANGE_KEY,
    REASON_EXCHANGE_MALFORMED,
)
from .chain import ExchangeConfig, looks_like_jws
from .exchange import ACCEPTED_TYP_HEADERS, MAX_TOKEN_BYTES

__all__ = [
    "COST_SENTENCE",
    "LIMIT_SENTENCE",
    "MAX_TOKEN_BYTES",
    "NOTE_WOULD_CALL_NEXTCLOUD",
    "OUTCOME_FAILED",
    "OUTCOME_NOT_CHECKED",
    "OUTCOME_PASSED",
    "OUTCOME_SKIPPED",
    "STEPS",
    "STEP_ACCOUNT_EXISTS",
    "DryRunResult",
    "DryRunStep",
    "dry_run",
]

# --- the closed set of step identifiers ---------------------------------------------------
#
# Machine readable lower case names, one per rule of ``ExchangeTokenChecker.claims_of``,
# plus the shape switch of the chain in front of them and the account step that is never
# executed at the end. The console of plan 24-06 turns these into the names an administrator
# reads; nothing here is written for a human eye.
#
# The list follows the checker and never the other way round. A rule that arrives in
# ``oauth/exchange.py`` without a step here is what the drift gate of
# ``tests/unit/test_oauth_exchange_dryrun.py`` exists to find.

STEP_TOKEN_PRESENT: Final[str] = "token_present"  # noqa: S105 - a step name, not a secret
STEP_TOKEN_SIZE: Final[str] = "token_size"  # noqa: S105 - a step name, not a secret
STEP_TOKEN_IS_TEXT: Final[str] = "token_is_text"  # noqa: S105 - a step name, not a secret
STEP_TOKEN_SHAPE: Final[str] = "token_shape"  # noqa: S105 - a step name, not a secret
STEP_HEADER_READABLE: Final[str] = "header_readable"
STEP_ALGORITHM_ALLOWED: Final[str] = "algorithm_allowed"
STEP_KEY_NAMED: Final[str] = "key_named"
STEP_HEADER_TYPE: Final[str] = "header_type"
STEP_PAYLOAD_READABLE: Final[str] = "payload_readable"
STEP_ISSUER_MATCHES: Final[str] = "issuer_matches"
STEP_KEY_AVAILABLE: Final[str] = "key_available"
STEP_SIGNATURE_AND_STANDARD_CLAIMS: Final[str] = "signature_and_standard_claims"
STEP_AUDIENCE_EXACT: Final[str] = "audience_exact"
STEP_ACTING_PARTY_NAMED: Final[str] = "acting_party_named"
STEP_ACTING_PARTY_ALLOWED: Final[str] = "acting_party_allowed"
STEP_TOKEN_TYPE_BEARER: Final[str] = "token_type_bearer"  # noqa: S105 - a step name, not a secret
STEP_TIMES_NUMERIC: Final[str] = "times_numeric"
STEP_LIFETIME_WITHIN_BOUND: Final[str] = "lifetime_within_bound"
STEP_AGE_WITHIN_BOUND: Final[str] = "age_within_bound"
STEP_SUBJECT_USABLE: Final[str] = "subject_usable"
STEP_MAPPING_YIELDS_PRINCIPAL: Final[str] = "mapping_yields_principal"
STEP_ACCOUNT_EXISTS: Final[str] = "account_exists"

#: Every step of a dry run, in checking order. Twenty-two, and the order is the order of
#: ``claims_of`` with exactly one deliberate deviation, named in the docstring of
#: :func:`dry_run`.
STEPS: Final[tuple[str, ...]] = (
    STEP_TOKEN_PRESENT,
    STEP_TOKEN_SIZE,
    STEP_TOKEN_IS_TEXT,
    STEP_TOKEN_SHAPE,
    STEP_HEADER_READABLE,
    STEP_ALGORITHM_ALLOWED,
    STEP_KEY_NAMED,
    STEP_HEADER_TYPE,
    STEP_PAYLOAD_READABLE,
    STEP_ISSUER_MATCHES,
    STEP_KEY_AVAILABLE,
    STEP_SIGNATURE_AND_STANDARD_CLAIMS,
    STEP_AUDIENCE_EXACT,
    STEP_ACTING_PARTY_NAMED,
    STEP_ACTING_PARTY_ALLOWED,
    STEP_TOKEN_TYPE_BEARER,
    STEP_TIMES_NUMERIC,
    STEP_LIFETIME_WITHIN_BOUND,
    STEP_AGE_WITHIN_BOUND,
    STEP_SUBJECT_USABLE,
    STEP_MAPPING_YIELDS_PRINCIPAL,
    STEP_ACCOUNT_EXISTS,
)

# --- the four outcomes --------------------------------------------------------------------

#: The rule held.
OUTCOME_PASSED: Final[str] = "passed"
#: The rule did not hold, and :attr:`DryRunStep.reason` names the group of the operating path.
OUTCOME_FAILED: Final[str] = "failed"
#: The step came after the one that fell and was therefore not reached.
OUTCOME_SKIPPED: Final[str] = "skipped"
#: The step was deliberately not executed, and the note beside it says why.
OUTCOME_NOT_CHECKED: Final[str] = "not_checked"

#: The one note this module hands out: the step would be a Nextcloud call, and the third
#: success criterion of this phase forbids exactly that. It stands on ``account_exists`` in
#: every answer, whether that step is ``not_checked`` after a clean run or ``skipped`` behind
#: a rule that already fell, because a step that is merely absent reads as a passed step
#: (pitfall 8 of the research).
NOTE_WOULD_CALL_NEXTCLOUD: Final[str] = "would_call_nextcloud"

#: The last thing an answer says, and it belongs in the answer rather than only in this
#: docstring, because a green result is judged by whoever reads the console. Same reasoning
#: and same place in the answer as ``exapp/audit_verify.LIMIT_SENTENCE``.
LIMIT_SENTENCE: Final[str] = (
    "A green run does not mean the token works. The account was not checked: that step is "
    "a Nextcloud call and this check makes none. The times were judged against the clock of "
    "this container. And on an instance whose account list answers incompletely, the same "
    "token is refused in operation, because the exchange path treats an unreadable account "
    "list as a refusal."
)

#: The price of the run, said out loud for the same reason: one outgoing key set fetch per
#: dry run, paid on purpose so that an administrator's test cannot spend the cooldown of the
#: running checker (pitfall 7 of the research).
COST_SENTENCE: Final[str] = (
    "This check costs one outgoing key set request to the configured provider. It uses a key "
    "set of its own, so it neither fills nor spends the cache and the cooldown of the "
    "running checker."
)

#: The header ``typ`` values of the checker, folded once here for the comparison. The set
#: itself is imported and never retyped: which header types are tolerated is a rule of
#: ``oauth/exchange.py`` and a second spelling of it would be a second rule.
_TYP_HEADERS_FOLDED: Final[frozenset[str]] = frozenset(
    value.lower() for value in ACCEPTED_TYP_HEADERS
)


@dataclass(frozen=True, slots=True)
class DryRunStep:
    """One checked rule with its outcome, as data and never as a finished sentence.

    The wording an administrator reads is built by the console of plan 24-06, so the same
    step can also be handed out machine readable. What stands here is only what was
    measured: which rule, how it ended, and, when it fell, which rejection group the
    operating path would have booked it under.

    ``reason`` is one of the identifiers of :data:`mcp_connector.errors.REASONS` and is set
    on a fallen step alone. ``note`` is set on a step that was deliberately not executed and
    names why in one machine readable word.

    **No field ever carries a value out of the token.** Not a claim, not a key id, not a
    fragment of the token itself. This is not an omission that a later reader may helpfully
    fill in: the presented token belongs to a foreign realm, and an answer that repeated any
    part of it would both echo that realm's text and turn a refusal into an oracle about
    which single rule fell (T-24-09).
    """

    step: str
    outcome: str
    reason: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class DryRunResult:
    """Every step of one run, the overall verdict, and the two sentences that qualify it.

    ``passed`` is true only when every step either held or was the one step this check
    never executes. A run that stopped at a fallen rule leaves later steps ``skipped``, and
    a skipped step is an unanswered question rather than a passed one, so it keeps the
    verdict false.
    """

    steps: tuple[DryRunStep, ...]
    passed: bool
    limit_sentence: str = LIMIT_SENTENCE
    cost_sentence: str = COST_SENTENCE


@dataclass(slots=True)
class _Run:
    """The recorder of one walk through :data:`STEPS`. Never leaves this module."""

    seen: dict[str, DryRunStep] = field(default_factory=dict)

    def held(self, step: str) -> None:
        self.seen[step] = DryRunStep(step=step, outcome=OUTCOME_PASSED)

    def fell(self, step: str, reason: str) -> DryRunResult:
        self.seen[step] = DryRunStep(step=step, outcome=OUTCOME_FAILED, reason=reason)
        return self.finish()

    def finish(self) -> DryRunResult:
        """Every name of :data:`STEPS` in order, with the unreached ones marked skipped.

        The list never breaks off at the rule that fell. An administrator has to see the
        order and the completeness of the checks, and a step that is simply missing from an
        answer reads like a step that passed (pitfall 8).
        """
        steps = tuple(self._step(name) for name in STEPS)
        return DryRunResult(
            steps=steps,
            passed=all(step.outcome in (OUTCOME_PASSED, OUTCOME_NOT_CHECKED) for step in steps),
        )

    def _step(self, name: str) -> DryRunStep:
        if name in self.seen:
            return self.seen[name]
        if name == STEP_ACCOUNT_EXISTS:
            # The one step that is never executed, and it carries its note in both shapes:
            # ``not_checked`` when the run got that far, ``skipped`` when a rule fell first.
            return DryRunStep(
                step=name,
                outcome=OUTCOME_NOT_CHECKED if self._complete() else OUTCOME_SKIPPED,
                note=NOTE_WOULD_CALL_NEXTCLOUD,
            )
        return DryRunStep(step=name, outcome=OUTCOME_SKIPPED)

    def _complete(self) -> bool:
        return all(
            self.seen.get(name) is not None and self.seen[name].outcome == OUTCOME_PASSED
            for name in STEPS
            if name != STEP_ACCOUNT_EXISTS
        )


async def dry_run(
    token: str,
    config: ExchangeConfig,
    *,
    clock: Callable[[], float] | None = None,
    now: Callable[[], float] | None = None,
    max_token_bytes: int = MAX_TOKEN_BYTES,
) -> DryRunResult:
    """Check ``token`` against ``config`` and answer with one named outcome per step.

    The order of the steps is the order of ``ExchangeTokenChecker.claims_of``, and its own
    ordering comment is the reason it may not be made more convenient here: the cheap, local
    rules fall first, the outgoing key fetch happens only for a token that already looks like
    one of our issuer, and the signature-covered checks are the last word on everything the
    earlier steps read unverified. A dry run that reordered them would answer a different
    question than the operating path answers.

    **The one deliberate deviation.** In operation ``chain.looks_like_jws`` decides *before*
    ``claims_of`` which branch ever looks at a token. This function puts its own three input
    bounds (``token_present``, ``token_size``, ``token_is_text``) in front of that switch,
    because it has to bound its own input before it does anything with it at all. The
    deviation is written down here so that it stays a decision and does not quietly become
    sloppiness; it changes no verdict, because a token that falls at any of the three would
    be refused on either side of the switch.

    ``clock`` is the monotonic clock of the key set layer and ``now`` the wall clock of the
    claim rules, separate and separately injectable for the reason the checker keeps them
    apart: whoever checks ``exp`` against a monotonic clock checks it against the uptime of
    the process.
    """
    run = _Run()
    settings = config.settings

    if not token:
        return run.fell(STEP_TOKEN_PRESENT, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_TOKEN_PRESENT)

    # Bytes before base64, base64 before JSON, exactly as in the checker: the bound stands in
    # front of the first decoding step and not behind it (T-24-25). The number is imported
    # and never typed a second time, so the two sides cannot draw different lines.
    if len(token) > max_token_bytes:
        return run.fell(STEP_TOKEN_SIZE, REASON_EXCHANGE_MALFORMED)
    try:
        measured = len(token.encode("utf-8"))
    except UnicodeEncodeError:
        # The character count already held, so the size step is answered; what falls is the
        # rule that an input which cannot be encoded is refused rather than repaired.
        run.held(STEP_TOKEN_SIZE)
        return run.fell(STEP_TOKEN_IS_TEXT, REASON_EXCHANGE_MALFORMED)
    if measured > max_token_bytes:
        return run.fell(STEP_TOKEN_SIZE, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_TOKEN_SIZE)
    run.held(STEP_TOKEN_IS_TEXT)

    # The shape switch is asked, never re-implemented. Counting the dots here would be a
    # second copy of the one weiche of the chain and precisely the drift this plan exists to
    # rule out; a token of another shape goes to the store branch in operation (EXCH-04) and
    # never reaches the checker at all, which is why this step has no rejection phrase of its
    # own and stands in the named exception set of the drift gate.
    if not looks_like_jws(token):
        return run.fell(STEP_TOKEN_SHAPE, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_TOKEN_SHAPE)

    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        # Deliberately by class and not by the list of exceptions one library version happens
        # to raise on unverified bytes; the checker's comment carries the measurement.
        return run.fell(STEP_HEADER_READABLE, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_HEADER_READABLE)

    algorithm = header.get("alg")
    if algorithm not in settings.algorithms:
        return run.fell(STEP_ALGORITHM_ALLOWED, REASON_EXCHANGE_KEY)
    run.held(STEP_ALGORITHM_ALLOWED)

    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        return run.fell(STEP_KEY_NAMED, REASON_EXCHANGE_KEY)
    run.held(STEP_KEY_NAMED)

    header_typ = header.get("typ")
    if header_typ is not None and (
        not isinstance(header_typ, str) or header_typ.lower() not in _TYP_HEADERS_FOLDED
    ):
        # Tolerated when present, never required. A missing header type is no reason to
        # refuse; a foreign one is a different artifact altogether.
        return run.fell(STEP_HEADER_TYPE, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_HEADER_TYPE)

    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return run.fell(STEP_PAYLOAD_READABLE, REASON_EXCHANGE_MALFORMED)
    run.held(STEP_PAYLOAD_READABLE)

    if unverified.get("iss") != settings.issuer:
        return run.fell(STEP_ISSUER_MATCHES, REASON_EXCHANGE_ISSUER)
    run.held(STEP_ISSUER_MATCHES)

    # The signature-covered half is task 2 of plan 24-05. Until it stands, everything behind
    # the issuer filter is unreached rather than passed, and ``finish`` marks it skipped: a
    # skipped step keeps the verdict false, so no half built run can read as green.
    _parked = (clock, now, kid, algorithm)
    assert _parked is not None  # noqa: S101 - the seam of task 2, named instead of dropped
    return run.finish()
