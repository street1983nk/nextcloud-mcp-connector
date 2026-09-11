"""Environment parsing (D-11, D-12), base URL normalisation and mode selection.

Four credential modes exist and they are mutually exclusive, because a server that can
fall back from one identity source to another has no identity source at all:

===================  =========================================  ==================================
Mode                 Selected by                                Nextcloud credentials
===================  =========================================  ==================================
stdio                no transport headers exist at all          environment (D-11)
exapp                ``APP_ID`` and ``APP_SECRET`` are set      the user id in the AppAPI header
http_passthrough     headers present, no static bearer set      Basic credentials of the request
http_static_bearer   ``NC_MCP_STATIC_BEARER`` is set            environment, guarded by the bearer
===================  =========================================  ==================================

The AppAPI variables are the one group here without the ``NC_MCP_`` prefix: ``APP_ID``,
``APP_SECRET``, ``APP_VERSION``, ``AA_VERSION``, ``APP_HOST``, ``APP_PORT``,
``APP_PERSISTENT_STORAGE``, ``HP_SHARED_KEY``, ``HP_EXAPP_SOCK`` and ``NEXTCLOUD_URL``
are dictated by the AppAPI deploy daemon, which injects them into the container. Renaming
them here would mean renaming them in a component we do not own.

``select_mode`` is a pure function of the environment plus the request headers, so every
branch is testable without a server. The remaining helpers here feed the transport
hardening of ``entry_http`` (allowed hosts, DNS rebinding protection).
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from .errors import ToolError
from .nextcloud.credentials import Credentials

logger = logging.getLogger("mcp_connector.config")

ENV_URL = "NC_MCP_URL"
ENV_USER = "NC_MCP_USER"
ENV_APP_PASSWORD = "NC_MCP_APP_PASSWORD"  # noqa: S105 - the env var name, not a secret

ENV_ALLOWED_HOSTS = "NC_MCP_ALLOWED_HOSTS"
ENV_STATIC_BEARER = "NC_MCP_STATIC_BEARER"
ENV_DISABLE_DNS_REBINDING = "NC_MCP_DISABLE_DNS_REBINDING_PROTECTION"
ENV_PUBLIC_URL = "NC_MCP_PUBLIC_URL"
ENV_TALK_SEND = "NC_MCP_TALK_SEND"

# The audit log of phase 18. The first one is the switch the whole feature hangs on (D-14),
# the other two move the two limits of the store (D-09). All three read by the three
# functions at the end of this module.
ENV_AUDIT_LOG = "NC_MCP_AUDIT_LOG"
ENV_AUDIT_RETENTION_DAYS = "NC_MCP_AUDIT_RETENTION_DAYS"
ENV_AUDIT_MAX_BYTES = "NC_MCP_AUDIT_MAX_BYTES"

# The AppAPI deploy environment. The names come from AppAPI, see the module docstring.
ENV_APP_ID = "APP_ID"
ENV_APP_SECRET = "APP_SECRET"  # noqa: S105 - the env var name, not a secret
ENV_APP_VERSION = "APP_VERSION"
ENV_AA_VERSION = "AA_VERSION"
ENV_APP_HOST = "APP_HOST"
ENV_APP_PORT = "APP_PORT"
ENV_APP_PERSISTENT_STORAGE = "APP_PERSISTENT_STORAGE"
ENV_HP_SHARED_KEY = "HP_SHARED_KEY"  # the env var name, not a secret
ENV_HP_EXAPP_SOCK = "HP_EXAPP_SOCK"
ENV_NEXTCLOUD_URL = "NEXTCLOUD_URL"

Mode = Literal["stdio", "exapp", "http_passthrough", "http_static_bearer"]

#: Used as issuer and resource server URL in the static bearer mode. It is only ever a
#: self-reference for the RFC 9728 discovery document, never a place we send secrets to.
DEFAULT_PUBLIC_URL = "http://127.0.0.1:8765"

#: What the SDK allows when no allowlist is configured. Spelled out instead of relying on
#: the SDK default, because a silent default is what produces a 421 nobody can explain.
LOCALHOST_NAMES = ("127.0.0.1", "localhost", "[::1]")

#: The spellings that arm a switch, and the ones that disarm it. Deliberately identical to
#: the two sets of ``exapp/config_values.py`` and of ``oauth/registry.py``, and held equal by
#: a test: a value that arms a switch in the environment has to arm the same switch when it
#: comes out of the admin form, or an administrator debugs a difference nobody wrote down.
#: Spelled here instead of imported, because ``exapp/config_values.py`` imports this module
#: and a shared constant in the other direction would be a circular import.
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})

#: The two limits of the audit store, repeated here instead of imported, and the direction
#: was measured before it was written down rather than assumed. ``audit/store.py`` itself
#: imports nothing but the standard library and never this module, but a submodule cannot be
#: imported without its package, and ``audit/__init__.py`` does import this one. A
#: ``from .audit import store`` here would therefore close a ring that survives today only
#: because ``audit/__init__`` reads ``config`` at call time and because the import system
#: falls back to ``sys.modules`` for a partially initialised submodule. That is a property of
#: two files that nobody would think to keep, so the direction stays clean and the two
#: numbers stand twice. The place they are justified in is ``audit/store.py`` (D-09: 180 days
#: sits exactly on the floor AUDIT-03 asks for, 100 MB generously above it so the window and
#: not the size is what usually bites), and ``tests/unit/test_config.py`` holds both pairs
#: equal so the copy cannot drift away from the original.
AUDIT_RETENTION_DAYS = 180
AUDIT_SIZE_LIMIT_BYTES = 100_000_000

#: The floor under the retention window. AUDIT-03 asks that the window can *reach* 180 days,
#: so a smaller value is not a preference but a configuration that breaks the requirement,
#: and it is refused instead of applied. Larger is allowed: keeping longer than asked is the
#: administrator's decision and no requirement of ours stands against it.
AUDIT_RETENTION_FLOOR = 180

#: The floor under the upper bound. A mistyped size that lands at a few bytes would sweep
#: every row away again the moment it was written, which looks exactly like a log that does
#: not work, so anything below one megabyte keeps the default instead.
AUDIT_SIZE_LIMIT_FLOOR = 1_000_000

#: Where the OAuth store goes when this process was not started by the AppAPI deploy
#: daemon, which is the ``--manual`` development mode and nothing else. Relative to the
#: working directory and git ignored, because the file holds encrypted app passwords.
DEV_STORAGE_DIR = ".nc-mcp-dev-storage"

REDIRECT_HINT = "Your Nextcloud URL redirects; use the final URL, including https and any subpath."

_URL_HINT = (
    f"Set {ENV_URL} to the full base URL of your Nextcloud, for example "
    "https://cloud.example.com or https://example.com/nextcloud."
)

_EXAPP_HINT = (
    f"{ENV_APP_ID}, {ENV_APP_SECRET}, {ENV_APP_VERSION} and {ENV_NEXTCLOUD_URL} are set by the "
    "AppAPI deploy daemon when it starts the container. A missing one means the process was "
    "started by hand: register the ExApp with 'occ app_api:app:register' and take the values "
    "from that registration."
)

_STORAGE_HINT = (
    f"{ENV_APP_PERSISTENT_STORAGE} is the mount point of the volume AppAPI creates for this "
    "app (nc_app_<appid>_data). The deploy daemon sets it and mounts the volume writable for "
    "uid 10001. Check the volume of the container and the value in the deploy environment; "
    "without it every authorization would be lost on the next restart."
)


@dataclass(frozen=True, slots=True, repr=False)
class ExAppSettings:
    """The AppAPI identity of this process: who we are and where Nextcloud lives.

    Masked like :class:`~mcp_connector.nextcloud.credentials.Credentials`: ``app_secret``
    is a bearer equivalent secret whose disclosure allows impersonating every user of the
    instance, so it never appears in a traceback or in the repr of a container (T-02-03).
    """

    app_id: str
    app_secret: str
    app_version: str
    aa_version: str
    base_url: str

    def __repr__(self) -> str:
        return (
            f"ExAppSettings(app_id={self.app_id!r}, app_version={self.app_version!r}, "
            f"aa_version={self.aa_version!r}, base_url={self.base_url!r}, app_secret='***')"
        )


def normalize_base_url(raw: str) -> str:
    """Strip whitespace and trailing slashes, keep a subpath, require http or https."""
    candidate = (raw or "").strip().rstrip("/")
    if not candidate:
        raise ToolError(message=f"{ENV_URL} is empty.", hint=_URL_HINT)

    parts = urlsplit(candidate)
    if parts.scheme not in ("http", "https"):
        raise ToolError(
            message=f"{ENV_URL} must start with http:// or https:// (got {candidate!r}).",
            hint=_URL_HINT,
        )
    if not parts.netloc:
        raise ToolError(
            message=f"{ENV_URL} has no host ({candidate!r}).",
            hint=_URL_HINT,
        )
    if parts.username or parts.password:
        # The value neither belongs in a URL nor in this message: base_url is logged with
        # its full value in exapp/status.py, so a password in there would end up in the
        # log of a failed progress push (IN-04). This project takes credentials from
        # NC_MCP_USER and NC_MCP_APP_PASSWORD, or from the AppAPI header, never from here.
        raise ToolError(
            message=f"{ENV_URL} carries credentials in the URL.",
            hint=_URL_HINT,
        )
    return candidate


def load_base_url(env: Mapping[str, str] | None = None) -> str:
    """The configured Nextcloud instance. Needed in every mode, including passthrough."""
    source = os.environ if env is None else env
    return normalize_base_url(_required(source, ENV_URL))


def load_stdio_credentials(env: Mapping[str, str] | None = None) -> Credentials:
    """Build credentials from the environment, naming any missing variable."""
    source = os.environ if env is None else env
    base_url = load_base_url(source)
    user = _required(source, ENV_USER)
    secret = _required(source, ENV_APP_PASSWORD)
    return Credentials(base_url=base_url, user=user, secret=secret)


def select_mode(
    env: Mapping[str, str] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> Mode:
    """Return the one credential mode that applies to this call.

    ``headers is None`` means the transport has none (stdio, in-memory client), and no
    environment variable can turn such a process into an HTTP mode.
    """
    source = os.environ if env is None else env
    if headers is None:
        return "stdio"
    # The ExApp mode wins over the static bearer on purpose: a process deployed by AppAPI
    # has APP_SECRET from the deploy environment, so a process that carries both is a
    # misconfiguration. entry_exapp rejects that combination at startup with exit code 2
    # instead of resolving it silently per request (D-27, no silent fallbacks).
    if exapp_configured(source):
        return "exapp"
    if static_bearer(source):
        return "http_static_bearer"
    return "http_passthrough"


def static_bearer(env: Mapping[str, str] | None = None) -> str | None:
    """The configured static bearer, or ``None`` when the variable is unset or blank."""
    source = os.environ if env is None else env
    return (source.get(ENV_STATIC_BEARER) or "").strip() or None


def exapp_configured(env: Mapping[str, str] | None = None) -> bool:
    """True when this process was deployed as an ExApp, by the same rule as the bearer.

    A blank value counts as unset: an empty ``APP_SECRET`` in a compose file is a typo,
    not a request to authenticate everyone.
    """
    source = os.environ if env is None else env
    app_id = (source.get(ENV_APP_ID) or "").strip()
    app_secret = (source.get(ENV_APP_SECRET) or "").strip()
    return bool(app_id) and bool(app_secret)


def exapp_settings(env: Mapping[str, str] | None = None) -> ExAppSettings:
    """Read the AppAPI deploy environment, naming any variable that is missing.

    ``AA_VERSION`` is the one optional value: HaRP writes a hard coded placeholder into
    that header anyway, and nothing in this project evaluates it (pitfall 8).
    """
    source = os.environ if env is None else env
    raw_url = (source.get(ENV_NEXTCLOUD_URL) or "").strip() or (source.get(ENV_URL) or "").strip()
    if not raw_url:
        raise ToolError(message=f"{ENV_NEXTCLOUD_URL} is not set.", hint=_EXAPP_HINT)
    return ExAppSettings(
        app_id=_required_exapp(source, ENV_APP_ID),
        app_secret=_required_exapp(source, ENV_APP_SECRET),
        app_version=_required_exapp(source, ENV_APP_VERSION),
        aa_version=(source.get(ENV_AA_VERSION) or "").strip(),
        base_url=normalize_base_url(raw_url),
    )


def public_url(env: Mapping[str, str] | None = None) -> str:
    """Public base URL of this MCP server, used for the bearer discovery document."""
    source = os.environ if env is None else env
    return (source.get(ENV_PUBLIC_URL) or "").strip().rstrip("/") or DEFAULT_PUBLIC_URL


def persistent_storage(env: Mapping[str, str] | None = None) -> Path:
    """Return the directory the OAuth store writes into, or say what is missing.

    Fail closed in the ExApp mode (pitfall 12, T-03-15): AppAPI creates the volume and
    passes its mount point, so a missing variable, a missing directory or a read only
    mount is a deployment error that must stop the start. It is never a directory this
    process may invent, because a store on the container filesystem answers every
    question correctly until the first restart and then loses every authorization.

    Outside the ExApp mode there is no volume and no daemon: the ``--manual`` development
    mode falls back into a git ignored directory of the working tree. That branch is named
    in the log instead of being a silent default, because a production process that ever
    reaches it is misconfigured.
    """
    source = os.environ if env is None else env
    raw = (source.get(ENV_APP_PERSISTENT_STORAGE) or "").strip()

    if not exapp_configured(source):
        fallback = Path.cwd() / DEV_STORAGE_DIR
        fallback.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "%s is not set and this process is not an ExApp: the OAuth store falls back to "
            "the development directory %s. Encrypted app passwords live there; it is git "
            "ignored and must never be used in a deployment.",
            ENV_APP_PERSISTENT_STORAGE,
            DEV_STORAGE_DIR,
        )
        return fallback

    if not raw:
        raise ToolError(message=f"{ENV_APP_PERSISTENT_STORAGE} is not set.", hint=_STORAGE_HINT)

    path = Path(raw)
    if not path.is_dir():
        raise ToolError(
            message=f"{ENV_APP_PERSISTENT_STORAGE} does not point at a directory.",
            hint=_STORAGE_HINT,
        )
    if not _probe_writable(path):
        raise ToolError(
            message=f"The directory in {ENV_APP_PERSISTENT_STORAGE} is not writable.",
            hint=_STORAGE_HINT,
        )
    return path


def _probe_writable(path: Path) -> bool:
    """Write a file and remove it again, because asking is not the same as knowing.

    ``os.access`` reports the permission bits, which say nothing about a read only bind
    mount, a full filesystem or a Windows ACL. The store has to write, so the check
    writes.
    """
    probe = path / f".write-probe-{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        return False
    return True


def deployment_hosts(env: Mapping[str, str] | None = None) -> list[str]:
    """The host names this deployment answers to, read out of its own two addresses.

    The answer to issue #4: in Nextcloud AIO the proxy in front of an ExApp forwards the
    ``Host`` header of the public custom domain, the allowlist knew localhost and nothing
    else, and every ``/mcp`` request died as a 421 that an administrator of a one click
    installation had no variable to fix, because ``NC_MCP_ALLOWED_HOSTS`` is a deploy
    variable and a store installation gets none.

    Two variables are read and no third one:

    * ``NC_MCP_PUBLIC_URL`` is the address clients are told to call this server at. It is
      the one value such an installation *does* have, because it is the one field the
      administration form of this app asks for, so deriving from it is what makes the
      allowlist reachable without a deploy variable at all.
    * ``NEXTCLOUD_URL`` is the address of the Nextcloud this container belongs to, set by
      the AppAPI deploy daemon, and in AIO it *is* the public custom domain: that
      deployment passes ``'nextcloud_url' => 'https://' . getenv('NC_DOMAIN')``
      (``AIODockerActions::registerAIOHarpDaemonConfig``). So this is the variable that
      carries the answer before an administrator has filled in any form at all. Only its
      host is read, so the ``https`` to ``http`` rewrite AppAPI does to that value on
      other daemons is irrelevant here.

    ``NC_MCP_URL`` is deliberately not among them: that is the Nextcloud a standalone
    process talks *to*, never an address this server is reached at, and an allowlist entry
    for it would widen the check for nothing.

    This is not a hole in the DNS rebinding protection, it is what the protection is for.
    Both values come from the deploy environment or from the administration form of this
    app, neither is settable from a request, and the check stays armed against every other
    name. The alternative, and the one this replaces, is disabling the protection.
    """
    source = os.environ if env is None else env
    names: list[str] = []
    for variable in (ENV_PUBLIC_URL, ENV_NEXTCLOUD_URL):
        host = _host_of(source.get(variable) or "")
        if host and host not in names:
            names.append(host)
    return names


def allowed_hosts(env: Mapping[str, str] | None = None) -> list[str]:
    """Build the Host allowlist of the transport layer for this deployment.

    Two sources, in this order: the host names of :func:`deployment_hosts`, which this
    server answers to by definition and which are therefore always present, and then
    ``NC_MCP_ALLOWED_HOSTS`` if an operator set one, or the localhost default if she did
    not. The explicit variable still replaces that default rather than extending it, which
    is what it always did: an operator who narrows the list meant to narrow it, and the
    derived names are not a widening she did not ask for but the address of her own
    deployment.

    Two entries per bare hostname (``example.com`` and ``example.com:*``), because the
    Host header carries the port whenever the client was given one, and an allowlist that
    only knows the bare name answers 421 to every real request (pitfall 6). An entry that
    already carries a port or a wildcard is taken verbatim: the operator meant it.
    """
    source = os.environ if env is None else env
    raw = (source.get(ENV_ALLOWED_HOSTS) or "").strip()
    configured = [item.strip() for item in raw.split(",") if item.strip()]
    names = [*deployment_hosts(source), *(configured or list(LOCALHOST_NAMES))]

    hosts: list[str] = []
    for name in names:
        for candidate in (name,) if _has_port(name) else (name, f"{name}:*"):
            if candidate not in hosts:
                hosts.append(candidate)
    return hosts


def dns_rebinding_protection(env: Mapping[str, str] | None = None) -> bool:
    """Whether the Host header check stays armed. Off only behind a trusted proxy."""
    source = os.environ if env is None else env
    value = (source.get(ENV_DISABLE_DNS_REBINDING) or "").strip().lower()
    return value not in _TRUE_VALUES


def talk_send_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Whether an assistant may send a Talk message through this app at all (TALK-04).

    The one outgoing channel of this connector that an administrator can close for a whole
    instance. Reading is untouched by it: conversations and history stay readable whatever
    this answers, which is why the switch is about sending and not about Talk.

    This is the one line of this module that must not be copied from
    :func:`dns_rebinding_protection`. The return is ``value not in _FALSE_VALUES`` and not
    ``value in _TRUE_VALUES``, because the shipped state of this switch is on (TALK-04): an
    unset value, a blank one and a value nobody understands all have to answer True. A
    membership test in the positive set would turn a typo into the silent removal of a
    capability this server promises, which is the worse of the two failures.
    ``dns_rebinding_protection`` does the opposite for the same reason read the other way
    round: there the variable switches a default-on protection *off*, so an unreadable value
    must not disarm it either.
    """
    source = os.environ if env is None else env
    value = (source.get(ENV_TALK_SEND) or "").strip().lower()
    return value not in _FALSE_VALUES


