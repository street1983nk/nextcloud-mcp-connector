"""The seven admin values of BL-06, TALK-04 and D-14, read out of the ExApp configuration.

The fifth one joined in phase 6 with ``NC_MCP_OAUTH_CIMD``: a switch that exists as a deploy
variable and as a documented sentence, but not in this chain, is a switch an installation
from the app store cannot reach at all, because such an installation never gets a deploy
variable (the whole reason this module exists). The sixth joined in phase 9 with
``NC_MCP_TALK_SEND``, the switch that closes the outgoing Talk channel of this app, and it is
here for exactly that reason: a countermeasure a store installation cannot reach is not one.
The seventh joined in phase 18 with ``NC_MCP_AUDIT_LOG``, the switch that decides whether
tool calls are recorded at all (D-14), and it is the one of the seven that ships off: a
record about named people that an administrator never asked for is the failure that switch
exists to prevent, so the end of this chain, the default in code, says no.

Three facts carry this module, and each of them is measured rather than assumed:

* **The read channel is the one this repository already runs.** ``oauth/crypto.py`` fetches
  the data key of this installation with a ``POST`` on
  ``/ocs/v2.php/apps/app_api/api/v1/ex-app/config/get-values`` and a JSON body
  ``{"configKeys": [...]}``. There is no ``GET`` on that resource; the shape was measured
  against a running AppAPI 34.0.0 in plan 03-08. The path and the field name are imported
  from that module here instead of being spelled a second time.
* **The config key IS the field id of the Declarative Settings form.** AppAPI's
  ``SetValueListener`` stores an admin value with
  ``ExAppConfigService::setAppConfigValue($app, $fieldId, $value)``, without a prefix, so
  the seven ids of ``exapp/admin_settings.py`` are exactly :data:`CONFIG_KEYS`
  (nextcloud/app_api v34.0.3, ``lib/Listener/DeclarativeSettings/SetValueListener.php``).
* **AppAPI 34 answers in lower case.** The entries carry ``configkey`` and ``configvalue``,
  the column names of ``ex_apps_config`` serialised straight out of the entity. The camel
  case spelling is what the write side takes and what a later version may answer with, so
  both are accepted.

**Why this module fails soft while the data key path fails hard.** An invented data key
looks like it works and silently makes every stored authorization unreadable, so
``crypto._read_key`` raises on every failure. A missing admin value means one thing only:
the administrator has not set anything. Falling back to the deploy environment is then the
correct answer, and stopping an installation over an unreachable OCS call would be the
wrong one. Every failure below is therefore an empty result plus exactly one log line.

**Why a 401 is told and not reported as a fault.** Plan 05-12 measured this read against a
running HaRP topology instead of guessing about it. The channel carries: with the app on
``enabled`` the same call answers ``200`` and returns a value that was set in the form. The
``401`` hangs on one thing only, the activation state, because
``AppAPIService::validateExAppRequestToNC`` accepts the app secret and then refuses over
``!$exApp->getEnabled()``, with ``ex-app/state`` as the only exempt path. The first start
after a deployment is always inside that window (``enable`` comes after ``init``), and inside
it there cannot be an admin value yet. So this one outcome is an INFO line that names the way
out, and every other failure of this read stays an ERROR. What does make a value take effect
is measured as well and unchanged: one disable and enable cycle, which stops and starts this
container (05-12-MEASUREMENTS.md, M1, M2, M3, M3b, M3c).

**Why ``config.normalize_base_url`` stays as it is.** The public address of this app is held
to a harder rule here than that function applies (https, with the loopback exception of RFC
8414), and the rule deliberately lives here instead of in it: the same function validates
``NC_MCP_URL``, the address of the Nextcloud this container talks to, and http on an internal
host is a legitimate deployment there. One shared rule would either break those installations
or leave this value unchecked (CR-01).

The precedence rule this implements, together with plan 05-04 which applies it: admin value,
then the ``NC_MCP_*`` variable of the deploy environment, then the default in code. That is
why :func:`admin_overlay` returns the spelling of those variables and not a settings object:
no signature in the existing code has to change for an admin value to take effect.
"""

