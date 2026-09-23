"""The token exchange path of milestone v1.6: its configuration, read once at startup.

This file exists next to ``verifier.py`` instead of inside it. The ``StoreTokenVerifier``
answers for the tokens this server issued itself, and it stays byte for byte what it was:
that is the first success criterion of this phase, and a path that accepts tokens of a
foreign issuer has no business growing inside the class that answers for our own. The
second half of this file is the chain of plan 22-02: it puts that untouched verifier and
the checker of phase 21 side by side and decides between them on the shape of the token,
before either of them has looked at anything.

The configuration is read here and not in ``exchange.py`` on purpose. That module promises
in its own docstring that it reads nothing from the environment, and that promise is what
makes every one of its rules provable against hand built settings in a test: it can be
handed a deliberately broken configuration and has to refuse it. A module that also read
the environment would have to be tested with the environment. So one module owns the rules
and this one owns the reading, and the seam between them is a :class:`ValueError` that
becomes a :class:`~mcp_connector.errors.ToolError` in exactly one place below.

The path is off in the factory state (CONF-01). Off means: no variable of the namespace is
read, no default is computed, and nothing about an installation that never heard of this
milestone changes. What an operator configures, and what this module defaults:

``config.ENV_EXCHANGE_ENABLED``
    The switch. Off unless set, and nothing below it is reached while it is off.
``config.ENV_EXCHANGE_ISSUER``
    Required. The realm URL of the provider, HTTPS, without a trailing slash. No default
    can be guessed: it decides whose signatures this server will trust.
``config.ENV_EXCHANGE_AZP``
    Required, comma separated. Which authorized parties may act at all. No default either,
    for the same reason read the other way round: it decides who may act.
``config.ENV_EXCHANGE_JWKS_URI``
    Defaults to the issuer plus :data:`DEFAULT_JWKS_PATH`.
``config.ENV_EXCHANGE_JWKS_ORIGIN``
    Defaults to nothing, which leaves the same origin rule of phase 21 on the issuer. Only
    a split network (openDesk, agency deployments with an internal certs host) needs it.
``config.ENV_EXCHANGE_AUDIENCE``
    Defaults to the resource URL of this instance, the same value this server writes into
    its own tokens. Never a generic name: a token minted for instance A must not hold at
    instance B (T-22-03). The default therefore needs ``config.ENV_PUBLIC_URL`` to derive
    it from, and an armed path without either variable is refused rather than defaulted:
    ``config.public_url`` would answer ``config.DEFAULT_PUBLIC_URL``, which is the same
    loopback placeholder on every installation and would be no instance boundary at all
    (CR-01 of 22-REVIEW.md).
``config.ENV_EXCHANGE_ACCOUNT_CLAIM``
    Defaults to ``config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM``, which is the one claim every
    exchanged token of Keycloak carries.
``config.ENV_EXCHANGE_ALGORITHMS``
    Defaults to ``exchange.DEFAULT_EXCHANGE_ALGORITHMS``, comma separated when set.
``config.ENV_EXCHANGE_MAPPING``
    Which mapping profile of ``oauth/mapping.py`` turns the checked claim set of an
    exchanged token into the canonical Nextcloud principal (MAP-01). Defaults to
    ``config.DEFAULT_EXCHANGE_MAPPING``: the value of the configured claim is the account
    id itself, which is the case in which the provider carries the canonical id and the
    assumption an installation without an F13 answer is least wrong with. The rules of a
    profile live in the mapping module and are not written a second time here.
``config.ENV_EXCHANGE_OIDC_PROVIDER_ID``
    No default, and it belongs to the sub profile alone: the positive numeric id of the
    ``user_oidc`` provider its derivation is keyed with. Set while the account id profile
    is in force, it is refused rather than ignored, because a value nobody reads is the
    same half state an empty variable is.

Nothing that came out of the environment is logged or put into a message anywhere in this
module: not the issuer, not the audience, not the claim name. Refusals name variables. An
administrator's value can reach this process over HTTP through the settings overlay of the
ExApp, and a container log is read by everyone who can read container logs (T-22-04).
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from mcp.server.auth.provider import AccessToken
from starlette.requests import Request

from .. import config
from ..errors import ToolError
from .exchange import (
    DEFAULT_EXCHANGE_ALGORITHMS,
    ExchangeRefused,
    ExchangeSettings,
    ExchangeTokenChecker,
)
from .mapping import MappingSettings
from .metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from .verifier import IdentitySource, OAuthIdentity

__all__ = [
    "DEFAULT_JWKS_PATH",
    "EXCHANGE_CLAIM",
    "ChainedVerifier",
    "ExchangeBranch",
    "ExchangeConfig",
    "StoreBranch",
    "build_chain",
    "exchange_shaped_request",
    "load_exchange_config",
    "looks_like_jws",
]

logger = logging.getLogger("mcp_connector.oauth.chain")


#: Where Keycloak publishes the key set of a realm, and the issuer is the realm URL, so
#: the default is a concatenation and never a discovery request. An outgoing call at
#: startup would turn an outage at the provider into a container that cannot start, and it
#: would buy nothing: the same origin rule of :class:`~mcp_connector.oauth.exchange.
#: ExchangeSettings` judges the value this module composes exactly as it judges one an
#: operator typed, so a wrong host is refused either way. A provider that publishes its
#: keys somewhere else is configured, not discovered.
DEFAULT_JWKS_PATH = "/protocol/openid-connect/certs"

#: What every refusal of this module tells an operator to do. Built from the constants of
#: ``config`` rather than spelled out, so that renaming a variable there cannot leave a
#: hint behind that names a variable nobody reads any more.
_HINT = (
    f"The token exchange path stays off until {config.ENV_EXCHANGE_ENABLED} arms it. "
    f"Armed, it requires {config.ENV_EXCHANGE_ISSUER} and {config.ENV_EXCHANGE_AZP}; "
    f"{config.ENV_EXCHANGE_JWKS_URI}, {config.ENV_EXCHANGE_JWKS_ORIGIN}, "
    f"{config.ENV_EXCHANGE_AUDIENCE}, {config.ENV_EXCHANGE_ACCOUNT_CLAIM}, "
    f"{config.ENV_EXCHANGE_ALGORITHMS} and {config.ENV_EXCHANGE_MAPPING} have defaults, "
    f"documented in oauth/chain.py; {config.ENV_EXCHANGE_OIDC_PROVIDER_ID} belongs to the "
    "sub profile alone."
)


@dataclass(frozen=True, slots=True)
class ExchangeConfig:
    """The validated configuration of the exchange path, or nothing at all.

    Frozen like the settings it carries: an allowlist that a later line could widen would
    be no allowlist, and the start is the one moment at which this is decided.
    """

    settings: ExchangeSettings
    #: Which claim of an exchanged token names the account. Since 23-01 the mapping below
    #: reads it: it travels as ``mapping.account_claim`` into
    #: ``mapping.principal_from_claims``, which is the one function that turns the checked
    #: claim set into the canonical principal. It stays here as well, as the configured
    #: value next to the other variables of its namespace.
    account_claim: str
    #: The validated mapping profile of MAP-01, built by :func:`load_exchange_config` from
    #: the two mapping variables of the namespace. Half configured breaks the start with a
    #: named refusal; nothing reads an identity out of it before plan 23-02.
    mapping: MappingSettings


def load_exchange_config(env: Mapping[str, str] | None = None) -> ExchangeConfig | None:
    """The environment as a validated configuration, as ``None``, or as a named refusal.

    ``None`` is the factory state and the only silent answer this function gives. Every
    other incomplete state is a :class:`~mcp_connector.errors.ToolError`, which both entry
    points let travel into their existing handler, where it becomes a named message and
    exit code 2. Half configured is never served (T-22-01, T-22-02).
    """
    source = os.environ if env is None else env
    if not config.exchange_enabled(source):
        _refuse_a_disarmed_configuration(source)
        return None

    issuer = _required(source, config.ENV_EXCHANGE_ISSUER)
    azp_allowed = _allowlist(_required(source, config.ENV_EXCHANGE_AZP), config.ENV_EXCHANGE_AZP)
    jwks_uri = _optional(source, config.ENV_EXCHANGE_JWKS_URI) or f"{issuer}{DEFAULT_JWKS_PATH}"
    jwks_origin = _optional(source, config.ENV_EXCHANGE_JWKS_ORIGIN)
    audience = _optional(source, config.ENV_EXCHANGE_AUDIENCE) or _derived_audience(source)
    account_claim = (
        _optional(source, config.ENV_EXCHANGE_ACCOUNT_CLAIM)
        or config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM
    )
    mapping_name = _optional(source, config.ENV_EXCHANGE_MAPPING) or config.DEFAULT_EXCHANGE_MAPPING
    oidc_provider_id = _provider_id(_optional(source, config.ENV_EXCHANGE_OIDC_PROVIDER_ID))
    raw_algorithms = _optional(source, config.ENV_EXCHANGE_ALGORITHMS)
    algorithms = (
        _allowlist(raw_algorithms, config.ENV_EXCHANGE_ALGORITHMS)
        if raw_algorithms
        else DEFAULT_EXCHANGE_ALGORITHMS
    )

    try:
        settings = ExchangeSettings(
            issuer=issuer,
            jwks_uri=jwks_uri,
            audience=audience,
            azp_allowed=azp_allowed,
            jwks_origin=jwks_origin,
            algorithms=algorithms,
        )
    except ValueError as exc:
        # The rules are phase 21's and are not written a second time here: a copy would
        # drift and the drift would show as a configuration that passes one check and
        # fails the other. What this line owes an operator is the translation. A bare
        # ValueError in a container log names no variable and suggests a bug in this app
        # rather than a value that has to change. The text of the ValueError names the
        # field and never the value, which is why it can be carried over unchanged.
        raise ToolError(
            message=f"The token exchange configuration is invalid: {exc}.", hint=_HINT
        ) from None
    try:
        mapping = MappingSettings(
            strategy=mapping_name, account_claim=account_claim, oidc_provider_id=oidc_provider_id
        )
    except ValueError as exc:
        # The same seam as three lines above: the rules live in ``oauth/mapping.py`` and
        # are not written a second time here. The translation names the two variables the
        # operator can act on, because the ValueError names a field, and a field name in a
        # container log points at this app rather than at the value that has to change. The
        # text of the ValueError never repeats a value, which is why it travels unchanged.
        raise ToolError(
            message=(
                f"The token exchange mapping configured by {config.ENV_EXCHANGE_MAPPING} and "
                f"{config.ENV_EXCHANGE_OIDC_PROVIDER_ID} is invalid: {exc}."
            ),
            hint=_HINT,
        ) from None
    return ExchangeConfig(settings=settings, account_claim=account_claim, mapping=mapping)


def _refuse_a_disarmed_configuration(source: Mapping[str, str]) -> None:
    """Refuse a start that configured the path and never armed it (T-22-02).

    The opposite half of CONF-01, and the one that is easy to leave out: an operator who
    wrote six variables and forgot the switch gets a server that quietly serves without the
    path, and believes the opposite until somebody measures it. Every name of the namespace
    is walked, so a variable added to ``config`` later cannot fall through this check
    without being added to ``config.EXCHANGE_VARIABLES`` first, which is where a test holds
    it.
    """
    for name in config.EXCHANGE_VARIABLES:
        if name == config.ENV_EXCHANGE_ENABLED:
            continue
        if (source.get(name) or "").strip():
            raise ToolError(
                message=(
                    f"{name} is set, but {config.ENV_EXCHANGE_ENABLED} does not arm the "
                    "token exchange path."
                ),
                hint=(
                    "A configured path that nothing armed is the silent half state CONF-01 "
                    f"was written against. Either arm it with {config.ENV_EXCHANGE_ENABLED} "
                    "or remove the variables of this namespace from the deployment."
                ),
            )


def _derived_audience(source: Mapping[str, str]) -> str:
    """The resource URL of this instance, or a refusal when no address names it (CR-01).

    The audience is the only thing that binds a foreign signed token to this installation.
    Our own tokens are random values against a local store, so a mix-up between instances
    is structurally impossible there; an exchanged token is signed by a provider that may
    serve a dozen agencies from one realm, and the audience is what keeps a token minted
    for instance A from holding at instance B (T-22-03).

    :func:`config.public_url` answers ``config.DEFAULT_PUBLIC_URL`` when nothing is
    configured, and that value is byte for byte the same on every installation. Derived
    from it, the audience would be a placeholder no operator has ever seen and every
    equally misconfigured instance would accept the same one. That is the half state the
    docstring of :func:`load_exchange_config` refuses everywhere else, so it is refused
    here too, and by name: the operator has to set an address or an audience.

    An address that is explicitly the loopback default is not this case and passes: it was
    typed, and a development run against ``http://127.0.0.1:8765`` is a legitimate
    deployment. What is refused is the absence of any answer, which is why this asks the
    variable and not the value :func:`config.public_url` computed.
    """
    if not (source.get(config.ENV_PUBLIC_URL) or "").strip().rstrip("/"):
        raise ToolError(
            message=(
                f"{config.ENV_EXCHANGE_AUDIENCE} is not set and {config.ENV_PUBLIC_URL} "
                "names no address to derive it from."
            ),
            hint=(
                "The audience is what binds a token of the configured provider to this "
                f"installation. Set {config.ENV_PUBLIC_URL} to the address clients reach "
                f"this app at, or name the audience with {config.ENV_EXCHANGE_AUDIENCE}. "
                f"{_HINT}"
            ),
        )
    return f"{config.public_url(source)}{RESOURCE_SUFFIX}"


def _required(source: Mapping[str, str], name: str) -> str:
    """A value the armed path cannot default, named in the refusal, never repeated in it."""
    value = (source.get(name) or "").strip()
    if not value:
        raise ToolError(
            message=f"{name} is not set, and the token exchange path is armed.", hint=_HINT
        )
    return value


def _optional(source: Mapping[str, str], name: str) -> str | None:
    """A value with a documented default, or ``None`` when the variable is not there.

    A variable that stands in the deployment and says nothing is refused rather than
    defaulted. It is a typo or a template that was filled in with an empty value, and every
    one of these values decides something: which host holds the keys, which audience a
    token must name, which claim names the account. Silently answering such a line with a
    default is the same half state this whole module exists to refuse.
    """
    if name not in source:
        return None
    value = (source[name] or "").strip()
    if not value:
        raise ToolError(
            message=f"{name} is set to an empty value.",
            hint=(
                f"Remove the variable to take the documented default, or give it a value. {_HINT}"
            ),
        )
    return value


def _provider_id(raw: str | None) -> int | None:
    """The provider id as a positive whole number, or ``None`` when it is not configured.

    The refusal follows the rule of every reader in this module: it names the variable and
    never repeats the value, and it falls here rather than in the mapping constructor so an
    operator reads "this variable is not a number" instead of a type complaint about a
    field of an object no deployment ever sees. What number is acceptable for which profile
    stays a rule of ``oauth/mapping.py`` and is not judged here.
    """
    if raw is None:
        return None
    if not raw.isdigit() or int(raw, 10) <= 0:
        raise ToolError(
            message=(f"{config.ENV_EXCHANGE_OIDC_PROVIDER_ID} is not a positive whole number."),
            hint=_HINT,
        )
    return int(raw, 10)


def _allowlist(raw: str, name: str) -> tuple[str, ...]:
    """A comma separated list as a tuple of non-empty entries, never an empty allowlist.

    The shape ``entry_oauth.load_settings`` reads the OIDC algorithms with, for the two
    lists of this namespace. An empty result is refused and not passed on: phase 21 would
    refuse it as well, but one line later and with a message about a sequence rather than
    about the variable that has to change. An empty allowlist is also the configuration
    error that hides longest, because it refuses every token and therefore looks like a
    broken deployment rather than like a rule nobody wrote.
    """
    entries = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not entries:
        raise ToolError(
            message=f"{name} names no value.",
            hint=f"Separate several values with commas. {_HINT}",
        )
    return entries


# --- The chain: one switch, two branches, no fallback -------------------------------------

#: The one key of ``AccessToken.claims`` the checked claim set of an exchanged token travels
#: under. One nested key and not the claim set spread out next to our own claims, because a
#: foreign token may carry a claim of any name it likes: spread out, a claim called
#: ``auth_id`` would sit in the very field the store branch reads to find the authorization
#: behind one of our own tokens (T-22-07). Nested, the two can never be confused, and a
#: reader of this field can tell at a glance which issuer a token came from.
EXCHANGE_CLAIM = "exchange_claims"


class StoreBranch(IdentitySource, Protocol):
    """The branch that answers for the tokens this server issued itself, plus its eraser.

    A protocol and not the class, for the reason ``verifier.py`` states for ``ClientLookup``:
    the branch is handed into the chain and never rebuilt inside it, so the chain names the
    three methods it uses and nothing else. In the application this is always the one
    :class:`~mcp_connector.oauth.verifier.StoreTokenVerifier` of the deployment.
    """

    def invalidate(self) -> None: ...


class ExchangeBranch(Protocol):
    """The branch that answers for the tokens of the one configured foreign issuer.

    The two methods :class:`~mcp_connector.oauth.exchange.ExchangeTokenChecker` offers the
    chain, named here so that a test can hand in a stand-in that fails on contact. That is
    what makes "a token of this server never reaches the foreign checker" a measurement
    rather than a sentence.
    """

    async def claims_of(self, token: str) -> dict[str, Any]: ...

    def forget_keys(self) -> None: ...


def looks_like_jws(token: str) -> bool:
    """Whether ``token`` has the shape of a compact JWS: two dots, three non-empty segments.

    This is the whole switch of the chain, and it is structural rather than secret. The
    access tokens this server issues are ``secrets.token_urlsafe`` values, and that alphabet
    contains no dot; a compact JWS carries exactly two by RFC 7515. So the form of a token
    says which branch may look at it, the decision falls before any check, and no branch is
    ever the fallback of the other (pitfall 1 of the research, T-22-06).

    Everything else goes to the store branch: four dots (a compact JWE), one dot, no dot at
    all, or a shape with an empty segment. There it is refused as an unknown token, and it
    never reaches the foreign checker. That direction is deliberate: the store branch is the
    code this deployment has been running all along, and an unknown token costs it one
    indexed lookup by digest.
    """
    segments = token.split(".")
    return len(segments) == 3 and all(segments)


#: How the transport boundary reads a bearer credential. Spelled out here rather than
#: imported, because the middleware keeps it private and this plan does not touch that file.
#: What is deliberately not copied is the line below it: whether the value behind the scheme
#: is of this path is :func:`looks_like_jws` and exists exactly once.
#:
#: A copy needs something holding it to its original, and since WR-03 of 22-REVIEW.md that is
#: ``test_the_throttle_and_the_transport_boundary_read_the_same_bearer``: it drives the real
#: boundary over a matrix of header forms and demands that the two readings agree on every
#: one. Sharing the constant is the better fix and belongs to the phase that may touch
#: ``exapp/middleware.py``; until then the agreement is measured rather than assumed.
_BEARER_PREFIX = "bearer "


def exchange_shaped_request(request: Request) -> bool:
    """Whether this request carries a bearer of the shape the exchange branch answers for.

    This is the condition the throttle of the MCP route is handed (EXCH-05), and it lives
    here and not in ``throttle.py`` for one reason: the rule that tells the two kinds of
    token apart may exist exactly once. Written a second time next to the counter, the
    switch of this module and the switch of the throttle would drift apart the first time
    either of them was corrected, and a throttle counting a different set of requests than
    the one it is supposed to bound is worse than no throttle at all. So that module knows
    nothing of this path: it takes a condition and asks it.

    The header is read the way the transport boundary reads it, the scheme case
    insensitively and the rest stripped, so a value that boundary treats as a bearer is the
    same value this function judges. Everything else, no header, another scheme, an empty
    token, a token without the shape, is not of this path and is therefore never counted and
    never refused: it is the call this deployment has been serving all along.
    """
    header = request.headers.get("authorization") or ""
    if header[: len(_BEARER_PREFIX)].lower() != _BEARER_PREFIX:
        return False
    return looks_like_jws(header[len(_BEARER_PREFIX) :].strip())


class ChainedVerifier:
    """The store verifier and the exchange checker side by side, behind one switch.

    The store branch is the unchanged :class:`~mcp_connector.oauth.verifier.
    StoreTokenVerifier` of this deployment, handed in and never rebuilt: a second object
    would be a second cache and a second answer to the one question of who may act.

    The chain is itself an ``IdentitySource``, and that is a security property rather than
    tidiness. The transport boundary lets a verifier without an identity half pass the
    request on (it has nothing to hand over, and the credential layer refuses on its own),
    while an identity source that answers ``None`` ends the request. An exchange token has
    no identity in this phase, so the chain must be the second kind; a plain verifier would
    turn "refused" into "served without an identity".
    """

    def __init__(
        self, *, store: StoreBranch, checker: ExchangeBranch, config: ExchangeConfig
    ) -> None:
        self._store = store
        self._checker = checker
        self._config = config

    def __repr__(self) -> str:
        # The class of the store branch and the one word that matters, never a configured
        # value: an issuer or an audience can name an internal provider (T-22-04).
        return f"ChainedVerifier(store={type(self._store).__name__}, exchange='armed')"

    async def verify_token(self, token: str) -> AccessToken | None:
        """The SDK protocol, answered by exactly one of the two branches and never by both.

        The shape of the token picks the branch, and a refusal in it is the answer of this
        method. There is no second attempt in the other branch: a branch that catches what
        the other refused is a fallback, and a fallback makes every unknown token a run
        through foreign code, which is the one thing this phase is written against.
        """
        if not token:
            return None
        if not looks_like_jws(token):
            # The path this deployment has always taken, unchanged and alone. ``None`` from
            # here is the answer of the chain as well (T-22-06).
            return await self._store.verify_token(token)
        try:
            claims = await self._checker.claims_of(token)
            # Inside the same try as the call, and that is IN-01 of 22-REVIEW.md. The two
            # reads below assume a claim set that carries ``azp`` and ``exp``, which the
            # checker of phase 21 guarantees and an exchangeable ``ExchangeBranch`` does
            # not. Built four lines further down, a missing claim was a ``KeyError`` out of
            # a verifier and a 500 at the boundary, so the promise "every unexpected
            # exception of this branch is a refusal" ended just before the place it was
            # most likely to be needed.
            access = AccessToken(
                token=token,
                # The acting party of the checked claim set, which phase 21 guarantees to be
                # a non-empty string of the configured allowlist.
                client_id=str(claims["azp"]),
                scopes=[TOOL_SCOPE],
                expires_at=int(claims["exp"]),
                # The audience this server was configured to accept, not the one the token
                # named: the two are equal because the check made them equal, and the one
                # that travels on is ours (T-22-03).
                resource=self._config.settings.audience,
                # Empty on purpose. The canonical principal is born in the account mapping
                # of phase 23; a raw ``sub`` in this field would be a login name of a
                # foreign realm posing as the principal of this server, which is pitfall 5
                # of the research.
                subject=None,
                claims={EXCHANGE_CLAIM: claims},
            )
        except ExchangeRefused:
            # The same promise read the other way round: a checked refusal ends here and is
            # never offered to the store branch afterwards.
            return None
        except Exception as exc:
            # Fail closed means this one branch and no other. An exception travelling from a
            # verifier into the transport boundary would be a 500 where a 401 belongs, and
            # every other call of this process would keep running regardless, so turning it
            # into a refusal costs nothing and buys the promise of T-22-09. The line names
            # the type of the failure and nothing else: no token, no claim, no principal.
            logger.error("an exchanged token could not be checked: %s", type(exc).__name__)
            return None
        return access

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        """Who a verified token acts as: the store branch answers, the exchange branch does not.

        ``None`` for an exchanged token, and the transport boundary reads that as "this
        token may not act" and ends the request. That is the fail closed state EXCH-04 asks
        for while the account mapping does not exist yet, and it is where phase 23 (MAP-01)
        puts it: the configured claim onto a canonical principal, the existence check of the
        account, and the credential path. Exactly one place, and this is it.
        """
        if EXCHANGE_CLAIM in (access.claims or {}):
            return None
        return await self._store.resolve_identity(access)

    def invalidate(self) -> None:
        """One call, both layers: the answers of the store branch and the cached key set.

        The two halves of one window. The store branch forgets its five second cache, and
        the key set layer forgets keys that would otherwise stay usable for five minutes
        after a rotation. What the key set keeps are its two pre-authentication brakes
        (task 1 of this plan), because a revocation that reset them would be a way to order
        an outgoing fetch per invented key id.

        ``finally`` and not two plain statements (WR-04 of 22-REVIEW.md). The store branch
        of this deployment is a ``dict.clear`` and cannot throw, but the branch is a
        protocol on purpose, so the object here is whatever was handed in. For any
        implementation that can fail, a failure of the first half used to leave a rotated
        signature key usable for the five minutes of the cache, in the one moment somebody
        revoked: the stillest way this chain could fail. The exception still travels, so
        nothing about the failure is swallowed; only the second half is no longer skipped.
        """
        try:
            self._store.invalidate()
        finally:
            self._checker.forget_keys()


def build_chain(
    store_verifier: StoreBranch,
    *,
    env: Mapping[str, str] | None = None,
    config: ExchangeConfig | None = None,
) -> StoreBranch:
    """The one place a deployment hangs the chain in, and the one place it does not.

    Without a configured exchange path this returns ``store_verifier`` **itself**, not a
    wrapper that behaves like it today. The difference is the promise of this phase: at the
    transport boundary of an installation that never heard of this milestone hangs the very
    object that hung there before, and a test can say ``is`` about it instead of comparing
    behaviour and hoping the comparison was complete.

    ``config`` is the answer the entry point already read at startup, handed in so the
    environment is read once per application. Without it the reader runs here; in the off
    state both answers are ``None`` over the same mapping, so a caller that hands in the
    off state loses nothing but a dictionary lookup.
    """
    loaded = config if config is not None else load_exchange_config(env)
    if loaded is None:
        return store_verifier
    return ChainedVerifier(
        store=store_verifier,
        # Built here and nowhere else: one checker per application, holding the one key set
        # cache of the configured issuer. A checker per request would fetch the key set per
        # request, which is the load the cache of phase 20 exists to prevent.
        checker=ExchangeTokenChecker(loaded.settings),
        config=loaded,
    )