def audit_log_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Whether this installation records tool calls at all (D-14). Off unless switched on.

    This is the *positive* direction, and it is the one function here that must not be copied
    from :func:`talk_send_enabled`. That one returns ``value not in _FALSE_VALUES``, because
    the shipped state of the Talk switch is on and a typo must not take a promised capability
    away. Here the shipped state is off, and for the opposite reason: a log about named people
    that starts itself because somebody mistyped a variable is the failure this switch exists
    to prevent (D-14). So an unset value, a blank one and a value nobody understands all
    answer False, and copying the membership test of the other function would turn a typo into
    a recording nobody asked for.

    The chain above this line falls the same way: an administrator's value wins over the
    deploy variable, the deploy variable wins over this default, and the 401 every first start
    after an installation gets from AppAPI leaves an empty overlay behind
    (``exapp/config_values.py``), so what is in force on that start is exactly this "off".

    A value that is neither on nor off keeps the default and says so, naming the field and
    never the value: an admin value travels here over HTTP (T-05-03, T-05-21).
    """
    source = os.environ if env is None else env
    value = (source.get(ENV_AUDIT_LOG) or "").strip().lower()
    if not value:
        return False
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    logger.warning(
        "%s is neither on nor off, so the audit log stays off (understood are %s and %s).",
        ENV_AUDIT_LOG,
        ", ".join(sorted(_TRUE_VALUES)),
        ", ".join(sorted(_FALSE_VALUES)),
    )
    return False


def audit_retention_days(env: Mapping[str, str] | None = None) -> int:
    """How long a recorded call is kept, at least :data:`AUDIT_RETENTION_FLOOR` days (D-09)."""
    return _bounded_number(
        env, ENV_AUDIT_RETENTION_DAYS, AUDIT_RETENTION_DAYS, AUDIT_RETENTION_FLOOR
    )


def audit_size_limit(env: Mapping[str, str] | None = None) -> int:
    """How large the audit file may grow, at least :data:`AUDIT_SIZE_LIMIT_FLOOR` bytes."""
    return _bounded_number(env, ENV_AUDIT_MAX_BYTES, AUDIT_SIZE_LIMIT_BYTES, AUDIT_SIZE_LIMIT_FLOOR)


def _bounded_number(env: Mapping[str, str] | None, name: str, default: int, floor: int) -> int:
    """One of the two audit numbers out of the environment, or the default plus a warning.

    Only a plain run of ASCII digits is taken. ``str.isdigit`` alone would accept ``"²"`` and
    the Arabic-Indic digits, of which the first makes :func:`int` raise, and a run of more
    than 4300 digits makes it raise as well since the integer conversion limit of Python 3.11.
    Both are caught rather than argued about: this function is read at startup and a refused
    value must never be able to stop a container from serving.

    No minus sign is accepted either, which is why the floor is a second check and not the
    only one: without the digit test a negative retention would move the retention window
    into the future and sweep every row on the first write.

    The warnings name the field and the bound and never the value, the rule every reader of an
    admin value in this project follows (T-05-03).
    """
    source = os.environ if env is None else env
    raw = (source.get(name) or "").strip()
    if not raw:
        return default
    if not (raw.isascii() and raw.isdigit()):
        logger.warning(
            "%s is not a plain number, so the default of %s stays in force.", name, default
        )
        return default
    try:
        number = int(raw)
    except ValueError:
        logger.warning(
            "%s is not a number this server can read, so the default of %s stays in force.",
            name,
            default,
        )
        return default
    if number < floor:
        logger.warning(
            "%s is below the lowest value this server accepts (%s), so the default of %s "
            "stays in force.",
            name,
            floor,
            default,
        )
        return default
    return number


def _has_port(name: str) -> bool:
    """True for ``example.com:8765`` and ``[::1]:*``, false for ``[::1]``."""
    return ":" in name.rsplit("]", 1)[-1]


def _host_of(raw: str) -> str:
    """The bare host name of an absolute http(s) URL, in the spelling a Host header uses.

    Empty for everything this function cannot read with certainty: a blank value, a value
    without a scheme it knows, a value without an authority, and a value ``urlsplit`` or
    its own port parser refuses. Empty means "contributes no allowlist entry", which is the
    fail closed answer: a name guessed out of a string nobody could parse would be an
    allowlist entry nobody wrote.

    The port is dropped on purpose. :func:`allowed_hosts` expands a bare name into ``name``
    and ``name:*``, so the wildcard covers the port the deployment actually publishes,
    which is not always the one that happens to stand in the configured address.

    IPv6 comes back in brackets, because ``urlsplit`` strips them and a Host header carries
    them (RFC 3986 §3.2.2).
    """
    candidate = raw.strip()
    if not candidate:
        return ""
    try:
        parts = urlsplit(candidate)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return ""
        hostname = parts.hostname
    except ValueError:
        # A bracket that never closes, a port that is not a number: both raise here rather
        # than answering, and neither is a host name this function may invent one for.
        return ""
    if not hostname:
        return ""
    return f"[{hostname}]" if ":" in hostname else hostname


def _required_exapp(source: Mapping[str, str], name: str) -> str:
    """Like :func:`_required`, but with the hint an ExApp operator can act on."""
    value = (source.get(name) or "").strip()
    if not value:
        raise ToolError(message=f"{name} is not set.", hint=_EXAPP_HINT)
    return value


def _required(source: Mapping[str, str], name: str) -> str:
    value = (source.get(name) or "").strip()
    if not value:
        raise ToolError(
            message=f"{name} is not set.",
            hint=(
                f"Set {ENV_URL}, {ENV_USER} and {ENV_APP_PASSWORD} in the environment of the "
                "MCP server. Create the app password in Nextcloud under "
                "Settings, Security, Devices and sessions."
            ),
        )
    return value