import logging
import os
from collections.abc import Mapping
from typing import Any, NamedTuple
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx

from .. import config
from ..errors import ToolError
from ..nextcloud.clients.ocs import OCS_HEADERS
from ..nextcloud.credentials import appapi_auth_headers
from ..nextcloud.http import shared_client
from ..oauth import registry
from ..oauth.crypto import CONFIG_READ_FIELD, CONFIG_READ_SUFFIX, EXAPP_CONFIG_PATH

__all__ = [
    "CONFIG_KEYS",
    "FALSE_VALUES",
    "KEY_TO_ENV",
    "LOOPBACK_HOSTS",
    "PUBLIC_URL_KEY",
    "SWITCH_KEYS",
    "SWITCH_OFF",
    "SWITCH_ON",
    "TRUE_VALUES",
    "AdminValues",
    "admin_overlay",
    "admin_values",
    "derived_public_url",
    "read_values",
]

#: The hosts an issuer may carry without https, and the only exception RFC 8414 allows.
#: ``urlsplit(...).hostname`` answers in lower case and without the brackets of an IPv6
#: literal, so ``::1`` stands here without them; an additional entry ``[::1]`` would be a
#: line no comparison could ever reach. Membership of the full host name is the test, never
#: a prefix or a substring: ``localhost.example.com`` is a public host name.
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})

#: The field id of the public address. Spelled once, because ``entry_exapp.main`` asks
#: whether this one field was refused when it tells an administrator which setup state she
#: is looking at, and a second spelling there would be a string that drifts silently.
PUBLIC_URL_KEY = "public_url"

#: The seven keys, in the order the form declares its fields. They are the field ids of the
#: admin form and the configuration keys at the same time (see the module docstring).
#: ``oauth_cimd`` stands next to ``oauth_dcr`` because the code reads the two as one answer
#: (``registry.client_policy``: this switch AND the DCR switch), and two coupled switches
#: that sit apart in a form are two switches an administrator reads as independent.
#: ``talk_send`` comes after them for the same reason read the other way round: it is
#: independent of all four OAuth values, and putting it between them would tear that grouping
#: apart. ``audit_log`` is last and joined in phase 18; it is about none of the six above,
#: because it is about this app watching itself rather than about who may reach it.
CONFIG_KEYS: tuple[str, ...] = (
    PUBLIC_URL_KEY,
    "oauth_dcr",
    "oauth_cimd",
    "oauth_allowlist_only",
    "oauth_allowed_clients",
    "talk_send",
    "audit_log",
)

#: The variable each key stands for. The overlay speaks the language of the deploy
#: environment, because that is the language every reader of these values already reads.
KEY_TO_ENV: Mapping[str, str] = {
    PUBLIC_URL_KEY: config.ENV_PUBLIC_URL,
    "oauth_dcr": registry.ENV_DCR,
    "oauth_cimd": registry.ENV_CIMD,
    "oauth_allowlist_only": registry.ENV_ALLOWLIST_ONLY,
    "oauth_allowed_clients": registry.ENV_ALLOWED_CLIENTS,
    "talk_send": config.ENV_TALK_SEND,
    "audit_log": config.ENV_AUDIT_LOG,
}

#: The keys that carry a checkbox, named once so the validation cannot drift from the form.
#: Every one of them goes through :func:`_switch`, which refuses a value that is neither on
#: nor off instead of guessing a default. Five since phase 18: a refused ``audit_log`` leaves
#: the key out of the overlay, so the deploy variable and then the default in code decide,
#: and that default is off (``config.audit_log_enabled``).
SWITCH_KEYS: frozenset[str] = frozenset(
    {"oauth_dcr", "oauth_cimd", "oauth_allowlist_only", "talk_send", "audit_log"}
)

#: The spellings a switch may arrive in. Aligned with the two sets of ``oauth/registry.py``
#: on purpose and held equal by a test: a value that arms a switch in the environment has to
#: arm the same switch when it comes out of the admin form, or an administrator debugs a
#: difference nobody wrote down. A checkbox that arrives as a JSON boolean is turned into
#: ``"true"`` or ``"false"`` while the answer is parsed, so it lands in these sets as well.
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

#: What the four switches become. One spelling leaves this module, whatever came in.
SWITCH_ON = "on"
SWITCH_OFF = "off"

logger = logging.getLogger("mcp_connector.exapp.config_values")


class AdminValues(NamedTuple):
    """What one read of the admin values produced.

    ``overlay`` speaks the language of the deploy environment (see :data:`KEY_TO_ENV`),
    ``refused`` speaks the language of the form and holds the field ids of
    :data:`CONFIG_KEYS` that carried a value this module would not use. A field that was
    never filled in appears in neither.
    """

    overlay: dict[str, str]
    refused: frozenset[str]


async def read_values(
    *, env: Mapping[str, str] | None = None, client: httpx.AsyncClient | None = None
) -> dict[str, str]:
    """Return the stored admin values as raw strings, or an empty result.

    One attempt and no retry loop, like every other outgoing call of this project (D-37).
    The keys that carry no value are simply absent, and every failure is an empty dictionary
    plus one log line rather than an exception.

    The difference to the data key read path, spelled out because it is the whole reason
    this function exists next to ``crypto._read_key``: an invented data key makes every
    authorization unreadable, so that path fails hard, while a missing admin value only
    means that the administrator has not set anything, so this path falls back to the
    environment. An answer this module cannot read is nevertheless never counted as "no
    value": it is a failure with a log line, and the deploy environment stays in force
    (fail closed, T-05-02).

    ``client`` exists for one caller and one reason (plan 05-04): ``entry_exapp.main`` reads
    these values before it serves anything, in an event loop that is closed again as soon as
    the read returns. :func:`~mcp_connector.nextcloud.http.shared_client` binds its connection
    pool to the loop it is first used in, so a pool created there would be unusable in the
    loop uvicorn opens afterwards and its sockets would never be closed. Without the argument
    nothing changes: every other caller of this module runs inside the server loop and uses the
    shared client, exactly as it did before.
    """
    try:
        settings = config.exapp_settings(env)
    except ToolError:
        # Not a raise: the caller of this module is the enable hook and the start, and
        # neither may fall over because a variable of the deploy environment is missing.
        logger.error(
            "the admin values were not read: the AppAPI deploy environment is incomplete, "
            "so the deploy environment of this container stays in force"
        )
        return {}

    url = f"{settings.base_url}{EXAPP_CONFIG_PATH}{CONFIG_READ_SUFFIX}"
    if client is None:
        client = shared_client()
    try:
        response = await client.post(
            url,
            json={CONFIG_READ_FIELD: list(CONFIG_KEYS)},
            headers=_headers(settings),
        )
    except httpx.HTTPError:
        # No value of the request is repeated here: the headers carry the app secret.
        logger.error("the ExApp configuration at %s could not be read, the environment stays", url)
        return {}

    if response.status_code == httpx.codes.UNAUTHORIZED:
        # The one failure of this read that is expected, and it is measured rather than
        # assumed (05-12-MEASUREMENTS.md, M3b and M3c plus the source of AppAPI 34.0.0):
        # `AppAPIService::validateExAppRequestToNC` accepts the app secret and then falls
        # over `!$exApp->getEnabled()`, and only `ex-app/state` is exempt from that check
        # (plus `ex-app/status` while an install or an update runs). The configuration path
        # is not exempt and cannot become exempt without changing AppAPI. Every first start
        # after a deployment sits inside that window, because `enable` comes after `init`,
        # and inside it there cannot be an admin value yet, since the app did not exist
        # before. An ERROR line for the normal course of an installation is what made a
        # working installation look broken in this phase, so this one outcome is told and
        # not reported as a fault. Every other failure of this read stays an ERROR: none of
        # them is expected. Nothing else changes, the result stays empty and the deploy
        # environment stays in force.
        logger.info(
            "the admin values were not read on this start: Nextcloud answered 401, which is "
            "the expected answer while AppAPI does not have this app on enabled yet, and the "
            "first start after an installation is always inside that window. The deploy "
            "environment stays in force, and the values are read again on the next start of "
            "this container. That is why a value entered in the administration settings takes "
            "effect after this app has been disabled and enabled once. If this line appears on "
            "a start that followed an enable, then the app secret of this container is not the "
            "one Nextcloud stored for it."
        )
        return {}

    if response.status_code // 100 != 2:
        logger.error(
            "Nextcloud answered %s when the admin values were read, the environment stays",
            response.status_code,
        )
        return {}

    try:
        payload = response.json()
    except ValueError:
        logger.error("the answer to the admin value read was not JSON, the environment stays")
        return {}

    values = _config_values(payload)
    if values is None:
        # An unreadable envelope is never an empty one: a silent empty result would look
        # exactly like an administrator who configured nothing (T-05-02).
        logger.error("the admin value answer could not be read, so it is not treated as empty")
        return {}
    return values


async def admin_values(
    *, env: Mapping[str, str] | None = None, client: httpx.AsyncClient | None = None
) -> AdminValues:
    """The usable admin values, and the field ids that arrived and were refused.

    The second half is what :func:`admin_overlay` cannot answer, and the reason this
    function exists next to it: "no value in force" and "a value in force nowhere near
    usable" are the same empty overlay, and they are not the same state to be in. The one
    reader of the difference is ``entry_exapp.main``, which tells the administrator which of
    the two she is looking at instead of claiming the field is empty (05-14, line B).

    Only keys with a value that survives validation appear in the overlay. A blank value
    counts as unset and is refused by nobody, which is what makes the precedence rule work:
    the deploy environment wins whenever the administrator left a field empty.

    Validation is per key, so a typo in one field is never an outage of the other five, and
    the refusals are per key for the same reason.

    ``client`` is passed straight through to :func:`read_values`, where the one reason it
    exists is written down.
    """
    values = await read_values(env=env, client=client)

    overlay: dict[str, str] = {}
    refused: set[str] = set()
    for key in CONFIG_KEYS:
        raw = values.get(key)
        if raw is None or not raw.strip():
            continue
        usable = _usable_value(key, raw)
        if usable is None:
            refused.add(key)
            continue
        overlay[KEY_TO_ENV[key]] = usable
    return AdminValues(overlay, frozenset(refused))


async def admin_overlay(
    *, env: Mapping[str, str] | None = None, client: httpx.AsyncClient | None = None
) -> dict[str, str]:
    """Return the usable admin values, keyed by the variable name they stand for.

    The overlay half of :func:`admin_values`, for every caller that has no use for the
    refused field ids.
    """
    return (await admin_values(env=env, client=client)).overlay


def _usable_value(key: str, raw: str) -> str | None:
    """The validated form of one admin value, or ``None`` when it is not usable."""
    if key == PUBLIC_URL_KEY:
        return _public_url(raw)
    if key in SWITCH_KEYS:
        return _switch(key, raw)
    # oauth_allowed_clients travels unchanged: registry._entries splits, strips and
    # deduplicates it already, and a second implementation of that would be a second
    # answer to the same question.
    return raw.strip()


def _public_url(raw: str) -> str | None:
    """The public base URL, or ``None`` plus a warning that never quotes the value.

    This is the most dangerous of these values and the reason the rule here is harder
    than :func:`config.normalize_base_url` alone: it becomes the ``issuer`` of the
    authorization server metadata and the ``resource`` of the protected resource metadata
    (security domain V5, T-05-01).

    Three of the extra conditions are the ones ``registry.redirect_uri_allowed`` names for a
    return address, for the same reasons: a fragment is where a token hides from a server
    log, credentials in a URL render as a host in more than one client, and an address this
    library cannot take apart is not one a browser and this server would agree about.

    The fourth condition is this function's own, and it is the one CR-01 found missing: this
    value becomes the ``issuer`` of the authorization server metadata, the SDK refuses an
    issuer that is not https unless it points at loopback (RFC 8414), and until this rule
    stood here that refusal only surfaced where it strikes, in ``provider.auth_routes``
    during the next start. Refusing the value here is the prevention half of CR-01; the
    rescue half lives in ``entry_exapp.main``.

    What survives all of that leaves in one spelling, see :func:`_one_spelling` (IN-03).
    """
    outcome = _validated_address(raw)
    if outcome[0] is None:
        return _rejected("public_url", outcome[1])
    return outcome[0]


def _validated_address(raw: str) -> tuple[str, None] | tuple[None, str]:
    """One public address candidate through the whole rule, or the reason it fails.

    The validation core of :func:`_public_url`, extracted for BL-17 so the derived candidate
    of :func:`derived_public_url` runs through THE SAME rule as a value an administrator
    typed: one rule, two log texts, and the two sources cannot drift apart. The reason never
    contains the value, so both callers may log it verbatim (T-05-03).
    """
    candidate = raw.strip().rstrip("/")
    try:
        candidate = config.normalize_base_url(candidate)
    except ToolError:
        return None, "is not a usable base URL"

    parts = urlsplit(candidate)
    if parts.fragment:
        return None, "carries a fragment"
    try:
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None, "has a host or a port this server cannot read"
    if not host or parts.username or parts.password:
        return None, "has no host or carries credentials"
    if port is not None and not 0 < port <= 65535:
        return None, "has a port outside the range 1 to 65535"
    if parts.scheme != "https" and host not in LOOPBACK_HOSTS:
        return None, (
            "is http on a host that is not loopback; the issuer of the authorization "
            "server has to be https (RFC 8414)"
        )
    return _one_spelling(parts, host=host, port=port), None


def derived_public_url(env: Mapping[str, str] | None = None) -> str | None:
    """The public address derived from ``NEXTCLOUD_URL``, or ``None`` (BL-17).

    The derived form is ``<NEXTCLOUD_URL>/exapps/<APP_ID>`` and never the bare instance
    root, and every part of that form is measured rather than assumed:
    ``scripts/bootstrap_exapp.sh`` builds exactly this address for the local topology
    (``${BASE_URL}/exapps/${APP_ID}``), ``docs/exapp-install.md`` names it as where a HaRP
    ExApp is reachable, and AIO sets ``NEXTCLOUD_URL`` to the public custom domain
    (``'nextcloud_url' => 'https://' . getenv('NC_DOMAIN')``, quoted in
    :func:`config.deployment_hosts`). This is the third link of the precedence chain of
    plan 05-01: a stored admin value and the deploy variable both win over it, and
    ``entry_exapp._resolved_env`` only asks when neither produced an address.

    Assumption A2 of phase 05 said: no derivation, because AppAPI may rewrite ``https`` to
    ``http`` and the value may be an internal name, so a derived address would be a silent
    default with broken discovery. The answer here is validation instead of trust: the
    candidate runs through :func:`_validated_address`, the SAME core that judges an admin
    form value (https or loopback per RFC 8414, CR-01; one spelling per IN-03), so a
    downgraded or internal value derives nothing and the fail-closed path of ``main`` stays.

    Fail soft on purpose, unlike ``config.exapp_settings``: this runs on every start,
    including the ones with an incomplete environment, and a missing value means exactly
    "nothing to derive from", which is ``None`` without a log line. An unusable value is one
    INFO line that names the variable and the reason, never the value (T-05-03).
    """
    source = os.environ if env is None else env
    base = (source.get(config.ENV_NEXTCLOUD_URL) or "").strip().rstrip("/")
    app_id = (source.get(config.ENV_APP_ID) or "").strip()
    if not base or not app_id:
        return None

    outcome = _validated_address(f"{base}/exapps/{app_id}")
    if outcome[0] is None:
        logger.info(
            "no public address was derived on this start: the address built from %s %s. The "
            "existing ways stay open: enter one in the Nextcloud administration settings of "
            "this app, or set %s.",
            config.ENV_NEXTCLOUD_URL,
            outcome[1],
            config.ENV_PUBLIC_URL,
        )
        return None
    return outcome[0]


def _one_spelling(parts: SplitResult, *, host: str, port: int | None) -> str:
    """The same address with a scheme and a host nobody has to spell twice (IN-03).

    RFC 3986 makes the scheme (section 3.1) and the host (section 3.2.2) case insensitive
    and everything after them case sensitive, so this levelling loses nothing and the path
    and the query are left exactly as they arrived.

    It matters because this value becomes the ``issuer`` of the authorization server
    metadata and the prefix of ``resource``, and clients compare both character by
    character; ``docs/client-setup.md`` and ``docs/oauth-setup.md`` say so about the
    trailing slash for the same reason. Without this an administrator who typed one capital
    letter, and then entered her address lower case in the client, failed a comparison that
    no log line on either side explains.

    ``urlsplit(...).hostname`` answers lower case and without the brackets of an IPv6
    literal, so the brackets are put back here; the port travels as the number it was
    already read as, so a leading zero or an empty ``:`` cannot survive either.
    """
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))


def _switch(key: str, raw: str) -> str | None:
    """One checkbox value, normalised to ``"on"`` or ``"off"``, or refused.

    No silent default, for the reason ``registry._switch`` gives: a value nobody
    understands is a typo, and a typo is not a security switch. The difference to that
    function is that a refused value here leaves the key out of the overlay entirely, so
    the environment and then the default in code decide, exactly as before.
    """
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return SWITCH_ON
    if value in FALSE_VALUES:
        return SWITCH_OFF
    return _rejected(
        key,
        "is neither on nor off (understood are "
        f"{', '.join(sorted(TRUE_VALUES))} and {', '.join(sorted(FALSE_VALUES))})",
    )


def _rejected(key: str, why: str) -> None:
    """Name the field and the reason, never the value: it came in over HTTP (T-05-03)."""
    logger.warning(
        "the admin value for %s %s, so it is ignored and the deploy environment stays in "
        "force for it. Correct it in the Nextcloud administration settings of this app.",
        key,
        why,
    )


def _headers(settings: config.ExAppSettings) -> dict[str, str]:
    """The OCS headers plus the AppAPI identity, in the app context (empty user id)."""
    headers = dict(OCS_HEADERS)
    headers.update(
        appapi_auth_headers(
            "",
            app_id=settings.app_id,
            app_version=settings.app_version,
            aa_version=settings.aa_version,
            app_secret=settings.app_secret,
        )
    )
    return headers


def _config_values(payload: Any) -> dict[str, str] | None:
    """Pull our seven values out of the OCS envelope, or refuse to guess.

    ``None`` means the answer could not be read and is therefore not an empty one. The three
    accepted shapes are the ones ``crypto._config_value`` accepts: a list of entries with
    lower case field names, the same list in camel case, and a mapping of key to value.
    """
    if not isinstance(payload, dict):
        return None
    ocs = payload.get("ocs")
    if not isinstance(ocs, dict) or "data" not in ocs:
        return None

    data = ocs["data"]
    found: dict[str, str] = {}
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                return None
            name = entry.get("configkey", entry.get("configKey"))
            if not isinstance(name, str):
                return None
            if name not in CONFIG_KEYS:
                continue
            text = _as_text(entry.get("configvalue", entry.get("configValue")))
            if text is None:
                return None
            found[name] = text
        return found
    if isinstance(data, dict):
        for name in CONFIG_KEYS:
            if name not in data:
                continue
            text = _as_text(data[name])
            if text is None:
                return None
            found[name] = text
        return found
    return None


def _as_text(raw: Any) -> str | None:
    """A stored value as a string, or ``None`` when it is a shape we do not read.

    A checkbox may arrive as a JSON boolean rather than as ``"1"`` or ``"0"``, depending on
    what Nextcloud stored for the field, and ``True`` is a perfectly readable answer. It is
    turned into the lower case spelling here so the switch reader has one language.
    """
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if isinstance(raw, str):
        return raw
    return None
