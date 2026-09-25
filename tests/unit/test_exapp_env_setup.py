"""Guards for the ExApp package: container image, start scripts and appinfo/info.xml.

These are pure file assertions, no Docker and no network, so the default suite keeps
running on a host without a container engine (D-32). They hold the truths that would
otherwise only surface during a deploy, when the feedback loop is minutes long and the
audience is an administrator:

* a CR in a file the container reads turns the ENTRYPOINT into a "not found",
* a root container holds the shared secret and the data volume with far more authority
  than an MCP responder needs (T-02-22),
* a missing HEALTHCHECK makes AppAPI treat a broken container as healthy (T-02-25),
* an unverified frpc download is a supply chain hole (T-02-SC),
* and one route that is a shade too wide publishes the AppAPI lifecycle endpoints,
  including the one that disables the app, to anyone on the internet (T-02-20).

The manifest half is written as one function over a parsed root element rather than as a
chain of asserts, so the last test in this file can feed it a deliberately broken manifest
and prove that the gate actually fires.
"""

import ipaddress
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from lxml import etree

import mcp_connector
from mcp_connector import config
from mcp_connector.entry_exapp import build_exapp_app
from mcp_connector.nextcloud.clients.xml import hardened_parser
from mcp_connector.oauth import registry

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.exapp.example"
INSTALL_DOC = ROOT / "docs" / "exapp-install.md"
DOCKERFILE = ROOT / "Dockerfile"
ENTRYPOINT = ROOT / "entrypoint.sh"
START = ROOT / "start.sh"
HEALTHCHECK = ROOT / "healthcheck.sh"
DOCKERIGNORE = ROOT / ".dockerignore"
INFO_XML = ROOT / "appinfo" / "info.xml"
COMPOSE_EXAPP = ROOT / "compose.exapp.yml"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
BOOTSTRAP = ROOT / "scripts" / "bootstrap_exapp.sh"

CONTAINER_FILES = (DOCKERFILE, ENTRYPOINT, START, HEALTHCHECK)

#: The second half of this file guards the test topology of plan 02-04. Same reason as
#: above: docker compose exec breaks on a CR, a port that lost its 127.0.0.1 prefix
#: publishes a throwaway Nextcloud to the LAN (T-02-30), and a bootstrap script that grew a
#: reference to the other compose file could take down an instance somebody is using
#: (T-02-34).
TOPOLOGY_FILES = (COMPOSE_EXAPP, CADDYFILE, BOOTSTRAP)

#: What the read-only share fixture of plan 05-03 hands to the permission parity test
#: through the connection file. All four are paths or markers, no secret among them: the
#: asymmetry of that test lives in these objects, and a name that never reaches the file
#: turns the test into a silent skip rather than a failure.
SHARE_ENV_NAMES = (
    "NC_MCP_TEST_SHARED_DIR",
    "NC_MCP_TEST_SHARED_FILE",
    "NC_MCP_TEST_PRIVATE_FILE",
    "NC_MCP_TEST_SHARED_MARKER",
)

#: Names that must never be baked into a layer: they are secrets, or they are the second
#: credential channel the ExApp mode refuses to have (T-02-23, D-27).
FORBIDDEN_ENV_NAMES = ("APP_SECRET", "NC_MCP_APP_PASSWORD", "NC_MCP_STATIC_BEARER")

#: Route patterns that match everything worth protecting. The literal blacklist catches the
#: obvious spellings, the probe below catches the creative ones.
WIDE_URLS = frozenset({".*", "^.*$", "/", ".+", "^.+$"})

#: The three paths AppAPI calls on the container. None of them may be reachable through a
#: declared route: an unmatched path is a 404, a matched one is served by the PHP proxy
#: with valid AppAPI headers attached.
LIFECYCLE_PATHS = ("/heartbeat", "/init", "/enabled")

#: Headers the proxy sets itself. A route that does not have them stripped lets a client
#: send its own copy next to the real one, and which of the two a reader sees depends on
#: whether the proxy prepends or appends (WR-01, IN-01).
PROXY_OWNED_HEADERS = (
    "AUTHORIZATION-APP-API",
    "EX-APP-ID",
    "EX-APP-VERSION",
    "AA-VERSION",
    "X-ORIGIN-IP",
)

#: What this phase opens: the MCP transport, the three discovery documents, the two pages
#: of the browser onboarding, the four endpoints of the authorization server, the consent
#: screen behind /authorize, the decision behind that screen, and since phase 4 the
#: connections page of one account (D-38, AUTH-02, AUTH-03, EXAPP-02).
DECLARED_ROUTES = 13

#: The routes that must not be PUBLIC, and the level they carry instead. Empty, and that is
#: the finding of the live counter check: HaRP records every refusal of a USER route in a
#: blacklist of its own, and ten from one address inside HP_BLACKLIST_WINDOW answer that
#: address with 502 on every route of this app. ``/authorize/decide`` produces refusals as
#: its normal traffic (CR-01), so a USER declaration there is a remote switch that turns the
#: whole connector off for a caller. The account behind the request is resolved on a PUBLIC
#: route just as well, and comparing it is the app's job either way, because the relay
#: attacker of CR-01 holds a valid account too.
ACCESS_LEVELS: dict[str, str] = {}

#: Every access level this app is allowed to declare at all. ADMIN is deliberately absent:
#: no route of this app is an administrative one, and a level nobody meant to use is a
#: level nobody checks.
ALLOWED_ACCESS_LEVELS = frozenset({"PUBLIC", "USER"})

#: The onboarding paths the application registers, compared with the manifest below. Set
#: equality for the same reason as the well-known documents: a page that is declared but not
#: served is a 404 nobody can explain, and one that is served but not declared is unreachable
#: through the proxy.
CONNECT_PATHS = ("/connect", "/connect/wait")

#: The one route phase 4 adds: the page on which a user sees, ends and pauses their own
#: connections (EXAPP-02). A family of its own and deliberately not one of the onboarding
#: paths above, although it starts with the same eight characters.
CONNECTIONS_PATH = "/connections"

#: The four endpoints of the authorization server, compared with the manifest the same way.
#: A declared endpoint the application does not serve is a 404 during a first connection,
#: and a served one that is not declared is unreachable through HaRP (AUTH-03, D-38).
AS_PATHS = ("/authorize", "/token", "/register", "/revoke")

#: The consent screen of plan 03-05 and the decision behind it. Declared with the four
#: above and compared with them, because the screen is the page /authorize sends every
#: browser to and the decision is the request that grant hangs on (CR-01).
CONSENT_PATH = "/authorize/consent"
DECIDE_PATH = "/authorize/decide"

AUTHORIZATION_PATHS = (*AS_PATHS, CONSENT_PATH, DECIDE_PATH)

#: Enough of a deploy environment to build the application the manifest is compared against.
MANIFEST_ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: mcp_connector.__version__,
    config.ENV_NEXTCLOUD_URL: "http://nc.test",
}


def instruction_values(text: str, keyword: str) -> list[str]:
    """Every value of a Dockerfile instruction, in file order, comments removed."""
    values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        head, _, rest = stripped.partition(" ")
        if head == keyword:
            values.append(rest.strip())
    return values


def manifest_problems(root: etree._Element) -> list[str]:
    """Return every reason this manifest must not be shipped, empty list when it is fine.

    A function instead of a row of asserts, because a gate that was never seen failing is
    not a gate. ``test_the_manifest_gate_rejects_a_wide_public_route`` calls this with a
    manifest that carries the exact mistake 02-RESEARCH.md warns about first.
    """
    problems: list[str] = []

    if root.findtext("id") != "mcp_connector":
        problems.append("the app id is not the frozen mcp_connector")

    version = (root.findtext("version") or "").strip()
    if version != mcp_connector.__version__:
        problems.append(f"version {version!r} is not the package version")

    image_tag = (root.findtext(".//docker-install/image-tag") or "").strip()
    if image_tag != version:
        problems.append(f"image tag {image_tag!r} does not follow the version {version!r}")

    routes = root.findall(".//route")
    if len(routes) != DECLARED_ROUTES:
        problems.append(
            f"{len(routes)} routes declared, this phase opens exactly {DECLARED_ROUTES}"
        )

    for route in routes:
        url = (route.findtext("url") or "").strip()
        access_level = (route.findtext("access_level") or "").strip()
        bruteforce = (route.findtext("bruteforce_protection") or "").strip()
        excluded = (route.findtext("headers_to_exclude") or "").strip()

        if url in WIDE_URLS:
            problems.append(f"route {url!r} matches everything")
        for header in PROXY_OWNED_HEADERS:
            if f'"{header}"' not in excluded:
                problems.append(f"route {url!r} does not have {header} stripped by the proxy")
        if access_level == "PUBLIC" and not url.startswith("^/"):
            problems.append(f"public route {url!r} is not anchored at a path")
        if access_level not in ALLOWED_ACCESS_LEVELS:
            problems.append(f"route {url!r} declares the access level {access_level!r}")
        expected = ACCESS_LEVELS.get(url, "PUBLIC")
        if access_level != expected:
            # The access level table. Every route of this app is PUBLIC for a reason
            # written next to it in the manifest, and a route that changes level silently
            # is a change of who may reach it and of what a refusal costs, so it fails
            # here. The cost is the half that is easy to miss: a refused request to a USER
            # route is a strike in HaRP's own blacklist, and ten of them ban the caller
            # from every route of this app for five minutes.
            problems.append(f"route {url!r} is {access_level!r} and has to be {expected!r}")
        if not url.endswith("$"):
            # HaRP matches with re.match, which anchors at the start only, so a pattern
            # without an end anchor also matches every neighbour that starts the same way:
            # the old ^/\.well-known/ covered the whole tree, and even a per document
            # pattern without the $ would still cover /.well-known/openid-configuration.evil
            # (pitfall 14, AR-02-06). The rule holds for every route of this app since plan
            # 03-04, not only for the well-known ones: /connect without the anchor would
            # publish every path that begins with it.
            problems.append(f"route {url!r} has no end anchor")
        if "401" in bruteforce:
            problems.append(f"route {url!r} throttles on 401, which breaks OAuth discovery")
        for path in LIFECYCLE_PATHS:
            if _matches(url, path):
                problems.append(f"route {url!r} exposes the lifecycle path {path}")

    return problems


def declared_connect_paths(root: etree._Element) -> set[str]:
    """The literal path behind every onboarding route pattern of the manifest.

    Same reduction as for the well-known documents, plus the optional trailing slash that
    lets ``/connect/`` reach the same page as ``/connect``.
    """
    paths = set()
    for route in root.findall(".//route"):
        url = (route.findtext("url") or "").strip()
        literal = url.removeprefix("^").removesuffix("$").removesuffix("/?").replace("\\", "")
        # On the segment boundary and not on the prefix: ``/connections`` starts with the
        # same eight characters and is a different family with a different reason to exist.
        if literal != "/connect" and not literal.startswith("/connect/"):
            continue
        paths.add(literal)
    return paths


def declared_connections_paths(root: etree._Element) -> set[str]:
    """The literal path behind the connections route of the manifest (EXAPP-02)."""
    paths = set()
    for route in root.findall(".//route"):
        url = (route.findtext("url") or "").strip()
        literal = url.removeprefix("^").removesuffix("$").removesuffix("/?").replace("\\", "")
        if literal == CONNECTIONS_PATH:
            paths.add(literal)
    return paths


def declared_authorization_paths(root: etree._Element) -> set[str]:
    """The literal path behind every authorization server route of the manifest."""
    paths = set()
    for route in root.findall(".//route"):
        url = (route.findtext("url") or "").strip()
        literal = url.removeprefix("^").removesuffix("$").removesuffix("/?").replace("\\", "")
        if literal in AUTHORIZATION_PATHS:
            paths.add(literal)
    return paths


def declared_well_known_paths(root: etree._Element) -> set[str]:
    """The literal path behind every well-known route pattern of the manifest.

    The patterns are regular expressions for HaRP; reducing them to their literal form
    (anchors and escapes removed) is what makes them comparable with the Starlette paths
    the application actually registers.
    """
    paths = set()
    for route in root.findall(".//route"):
        url = (route.findtext("url") or "").strip()
        if "well-known" not in url:
            continue
        paths.add(url.removeprefix("^").removesuffix("$").replace("\\", ""))
    return paths


def _excluded_headers() -> str:
    """The headers_to_exclude value of the manifest, for a route a test builds itself."""
    return "[" + ",".join(f'"{header}"' for header in PROXY_OWNED_HEADERS) + "]"


def compose_services(text: str) -> dict[str, str]:
    """Split the services mapping of a compose file into one text block per service.

    Hand written instead of parsed: the project has no YAML dependency, and adding one for
    six assertions would be a runtime dependency for a test. The file it reads is written
    by hand and stays inside the two space indentation the rest of the repository uses.
    """
    blocks: dict[str, list[str]] = {}
    in_services = False
    current: str | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_services = line.startswith("services:")
            current = None
            continue
        if in_services and indent == 2 and line.strip().endswith(":"):
            current = line.strip().rstrip(":")
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


def published_ports(text: str) -> list[str]:
    """Every entry of every ``ports:`` list in the given compose text, comments removed."""
    ports: list[str] = []
    collecting = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "ports:":
            collecting = True
            continue
        if collecting:
            if stripped.startswith("- "):
                ports.append(stripped[2:].strip().strip('"').strip("'"))
            else:
                collecting = False
    return ports


def shell_function(name: str, path: Path | None = None) -> str:
    """Cut one function out of a shell script so a test can run it on its own.

    The alternative would be sourcing the whole file, and the bootstrap talks to Docker
    from its first line. The cut is exact: every script here writes a function as
    ``name() {`` on its own line and closes it with a ``}`` in column one, and the
    assertions below fail loudly if that ever stops being true.
    """
    text = (path or BOOTSTRAP).read_text(encoding="utf-8")
    opening = f"\n{name}() {{\n"
    start = text.index(opening)
    end = text.index("\n}\n", start)
    return text[start + 1 : end + 3]


def function_body(text: str, name: str) -> str:
    """The body of one shell function, cut out of a script text instead of a file.

    ``shell_function`` above reads the checked in script; this one works on a string, which
    is what the counter probe of the share gate needs: it manipulates the text in memory and
    the gate has to fire on the manipulated copy without a temporary file anywhere.
    """
    opening = f"\n{name}() {{\n"
    if opening not in text:
        return ""
    start = text.index(opening)
    end = text.index("\n}\n", start)
    return text[start : end + 3]


def env_heredoc(text: str) -> str:
    """The block the bootstrap writes into the connection file, without the rest of it."""
    opening = 'cat >"${ENV_FILE}" <<EOF\n'
    if opening not in text:
        return ""
    start = text.index(opening)
    return text[start : text.index("\nEOF\n", start)]


def share_fixture_problems(text: str) -> list[str]:
    """Every reason the read-only share fixture would not prove what plan 05-03 claims.

    Written as one function over the script text, the same shape ``manifest_problems`` uses,
    so the counter probe below can feed it a deliberately broken copy and show that the gate
    actually fires. Each problem names what is wrong, because a gate that only says "False"
    costs the next reader the whole script.
    """
    problems: list[str] = []
    body = function_body(text, "ensure_readonly_share")
    if not body:
        problems.append("the bootstrap does not define ensure_readonly_share")

    call = text.find("\nensure_readonly_share alice")
    passwords = text.find('ALICE_APP_PASSWORD="$(app_password')
    if call < 0:
        problems.append("ensure_readonly_share is never called in the main part")
    elif passwords < 0:
        problems.append("the app password block moved, so the call order cannot be checked")
    elif call > passwords:
        problems.append("ensure_readonly_share runs after the app password block")

    permissions = re.findall(r'-d "permissions=(\d+)"', text)
    if not permissions:
        problems.append("the share is created without a permissions value")
    for value in permissions:
        if value != "1":
            problems.append(f"the share is created with permissions={value}, which is not read")
    if '-d "shareType=0"' not in text:
        problems.append("the share is not created as a user share (shareType=0)")
    if '-d "shareWith=' not in text:
        problems.append("the share names no recipient (shareWith)")
    for header in ('"OCS-APIRequest: true"', '"Accept: application/json"'):
        if header not in text:
            problems.append(f"the share call does not send {header}")
    if "shareapi_auto_accept_share --value=yes" not in text:
        problems.append("the share is not auto accepted, so it waits in the recipient's inbox")

    if body:
        if "share_is_readonly_for" not in body:
            problems.append("the fixture never reads the share back, so it assumes instead")
        if "PROPFIND" not in body or "207" not in body:
            problems.append("the fixture never proves that the recipient's home carries it")

    heredoc = env_heredoc(text)
    if not heredoc:
        problems.append("the connection file is not written from a heredoc any more")
    for name in SHARE_ENV_NAMES:
        if f"\n{name}=" not in heredoc:
            problems.append(f"{name} is not written into the connection file")
        elif f"\n{name}=/" in heredoc:
            # Git Bash rewrites an exported value that starts with a slash into a Windows
            # path when it starts a native process, so pytest received the MSYS installation
            # directory in front of every path (measured, plan 05-03). Relative to the user's
            # root is the same string everywhere, and the test puts the slash back.
            problems.append(f"{name} is written as an absolute path, which Git Bash rewrites")
    return problems


def find_bash() -> str | None:
    """A bash that can actually run this repository's scripts, or ``None``.

    ``shutil.which('bash')`` is not enough on Windows: it finds the WSL relay in
    System32 first, which fails with "execvpe(/bin/bash)" on a host without a distro and
    cannot resolve a drive letter path even with one. So every candidate is probed with a
    Windows style path it has to see, and the first one that passes wins.
    """
    probe = f'test -f "{Path(__file__).as_posix()}"'
    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(  # noqa: S603 - a literal probe, no user input
                [candidate, "-c", probe],
                capture_output=True,
                check=False,
                timeout=60,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return candidate
    return None


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no usable bash on this host")


def run_bash(script: str) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(  # noqa: S603 - a literal script from this test, no user input
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _matches(url: str, path: str) -> bool:
    """Whether the route regex would let ``path`` through, unparseable patterns included."""
    try:
        return re.search(url, path) is not None
    except re.error:
        return True


@pytest.fixture
def manifest_root() -> etree._Element:
    return etree.parse(str(INFO_XML), hardened_parser()).getroot()


@pytest.mark.parametrize(
    "path", [DOCKERFILE, ENTRYPOINT, START, HEALTHCHECK, DOCKERIGNORE, INFO_XML]
)
def test_the_exapp_package_is_checked_in(path: Path) -> None:
    assert path.is_file(), f"{path.name} is missing"


@pytest.mark.parametrize("path", list(CONTAINER_FILES))
def test_no_crlf_in_files_the_container_reads(path: Path) -> None:
    assert b"\r\n" not in path.read_bytes(), (
        f"{path.name} has CRLF endings; docker compose exec fails on the CR"
    )


def test_the_image_declares_a_healthcheck() -> None:
    """T-02-25: AppAPI reads container health, and no healthcheck means always healthy."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "HEALTHCHECK" in text
    assert "/healthcheck.sh" in text


def test_the_image_runs_unprivileged() -> None:
    """T-02-22: the container holds APP_SECRET and the data volume, root is not needed."""
    users = instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "USER")
    assert users, "the Dockerfile never leaves root"
    final = users[-1]
    assert final not in {"root", "0", "root:root", "0:0"}, f"USER {final} is root"
    assert final.split(":")[0] not in {"root", "0"}, f"USER {final} is root"


def test_the_entrypoint_is_the_wrapper_that_execs_the_harp_start_script() -> None:
    """WR-02, WR-04: the guards run first, then the upstream script, with the same arg."""
    entrypoints = instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "ENTRYPOINT")
    assert entrypoints, "the Dockerfile declares no ENTRYPOINT"
    assert "/entrypoint.sh" in entrypoints[-1]
    assert "nc-mcp-exapp" in entrypoints[-1]
    assert 'exec /start.sh "$@"' in ENTRYPOINT.read_text(encoding="utf-8")


def test_the_image_arms_no_transport_switch_in_a_layer() -> None:
    """WR-02: the switch disables the Host and the Origin check of the MCP transport, and
    in a layer it did so for every deployment mode, HaRP or not."""
    for value in instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "ENV"):
        assert "NC_MCP_DISABLE_DNS_REBINDING_PROTECTION" not in value


def test_the_transport_switch_is_bound_to_the_harp_path() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    switch = "export NC_MCP_DISABLE_DNS_REBINDING_PROTECTION=1"
    assert switch in text
    before = text.split(switch, 1)[0]
    assert 'if [ -n "${HP_SHARED_KEY:-}" ]; then' in before, "the switch is not HaRP bound"
    code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    assert not any("NC_MCP_ALLOWED_HOSTS=" in line for line in code), (
        "the host allowlist stays a deployment decision, the entrypoint never sets it"
    )


def test_the_entrypoint_refuses_a_plaintext_frp_tunnel() -> None:
    """WR-04: without /certs/frp start.sh writes transport.tls.enable = false and sends
    HP_SHARED_KEY in the clear. The downgrade is refused, with a documented opt-in."""
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "/certs/frp" in text
    assert "exit 1" in text
    assert "ALLOW_PLAINTEXT_FRP" in text


@needs_bash
@pytest.mark.parametrize(
    ("env", "expected_code"),
    [
        ({"HP_SHARED_KEY": "x" * 64, "FRP_CERT_WAIT_SECONDS": "0"}, 1),
        (
            {
                "HP_SHARED_KEY": "x" * 64,
                "FRP_CERT_WAIT_SECONDS": "0",
                "ALLOW_PLAINTEXT_FRP": "1",
            },
            0,
        ),
        ({"FRP_CERT_WAIT_SECONDS": "0"}, 0),
    ],
    ids=["harp without a certificate", "explicit opt-in", "no harp at all"],
)
def test_the_plaintext_guard_decides_by_the_shared_key(
    tmp_path: Path, env: dict[str, str], expected_code: int
) -> None:
    """The guard runs for real, with /start.sh replaced by a stub that only records that
    it was reached. A container without HP_SHARED_KEY has no tunnel and must not be
    blocked by a certificate it does not need."""
    stub = tmp_path / "start.sh"
    stub.write_text('#!/bin/sh\necho REACHED_START "$@"\n', encoding="utf-8", newline="\n")
    absent = (tmp_path / "absent").as_posix()
    body = (
        ENTRYPOINT.read_text(encoding="utf-8")
        .replace('FRP_CERT_DIR="/certs/frp"', f'FRP_CERT_DIR="{absent}"')
        .replace('exec /start.sh "$@"', f'exec sh "{stub.as_posix()}" "$@"')
    )
    assert absent in body, "the certificate directory is not a single literal any more"
    exports = "".join(f'export {name}="{value}"\n' for name, value in env.items())
    script = f"{exports}{body}"

    result = run_bash(script)

    assert result.returncode == expected_code, result.stderr
    assert ("REACHED_START" in result.stdout) is (expected_code == 0)


@needs_bash
@pytest.mark.parametrize(
    ("files", "expected_code"),
    [
        ((), 1),
        (("client.crt", "client.key"), 1),
        (("client.crt", "client.key", "ca.crt"), 0),
    ],
    ids=["directory without files", "ca.crt still missing", "all three files"],
)
def test_the_plaintext_guard_waits_for_the_files_not_the_directory(
    tmp_path: Path, files: tuple[str, ...], expected_code: int
) -> None:
    """IN-02: HaRP creates /certs/frp with `mkdir -p` before it copies the three files
    start.sh reads. A guard that only checks the directory lets start.sh emit a TLS
    configuration whose certFile does not exist yet, so the guard has to wait for the
    files themselves."""
    stub = tmp_path / "start.sh"
    stub.write_text('#!/bin/sh\necho REACHED_START "$@"\n', encoding="utf-8", newline="\n")
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    for name in files:
        (cert_dir / name).write_text("not a real certificate\n", encoding="utf-8", newline="\n")
    body = (
        ENTRYPOINT.read_text(encoding="utf-8")
        .replace('FRP_CERT_DIR="/certs/frp"', f'FRP_CERT_DIR="{cert_dir.as_posix()}"')
        .replace('exec /start.sh "$@"', f'exec sh "{stub.as_posix()}" "$@"')
    )
    assert cert_dir.as_posix() in body, "the certificate directory is not a single literal"
    script = f'export HP_SHARED_KEY="{"x" * 64}"\nexport FRP_CERT_WAIT_SECONDS="0"\n{body}'

    result = run_bash(script)

    assert result.returncode == expected_code, result.stderr
    assert ("REACHED_START" in result.stdout) is (expected_code == 0)


def test_the_frpc_download_is_checksum_verified() -> None:
    """T-02-SC: frpc is a foreign binary, and a release asset can be replaced."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "sha256sum -c" in text, "the frpc archive is unpacked without a checksum check"
    assert "FRP_AMD64_SHA256" in text
    assert "FRP_ARM64_SHA256" in text


def test_the_frpc_checksums_cannot_be_replaced_from_the_command_line() -> None:
    """IN-03: as ARGs they were overridable with --build-arg, so the pin only held for a
    build nobody tampered with."""
    args = instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "ARG")
    for name in ("FRP_AMD64_SHA256", "FRP_ARM64_SHA256", "FRP_VERSION"):
        assert not any(value.startswith(name) for value in args), f"{name} is still an ARG"


@pytest.mark.parametrize("name", FORBIDDEN_ENV_NAMES)
def test_no_secret_is_baked_into_the_image(name: str) -> None:
    """T-02-23: secrets come from the deploy environment, never from a layer."""
    for value in instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "ENV"):
        assert name not in value, f"the image sets {name} in an ENV instruction"


def test_the_runtime_user_does_not_own_its_own_code() -> None:
    """WR-13: a writable site-packages turns any single file write into persistence, and
    AppAPI restarts this container rather than recreating it."""
    for value in instruction_values(DOCKERFILE.read_text(encoding="utf-8"), "COPY"):
        if "/app/.venv" not in value:
            continue
        assert "--chown" not in value, f"the virtual environment is chowned: COPY {value}"


def test_the_build_context_excludes_the_history_and_any_env_file() -> None:
    entries = DOCKERIGNORE.read_text(encoding="utf-8").split()
    for pattern in (".git", ".planning", ".env*", "tests"):
        assert pattern in entries, f"{pattern} belongs into .dockerignore"


def test_the_start_script_is_the_upstream_one_with_its_origin_named() -> None:
    """It is copied verbatim from HaRP on purpose, so the header has to say so."""
    text = START.read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: AGPL-3.0-or-later" in text
    assert "nextcloud/HaRP" in text
    assert "exapps_dev/start.sh" in text
    assert 'exec "$@"' in text, "without the exec the container would not run the app"


def test_the_healthcheck_knows_both_transports() -> None:
    """Behind HaRP there is no TCP port at all, so one probe would be permanently red."""
    text = HEALTHCHECK.read_text(encoding="utf-8")
    assert "HP_SHARED_KEY" in text
    assert "APP_PORT" in text
    assert "--unix-socket" in text
    assert "/heartbeat" in text


def test_the_healthcheck_notices_a_dead_tunnel_client() -> None:
    """WR-05: frpc is an unsupervised background child with loginFailExit = false, so the
    socket answers and the container reports healthy while HaRP has no backend."""
    text = HEALTHCHECK.read_text(encoding="utf-8")
    assert "frpc_is_running" in text
    harp_branch = text.split('if [ -n "${HP_SHARED_KEY:-}" ]; then', 1)[1]
    assert "if ! frpc_is_running; then" in harp_branch
    assert harp_branch.index("frpc_is_running") < harp_branch.index("exec curl"), (
        "the tunnel check has to run before the probe that would answer anyway"
    )


@needs_bash
@pytest.mark.parametrize(
    ("second_process", "expected_code"),
    [("uvicorn", 1), ("frpc", 0)],
    ids=["frpc is dead", "frpc is alive"],
)
def test_the_tunnel_probe_reads_the_process_table(
    tmp_path: Path, second_process: str, expected_code: int
) -> None:
    """The helper runs for real, against a process table built for this test: a container
    always has PID 1, and the question is whether frpc sits next to it."""
    fake_proc = tmp_path / "process-table"
    for pid, comm in (("1", "sh"), ("42", second_process)):
        entry = fake_proc / pid
        entry.mkdir(parents=True)
        (entry / "comm").write_text(f"{comm}\n", encoding="utf-8", newline="\n")

    body = shell_function("frpc_is_running", HEALTHCHECK).replace(
        "/proc/[0-9]*", f"{shlex.quote(fake_proc.as_posix())}/[0-9]*"
    )
    assert fake_proc.as_posix() in body, "the process table path is not a single literal"
    result = run_bash(f"set -eu\n{body}\nfrpc_is_running\n")

    assert result.returncode == expected_code, result.stderr


def test_the_manifest_declares_exactly_the_thirteen_routes_of_this_phase(
    manifest_root: etree._Element,
) -> None:
    """D-38: /mcp is PUBLIC since plan 03-01, the one broad well-known route that carried the
    accepted risk AR-02-06 is three fully anchored ones now, plan 03-04 adds the two pages of
    the browser onboarding, and plan 03-05 adds the four endpoints of the authorization
    server plus the consent screen behind /authorize. Every one of them is anchored at both
    ends and PUBLIC for a reason of its own, the decision behind the consent screen
    included: HaRP names the account that decides on a PUBLIC route too, and a USER
    declaration would answer ten refusals with a five minute 502 on all thirteen (CR-01).
    Phase 4 adds the thirteenth, the connections page of one account, for the same measured
    reason: a settings page reached from a stale tab produces refusals as normal traffic."""
    routes = [
        ((route.findtext("url") or "").strip(), (route.findtext("access_level") or "").strip())
        for route in manifest_root.findall(".//route")
    ]
    assert routes == [
        ("^/mcp/?$", "PUBLIC"),
        ("^/\\.well-known/oauth-protected-resource/mcp$", "PUBLIC"),
        ("^/\\.well-known/openid-configuration$", "PUBLIC"),
        ("^/\\.well-known/oauth-authorization-server$", "PUBLIC"),
        ("^/connect/wait/?$", "PUBLIC"),
        ("^/connect/?$", "PUBLIC"),
        ("^/authorize/?$", "PUBLIC"),
        ("^/authorize/consent/?$", "PUBLIC"),
        ("^/authorize/decide/?$", "PUBLIC"),
        ("^/token/?$", "PUBLIC"),
        ("^/register/?$", "PUBLIC"),
        ("^/revoke/?$", "PUBLIC"),
        ("^/connections/?$", "PUBLIC"),
    ]


def test_the_declared_onboarding_routes_are_the_registered_ones(
    manifest_root: etree._Element,
) -> None:
    """Set equality again, for the second family of pages this app publishes (AUTH-02)."""
    registered = {
        path
        for path in (
            getattr(route, "path", "") for route in build_exapp_app(MANIFEST_ENV).router.routes
        )
        if path == "/connect" or path.startswith("/connect/")
    }

    assert declared_connect_paths(manifest_root) == registered == set(CONNECT_PATHS)


def test_the_declared_connections_page_is_the_registered_one(
    manifest_root: etree._Element,
) -> None:
    """EXAPP-02: a page that is declared but not served is a 404 nobody can explain, and one
    that is served but not declared is unreachable through the proxy."""
    registered = {
        path
        for path in (
            getattr(route, "path", "") for route in build_exapp_app(MANIFEST_ENV).router.routes
        )
        if path == CONNECTIONS_PATH
    }

    assert declared_connections_paths(manifest_root) == registered == {CONNECTIONS_PATH}


def test_the_connections_route_declares_both_verbs_and_no_third(
    manifest_root: etree._Element,
) -> None:
    """GET lists and POST acts. No DELETE: every state change of this page is a POST with a
    named action and an anti forgery value, and a verb nobody serves is surface for free
    (T-04-36)."""
    verbs = {
        (route.findtext("url") or "").strip(): (route.findtext("verb") or "").strip()
        for route in manifest_root.findall(".//route")
    }

    assert verbs["^/connections/?$"] == "GET,POST"


def test_the_onboarding_route_declares_the_verb_that_starts_a_sign_in(
    manifest_root: etree._Element,
) -> None:
    """A GET only declaration would leave the start of a flow unreachable through HaRP, and
    a POST on the waiting page would let a proxy replay a page that polls (T-03-34)."""
    verbs = {
        (route.findtext("url") or "").strip(): (route.findtext("verb") or "").strip()
        for route in manifest_root.findall(".//route")
    }

    assert verbs["^/connect/?$"] == "GET,POST"
    assert verbs["^/connect/wait/?$"] == "GET"


def test_the_declared_authorization_routes_are_the_registered_ones(
    manifest_root: etree._Element,
) -> None:
    """Set equality for the third family of routes, and the one that hands out tokens."""
    registered = {
        path
        for path in (
            getattr(route, "path", "") for route in build_exapp_app(MANIFEST_ENV).router.routes
        )
        if path in AUTHORIZATION_PATHS
    }

    assert declared_authorization_paths(manifest_root) == registered == set(AUTHORIZATION_PATHS)


def test_the_authorization_routes_declare_exactly_the_verbs_they_answer(
    manifest_root: etree._Element,
) -> None:
    """A missing POST on /authorize breaks the form post of RFC 6749, and a GET on /token
    would publish a credential endpoint to every crawler that follows a link."""
    verbs = {
        (route.findtext("url") or "").strip(): (route.findtext("verb") or "").strip()
        for route in manifest_root.findall(".//route")
    }

    assert verbs["^/authorize/?$"] == "GET,POST"
    assert verbs["^/authorize/consent/?$"] == "GET"
    assert verbs["^/authorize/decide/?$"] == "POST"
    assert verbs["^/token/?$"] == "POST"
    assert verbs["^/register/?$"] == "POST"
    assert verbs["^/revoke/?$"] == "POST"


def test_no_authorization_route_is_declared_twice(manifest_root: etree._Element) -> None:
    """The SDK registers a metadata document of its own at a path this app already serves,
    and two routes on one path answer whichever was registered first (plan 03-05)."""
    paths = [getattr(route, "path", "") for route in build_exapp_app(MANIFEST_ENV).router.routes]
    served = [
        path for path in paths if path.startswith("/.well-known/") or path in AUTHORIZATION_PATHS
    ]

    assert len(served) == len(set(served)), f"a path is served twice: {sorted(served)}"


def test_the_declared_well_known_routes_are_the_registered_ones(
    manifest_root: etree._Element,
) -> None:
    """Set equality, not a subset: a document that is declared but not served is a 404 an
    administrator cannot explain, and one that is served but not declared is unreachable
    through the proxy. Both are silent until a client tries to connect."""
    registered = {
        path
        for path in (
            getattr(route, "path", "") for route in build_exapp_app(MANIFEST_ENV).router.routes
        )
        if "well-known" in path
    }

    assert declared_well_known_paths(manifest_root) == registered


def test_the_manifest_gate_rejects_a_well_known_route_without_an_end_anchor(
    manifest_root: etree._Element,
) -> None:
    """Pitfall 14: HaRP matches with re.match, so a missing $ opens the neighbours too."""
    routes = manifest_root.find(".//routes")
    assert routes is not None
    route = etree.SubElement(routes, "route")
    etree.SubElement(route, "url").text = "^/\\.well-known/openid-configuration"
    etree.SubElement(route, "verb").text = "GET"
    etree.SubElement(route, "access_level").text = "PUBLIC"
    etree.SubElement(route, "headers_to_exclude").text = _excluded_headers()

    problems = manifest_problems(manifest_root)

    assert any("has no end anchor" in problem for problem in problems)


def test_the_manifest_gate_rejects_the_broad_well_known_route_of_phase_two(
    manifest_root: etree._Element,
) -> None:
    """The exact pattern AR-02-06 was accepted for. It must never come back unnoticed."""
    routes = manifest_root.find(".//routes")
    assert routes is not None
    route = etree.SubElement(routes, "route")
    etree.SubElement(route, "url").text = "^/\\.well-known/"
    etree.SubElement(route, "verb").text = "GET"
    etree.SubElement(route, "access_level").text = "PUBLIC"
    etree.SubElement(route, "headers_to_exclude").text = _excluded_headers()

    problems = manifest_problems(manifest_root)

    assert any("has no end anchor" in problem for problem in problems)


def test_the_manifest_passes_its_own_gate(manifest_root: etree._Element) -> None:
    assert manifest_problems(manifest_root) == []


def test_the_manifest_carries_no_scopes_element(manifest_root: etree._Element) -> None:
    """AppAPI 3.2.0 removed scopes; a leftover element is noise the store reviews."""
    assert manifest_root.findall(".//scopes") == []


def test_the_manifest_gate_rejects_a_wide_public_route(manifest_root: etree._Element) -> None:
    """The counter probe: without it, the green run above proves nothing about the gate."""
    routes = manifest_root.find(".//routes")
    assert routes is not None
    route = etree.SubElement(routes, "route")
    etree.SubElement(route, "url").text = ".*"
    etree.SubElement(route, "verb").text = "GET,POST,PUT,DELETE"
    etree.SubElement(route, "access_level").text = "PUBLIC"

    problems = manifest_problems(manifest_root)

    assert any("matches everything" in problem for problem in problems)
    assert any("/enabled" in problem for problem in problems)


def test_the_manifest_gate_rejects_a_user_decision_route(
    manifest_root: etree._Element,
) -> None:
    """The decision route may not go back to ``USER``, measured against a real HaRP.

    It was ``USER`` between the first shape of the CR-01 fix and the live counter check,
    and that is a remote off switch for the whole app: HaRP answers an anonymous request to
    a ``USER`` route with 403 *and* records it in its blacklist, and after ten of those from
    one address inside ``HP_BLACKLIST_WINDOW`` every route of this app answers that address
    with 502, discovery documents and ``/mcp`` included. Ten is nothing on this route, whose
    refusals are its normal traffic: the relay attempt of CR-01, an expired session behind
    an open consent screen, a resubmitted form.

    Nothing is lost by taking the level away, which is the other half of the measurement:
    HaRP resolves the Nextcloud account on a PUBLIC route as well, and the comparison in
    ``oauth/consent._decide`` is the only check that separates the relay attacker from the
    victim anyway, because both of them are signed in.
    """
    routes = {
        (route.findtext("url") or "").strip(): route for route in manifest_root.findall(".//route")
    }
    element = routes["^/authorize/decide/?$"].find("access_level")
    assert element is not None
    element.text = "USER"

    problems = manifest_problems(manifest_root)

    assert any("has to be 'PUBLIC'" in problem for problem in problems)


def test_the_manifest_gate_rejects_an_unexpected_user_route(
    manifest_root: etree._Element,
) -> None:
    """The same table read the other way: a route that quietly becomes USER stops answering
    the anonymous request it exists for, and the discovery documents and /mcp are exactly
    those routes (pitfall 6). PUBLIC is the declared default and a deviation has to be
    written into the table, not into the manifest alone."""
    routes = {
        (route.findtext("url") or "").strip(): route for route in manifest_root.findall(".//route")
    }
    element = routes["^/mcp/?$"].find("access_level")
    assert element is not None
    element.text = "USER"

    problems = manifest_problems(manifest_root)

    assert any("has to be 'PUBLIC'" in problem for problem in problems)


def test_the_manifest_gate_rejects_a_route_that_keeps_the_client_headers(
    manifest_root: etree._Element,
) -> None:
    """WR-01: an empty headers_to_exclude is what made the desync reachable at all."""
    route = manifest_root.find(".//route")
    assert route is not None
    element = route.find("headers_to_exclude")
    assert element is not None
    element.text = "[]"

    problems = manifest_problems(manifest_root)

    assert any("AUTHORIZATION-APP-API stripped" in problem for problem in problems)


def test_the_bootstrap_registration_strips_the_same_headers() -> None:
    """The json-info registration overrides the manifest, so it has to carry the list."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"headers_to_exclude":[]' not in text
    for header in PROXY_OWNED_HEADERS:
        assert f'"{header}"' in text, f"{header} is not stripped by the registration"


def test_the_bootstrap_registration_declares_the_same_thirteen_routes(
    manifest_root: etree._Element,
) -> None:
    """The json-info payload overrides the manifest, so a route that only lives in
    appinfo/info.xml is not registered on the test instance at all, and a level that differs
    between the two would make the local proof measure something the release does not do.
    access_level travels as a number there: 0 is PUBLIC and 1 is USER, and every route of
    this app carries 0 (CR-01, and the HaRP blacklist the counter probe above names)."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert text.count('"access_level":0') == DECLARED_ROUTES - len(ACCESS_LEVELS)
    assert text.count('"access_level":1') == len(ACCESS_LEVELS)
    assert '"access_level":2' not in text
    for url in ACCESS_LEVELS:
        pattern = url.replace("\\", "\\\\")
        assert f'"url":"{pattern}","verb":"POST","access_level":1' in text, url
    for path in declared_well_known_paths(manifest_root):
        # The payload carries the pattern with a doubled backslash escape, so the literal
        # path is compared without the dot escape (see the comment above json_info).
        assert path.replace("/.well-known/", "well-known/") in text, path
    for path in declared_connect_paths(manifest_root):
        assert f'"^{path}/?$"' in text, path
    for path in declared_authorization_paths(manifest_root):
        assert f'"^{path}/?$"' in text, path
    for path in declared_connections_paths(manifest_root):
        assert f'"^{path}/?$"' in text, path


def test_the_manifest_gate_rejects_a_throttler_on_401(manifest_root: etree._Element) -> None:
    """T-02-21: the OAuth discovery flow of phase 3 begins with a 401 by specification."""
    route = manifest_root.find(".//route")
    assert route is not None
    etree.SubElement(route, "bruteforce_protection").text = "[401]"

    assert any("throttles on 401" in problem for problem in manifest_problems(manifest_root))


@pytest.mark.parametrize("path", list(TOPOLOGY_FILES))
def test_the_test_topology_is_checked_in(path: Path) -> None:
    assert path.is_file(), f"{path.name} is missing"


@pytest.mark.parametrize("path", list(TOPOLOGY_FILES))
def test_no_crlf_in_the_topology_files(path: Path) -> None:
    assert b"\r\n" not in path.read_bytes(), (
        f"{path.name} has CRLF endings; docker compose exec and bash both break on the CR"
    )


def test_the_topology_publishes_on_loopback_only() -> None:
    """T-02-30: throwaway credentials plus a disabled bruteforce guard, so no LAN."""
    ports = published_ports(COMPOSE_EXAPP.read_text(encoding="utf-8"))
    assert ports, "no published port found, the parser or the file changed shape"
    for port in ports:
        assert port.startswith("127.0.0.1:"), f"port {port!r} is not bound to loopback"


def test_the_topology_carries_its_own_project_name() -> None:
    """Without it compose derives the project from the directory and both topologies land
    in the same project, where a `down` on one stops the containers of the other
    (T-02-34)."""
    lines = COMPOSE_EXAPP.read_text(encoding="utf-8").splitlines()
    names = [line for line in lines if line.startswith("name:")]
    assert names == ["name: nc-mcp-exapp"]


def test_the_shared_key_has_no_default_in_the_repository() -> None:
    """WR-11: a fixed default is a published secret, and the documented command used it,
    so nobody ever saw that their HaRP tunnel was open to whoever read this file."""
    services = compose_services(COMPOSE_EXAPP.read_text(encoding="utf-8"))
    lines = [
        line.strip()
        for line in services["appapi-harp"].splitlines()
        if line.strip().startswith("HP_SHARED_KEY:")
    ]
    assert lines, "HP_SHARED_KEY is not set for the deploy daemon any more"
    assert "${HP_SHARED_KEY:?" in lines[0], f"{lines[0]!r} still carries a default"
    assert ":-" not in lines[0]


def test_only_the_reverse_proxy_is_a_trusted_proxy() -> None:
    """WR-08: the whole subnet also covered the ExApp container, which is the component
    that processes untrusted input. It must not be able to forge a client address."""
    text = COMPOSE_EXAPP.read_text(encoding="utf-8")
    services = compose_services(text)
    addresses = set()
    for service, key in (
        ("nextcloud", "TRUSTED_PROXIES"),
        ("appapi-harp", "HP_TRUSTED_PROXY_IPS"),
    ):
        values = [
            line.split(":", 1)[1].strip().strip('"')
            for line in services[service].splitlines()
            if line.strip().startswith(f"{key}:")
        ]
        assert values, f"{key} is not set for {service}"
        assert "/" not in values[0], f"{key} is a range, not one proxy: {values[0]!r}"
        addresses.add(values[0])

    assert len(addresses) == 1, f"the two trust lists disagree: {addresses}"
    assert f"ipv4_address: {addresses.pop()}" in services["caddy"], (
        "the trusted address is not the fixed one assigned to the reverse proxy"
    )


def test_dynamic_addresses_never_enter_the_static_half_of_the_subnet() -> None:
    """IN-03: without an ip_range Docker may reassign the fixed proxy address once caddy
    is down, and the next container holding 172.29.42.10 (possibly the ExApp container
    itself) would be a trusted proxy for Nextcloud and HaRP."""
    text = COMPOSE_EXAPP.read_text(encoding="utf-8")
    ranges = re.findall(r"^\s*ip_range:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    assert ranges, "the ipam configuration carries no ip_range for dynamic assignment"
    dynamic = ipaddress.ip_network(ranges[0])
    statics = re.findall(r"^\s*ipv4_address:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    assert statics, "no statically assigned address found, the trust anchor is gone"
    for address in statics:
        assert ipaddress.ip_address(address) not in dynamic, (
            f"static address {address} lies inside the dynamic range {dynamic}"
        )


def test_the_deploy_daemon_publishes_no_port() -> None:
    """Caddy reaches HaRP inside the compose network; a published port only adds reach."""
    services = compose_services(COMPOSE_EXAPP.read_text(encoding="utf-8"))
    assert "appapi-harp" in services, f"services found: {sorted(services)}"
    assert "ports:" not in services["appapi-harp"]


def test_the_mail_server_publishes_no_port() -> None:
    """T-10-01: GreenMail runs without authentication, so its reach must end at the
    compose network. The loopback-only test above iterates over ports that ARE
    published and passes silently for a service without any, so a later
    `ports: ["127.0.0.1:3143:3143"]` on greenmail would slip through it; this
    service-specific assertion is the half of the mitigation the plan asked for."""
    services = compose_services(COMPOSE_EXAPP.read_text(encoding="utf-8"))
    assert "greenmail" in services, f"services found: {sorted(services)}"
    assert "ports:" not in services["greenmail"]


def test_the_bootstrap_never_reaches_into_the_other_topology() -> None:
    """T-02-34, WR-07: the other test instance is in daily use and must survive this
    script. Naming the file is not enough, because the name used to be overridable: a
    forgotten `export COMPOSE_FILE=compose.test.yml` passed this test and still disabled
    the bruteforce guard on the instance somebody was using."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "compose.test.yml" not in text
    assert "down -v" not in text
    assert 'COMPOSE_FILE="compose.exapp.yml"' in text
    assert 'COMPOSE_FILE="compose.staging.yml"' in text, (
        "the staging topology is not selected by a literal file name any more"
    )
    assert "COMPOSE_FILE:-" not in text, "the compose file is overridable from the shell"
    assert "ensure_own_topology" in text


@needs_bash
@pytest.mark.parametrize(
    ("project", "content", "expected_code"),
    [
        ("nc-mcp-exapp", "name: nc-mcp-exapp\nservices:\n", 0),
        ("nc-mcp-exapp", "name: some-other-project\nservices:\n", 1),
        ("nc-mcp-exapp", "services:\n", 1),
        ("nc-mcp-exapp", None, 1),
        ("nc-mcp-staging", "name: nc-mcp-staging\nservices:\n", 0),
        ("nc-mcp-staging", "name: nc-mcp-exapp\nservices:\n", 1),
        ("nc-mcp-exapp", "name: nc-mcp-staging\nservices:\n", 1),
    ],
    ids=[
        "the right project",
        "a foreign project",
        "no project name",
        "no file at all",
        "the staging project under the staging name",
        "the local topology behind the staging name",
        "the staging topology behind the local name",
    ],
)
def test_the_topology_guard_refuses_a_foreign_compose_file(
    tmp_path: Path, project: str, content: str | None, expected_code: int
) -> None:
    """WR-07: the guard is what makes the fixed file name more than a comment.

    Since plan 03-09 the script knows two throwaway topologies, so the guard compares the
    project name it expects with the one the file declares. The last two cases are the ones
    that matter for that: a run aimed at the public instance must not accept the local file
    and the other way round, because the two differ in exactly the properties that are
    dangerous on the wrong instance (a public port, and a bruteforce guard that is switched
    off on the local one).
    """
    compose = tmp_path / "compose.yml"
    if content is not None:
        compose.write_text(content, encoding="utf-8", newline="\n")
    script = (
        "set -euo pipefail\n"
        f'COMPOSE_FILE="{compose.as_posix()}"\n'
        f'PROJECT_NAME="{project}"\n'
        f"{shell_function('ensure_own_topology')}\n"
        "ensure_own_topology\n"
    )

    result = run_bash(script)

    assert result.returncode == expected_code, result.stderr


@needs_bash
@pytest.mark.parametrize(
    ("call", "expected_code"),
    [
        ("require_port_number NC_EXAPP_APP_PORT '23000'", 0),
        ("require_port_number NC_EXAPP_APP_PORT '23000,\"system\":true'", 1),
        ("require_port_number NC_EXAPP_APP_PORT ''", 1),
        ("require_port_number NC_EXAPP_APP_PORT '23000 '", 1),
        ("require_registry_shape '127.0.0.1:5000'", 0),
        ("require_registry_shape 'ghcr.io'", 0),
        ('require_registry_shape \'127.0.0.1:5000","image":"evil\'', 1),
        ("require_registry_shape ''", 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'https://cloud.test/exapps/mcp_connector'", 0),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'http://127.0.0.1:8081/exapps/mcp_connector'", 0),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'https://cloud.example.com'", 0),
        ('require_url_shape NC_EXAPP_PUBLIC_URL \'https://x","system":true\'', 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'https://cloud.example.com/a b'", 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'https://cloud.example.com/a\\b'", 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'https://ok.example.com\n\"evil\":1'", 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL 'cloud.example.com'", 1),
        ("require_url_shape NC_EXAPP_PUBLIC_URL ''", 1),
    ],
    ids=[
        "a plain port",
        "a port with a JSON injection",
        "an empty port",
        "a port with trailing whitespace",
        "a registry with a port",
        "a bare registry host",
        "a registry with a JSON injection",
        "an empty registry",
        "the public address of a real instance",
        "the local default with its port",
        "a public address without a path",
        "a public address with a JSON injection",
        "a public address with a space",
        "a public address with a backslash",
        "a public address with a second line",
        "a public address without a scheme",
        "an empty public address",
    ],
)
def test_the_registration_inputs_are_pinned_before_json_info(call: str, expected_code: int) -> None:
    """IN-07 and WR-03: json_info interpolates the port unquoted, and the registry and the
    public address into strings, and all three come from overridable variables. A value
    outside the pinned shape must stop the bootstrap instead of reaching AppAPI as extra
    JSON fields."""
    script = (
        "set -euo pipefail\n"
        f"{shell_function('require_port_number')}\n"
        f"{shell_function('require_registry_shape')}\n"
        f"{shell_function('require_url_shape')}\n"
        f"{call}\n"
    )

    result = run_bash(script)

    assert result.returncode == expected_code, result.stderr


def test_the_bootstrap_calls_every_registration_validator() -> None:
    """The functions only protect anything if the main flow actually runs them."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    for call in (
        'require_port_number NC_EXAPP_APP_PORT "${APP_PORT}"',
        'require_port_number NC_EXAPP_MANUAL_PORT "${MANUAL_APP_PORT}"',
        'require_registry_shape "${REGISTRY}"',
        'require_url_shape NC_EXAPP_PUBLIC_URL "${PUBLIC_URL}"',
    ):
        assert call in text, f"the bootstrap never runs {call!r}"


def test_every_registration_validator_runs_before_json_info_is_built() -> None:
    """WR-03: a validator after the registration would only describe the payload.

    ``json_info`` is reached through ``ensure_exapp`` and ``register_manual_install``, so
    the position that matters is the one in the main run at the end of the script, not the
    position of the function definitions above it.
    """
    text = BOOTSTRAP.read_text(encoding="utf-8")
    run = text[text.index('echo "== ExApp topology bootstrap =="') :]
    registration = min(run.index("\n  ensure_exapp\n"), run.index("\n  register_manual_install\n"))

    for call in (
        'require_port_number NC_EXAPP_APP_PORT "${APP_PORT}"',
        'require_registry_shape "${REGISTRY}"',
        'require_url_shape NC_EXAPP_PUBLIC_URL "${PUBLIC_URL}"',
    ):
        assert run.index(call) < registration, f"{call!r} runs after the registration"


# --- the third data layer of the permission parity proof (plan 05-03) --------------


def test_the_bootstrap_builds_the_read_only_share_with_proof() -> None:
    """SC 3 of this phase needs an asymmetry Nextcloud enforces, not one we assert.

    alice and bob alone only carry a leak test. The folder alice shares with bob read-only
    and the file she never shares are what make four non tautological statements measurable
    at all (05-RESEARCH.md, pitfall 6), and permissions=1 is what makes the refused upload a
    statement about Nextcloud's ACLs instead of a statement about our own tool.
    """
    assert share_fixture_problems(BOOTSTRAP.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("break_it", "expected"),
    [
        (
            lambda text: text.replace("\nensure_readonly_share() {\n", "\nensure_nothing() {\n"),
            "does not define ensure_readonly_share",
        ),
        (
            lambda text: text.replace("\nensure_readonly_share alice", "\n# no share here"),
            "never called in the main part",
        ),
        (
            lambda text: text.replace('-d "permissions=1"', '-d "permissions=31"'),
            "permissions=31",
        ),
        (
            lambda text: text.replace('-d "shareType=0"', '-d "shareType=3"'),
            "not created as a user share",
        ),
        (
            lambda text: text.replace(
                "shareapi_auto_accept_share --value=yes",
                "shareapi_auto_accept_share --value=no",
            ),
            "waits in the recipient's inbox",
        ),
        (
            lambda text: text.replace('share_is_readonly_for "$owner" "$owner_password"', "true"),
            "assumes instead",
        ),
        (
            lambda text: text.replace("PROPFIND \\\n", "GET \\\n"),
            "never proves that the recipient's home carries it",
        ),
        (
            lambda text: text.replace("NC_MCP_TEST_SHARED_FILE=", "SHARED_FILE_UNUSED="),
            "NC_MCP_TEST_SHARED_FILE is not written",
        ),
        (
            lambda text: text.replace(
                "NC_MCP_TEST_SHARED_DIR=${SHARED_DIR#/}", "NC_MCP_TEST_SHARED_DIR=/${SHARED_DIR}"
            ),
            "written as an absolute path",
        ),
        (
            lambda text: text.replace('cat >"${ENV_FILE}" <<EOF\n', 'echo "no file" # '),
            "not written from a heredoc",
        ),
    ],
    ids=[
        "no fixture function",
        "a fixture nobody calls",
        "a share that may be written to",
        "a share that is not a user share",
        "a share the recipient has to accept first",
        "a share that is assumed instead of read back",
        "a recipient whose home is never looked at",
        "a path the test never learns about",
        "a path Git Bash rewrites before pytest sees it",
        "a connection file that is not written",
    ],
)
def test_the_share_gate_fires_on_a_manipulated_script(
    break_it: Callable[[str], str], expected: str
) -> None:
    """The counter probe: without it the gate above could be green because it checks nothing.

    Each manipulation is one way the fixture would stop proving something while still looking
    complete, and the most dangerous one is the third: a share with write permission turns the
    refused upload into a green result that says nothing at all.
    """
    manipulated = break_it(BOOTSTRAP.read_text(encoding="utf-8"))
    assert manipulated != BOOTSTRAP.read_text(encoding="utf-8"), (
        "the manipulation changed nothing, so the script no longer has the shape it edits"
    )

    problems = share_fixture_problems(manipulated)

    assert any(expected in problem for problem in problems), problems


def test_the_share_fixture_pins_its_names_across_runs() -> None:
    """A fresh suffix per run would leave a second folder and a second share behind, and the
    test would then measure whichever of them the current connection file happens to name.
    Same reasoning as APP_SECRET, and the same shape: read the existing value, validate it,
    generate only when there is none."""
    body = shell_function("share_suffix")
    assert "NC_MCP_TEST_SHARED_DIR=" in body, "the suffix is not read back from the env file"
    assert "openssl rand -hex 5" in body, "there is no fresh suffix for a first run"
    assert "[0-9a-f]{10}" in body, "a hand written suffix would be adopted unchecked"


@needs_bash
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("NC_MCP_TEST_SHARED_DIR=mcp-share-0123456789\n", "0123456789"),
        ("NC_MCP_TEST_SHARED_DIR=/mcp-share-0123456789\n", "0123456789"),
        ("NC_MCP_TEST_SHARED_DIR=mcp-share-not-hex\n", ""),
        ("NC_MCP_TEST_SHARED_DIR=\n", ""),
        ("", ""),
    ],
    ids=[
        "a pinned suffix",
        "a pinned suffix from an older run",
        "a broken suffix",
        "an empty value",
        "no connection file yet",
    ],
)
def test_the_pinned_suffix_is_reused_and_a_broken_one_is_replaced(
    tmp_path: Path, stored: str, expected: str
) -> None:
    env_file = tmp_path / ".env.exapp"
    if stored:
        env_file.write_text(stored, encoding="utf-8", newline="\n")
    script = (
        "set -euo pipefail\n"
        f'ENV_FILE="{env_file.as_posix()}"\n'
        f"{shell_function('share_suffix')}\n"
        "share_suffix\n"
    )

    result = run_bash(script)

    assert result.returncode == 0, result.stderr
    if expected:
        assert result.stdout.strip() == expected
    else:
        assert re.fullmatch(r"[0-9a-f]{10}", result.stdout.strip()), result.stdout


@pytest.mark.parametrize(
    "forbidden",
    [
        '-e "OC_PASS=',
        '--json-info "$(',
        '--json-info "${json}"',
        '--harp_shared_key "${',
        '-u "${',
    ],
)
def test_no_secret_travels_through_the_process_list(forbidden: str) -> None:
    """WR-06: the argv of `docker` and `curl` is world readable in `ps aux` for the whole
    call, and every value these patterns carry is bearer equivalent: the registration
    payload holds "secret":"<APP_SECRET>", the daemon registration holds HP_SHARED_KEY,
    OC_PASS is a login password and `curl -u` an app password. All of them go through
    stdin or a private file now. Checked over every shell script, not only the bootstrap:
    the pattern crept back into two sister scripts once (02-REVIEW WR-01 to WR-03)."""
    scripts = sorted((ROOT / "scripts").glob("*.sh"))
    assert scripts, "no shell scripts found, the guard would silently pass"
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert forbidden not in text, (
            f"{forbidden!r} in {script.name} puts a secret on a command line"
        )


def test_the_secrets_reach_the_container_through_stdin() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "occ_stdin" in text
    assert 'OC_PASS="$(cat)"' in text
    assert 'JSON="$(cat)"' in text


def test_no_grep_q_on_a_pipe_in_the_shell_scripts() -> None:
    """The scripts run with pipefail, and `grep -q` exits on the first match, which closes
    the pipe while the docker side is still writing. That side then dies on SIGPIPE (exit
    141) and pipefail turns the successful check into a failure. Two CI runs failed exactly
    there, with the wanted calendar visibly printed one line above the failing check. A
    grep without -q reads its input to the end, so `grep pattern >/dev/null` is the shape
    every piped check uses; -q stays allowed where grep reads from a file, not a pipe.

    IN-05 is why the check is a pattern and no longer the literal `| grep -q`: every
    validator of `bootstrap_exapp.sh` piped into `grep -Eq` or `grep -Eqz`, which the
    literal did not see, so rule and gate had drifted apart and the next `| grep -Eq` on an
    occ pipe would have been waved through. Any letter may stand between the dash and the
    q, and a pipe may sit at the end of the line before it or behind a backslash.
    """
    piped_quiet = re.compile(r"\|\s*grep\s+(?:-[A-Za-z]*\s+)*-[A-Za-z]*q")
    scripts = sorted((ROOT / "scripts").glob("*.sh"))
    assert scripts, "no shell scripts found, the guard would silently pass"
    for script in scripts:
        # A pipe or a backslash at the end of a line continues the same command, and a rule
        # that only reads single lines would miss exactly the shape somebody reaches for
        # when the line gets long.
        text = re.sub(r"(\||\\)\s*\n\s*", r"\1 ", script.read_text(encoding="utf-8"))
        found = piped_quiet.findall(text)
        assert found == [], (
            f"{script.name} pipes into a quiet grep ({found}); under pipefail that is the "
            "SIGPIPE flake, and >/dev/null is the shape that reads its input to the end"
        )


def test_the_guard_sees_the_spellings_that_used_to_pass_it() -> None:
    """The counter probe of IN-05: the rule is a rule only if it catches the near misses.

    Without this, the guard above is a check on a literal that every writer of the script
    can miss by adding one letter, which is exactly what happened.
    """
    piped_quiet = re.compile(r"\|\s*grep\s+(?:-[A-Za-z]*\s+)*-[A-Za-z]*q")
    caught = (
        "docker exec x occ y | grep -q wanted",
        "docker exec x occ y | grep -Eq '^wanted$'",
        "printf '%s' \"$value\" | grep -Eqz '^https?://'",
        "docker exec x occ y |\n  grep -q wanted",
        "docker exec x occ y \\\n  | grep -Eq wanted",
        "docker exec x occ y | grep -E -q wanted",
    )
    allowed = (
        'grep -q "^name: x$" "${COMPOSE_FILE}"',
        "docker exec x occ y | grep -E '^wanted$' >/dev/null",
        "printf '%s' \"$value\" | grep -zE '^https?://' >/dev/null",
    )
    for line in caught:
        text = re.sub(r"(\||\\)\s*\n\s*", r"\1 ", line)
        assert piped_quiet.search(text), f"the guard has to see {line!r}"
    for line in allowed:
        text = re.sub(r"(\||\\)\s*\n\s*", r"\1 ", line)
        assert not piped_quiet.search(text), f"the guard must leave {line!r} alone"


def test_the_registration_verifies_what_the_registry_serves() -> None:
    """WR-09: the loopback registry takes a push from every local process, and the deploy
    daemon pulls by tag. A digest is the content, a tag is only a name."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "verify_image_digest" in text
    body = shell_function("ensure_exapp")
    assert body.index("verify_image_digest") < body.index("register_exapp"), (
        "the digest is checked after the registration triggered the pull"
    )


# --- the secret handling around the registration (CR-02) --------------------------

#: What the example file used to hand over as a working APP_SECRET, plus the shapes a
#: hand written value takes. None of them may survive into a registration.
WEAK_SECRETS = (
    "replace-me-with-a-random-hex-string",
    "nc-mcp-exapp-local-harp-key",
    "short",
    "0123456789abcdef",  # 16 hex characters, a quarter of what openssl produces
    "A" * 64,  # upper case, and not hex at all
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde",  # 63
)
GOOD_SECRET = "0123456789abcdef" * 4


@pytest.mark.parametrize("name", ["APP_SECRET", "HP_SHARED_KEY"])
def test_the_example_file_hands_out_no_usable_secret(name: str) -> None:
    """CR-02: `cp .env.exapp.example .env.exapp` used to publish the registration secret."""
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        assert not line.strip().startswith(f"{name}="), f"{name} is assignable in the example"


def test_the_example_file_says_that_it_is_read_and_not_copied() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "never copy it" in text


@needs_bash
@pytest.mark.parametrize("weak", WEAK_SECRETS)
def test_a_weak_app_secret_stops_the_bootstrap(tmp_path: Path, weak: str) -> None:
    """The attack path of CR-02, end to end: a placeholder must not become the secret."""
    env_file = tmp_path / ".env.exapp"
    env_file.write_text(f"APP_SECRET={weak}\n", encoding="utf-8")
    script = (
        "set -euo pipefail\n"
        f'ENV_FILE="{env_file.as_posix()}"\n'
        f"{shell_function('require_hex64')}\n"
        f"{shell_function('app_secret')}\n"
        "app_secret\n"
    )

    result = run_bash(script)

    assert result.returncode != 0, f"{weak!r} was accepted as APP_SECRET"
    assert weak not in result.stdout, "the weak value was printed as the secret to use"
    assert "64 lower case hex" in result.stderr


@needs_bash
def test_a_generated_app_secret_is_pinned_across_runs(tmp_path: Path) -> None:
    """The counter probe: the check must not break the reason the value is pinned at all
    (research pitfall 11, a fresh secret locks out whoever still holds the old one)."""
    env_file = tmp_path / ".env.exapp"
    env_file.write_text(f"APP_SECRET={GOOD_SECRET}\n", encoding="utf-8")
    script = (
        "set -euo pipefail\n"
        f'ENV_FILE="{env_file.as_posix()}"\n'
        f"{shell_function('require_hex64')}\n"
        f"{shell_function('app_secret')}\n"
        "app_secret\n"
    )

    result = run_bash(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == GOOD_SECRET


@needs_bash
def test_a_missing_env_file_still_generates_a_fresh_secret(tmp_path: Path) -> None:
    script = (
        "set -euo pipefail\n"
        f'ENV_FILE="{(tmp_path / "nothing-here").as_posix()}"\n'
        f"{shell_function('require_hex64')}\n"
        f"{shell_function('app_secret')}\n"
        "app_secret\n"
    )

    result = run_bash(script)

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(r"[0-9a-f]{64}", result.stdout.strip()), result.stdout


def test_the_shared_key_is_validated_like_the_app_secret() -> None:
    """Same class of secret, same gate: a foreign FRP client can attach with it."""
    body = shell_function("harp_shared_key")
    assert "require_hex64 HP_SHARED_KEY" in body


def test_the_documented_development_loop_stays_on_loopback() -> None:
    """WR-12: the same document explains at length why every port binds to 127.0.0.1 and
    then handed out APP_HOST=0.0.0.0, which publishes /init and /enabled to the LAN with
    APP_SECRET as their only guard, and that file sits in the same directory."""
    text = INSTALL_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**Do not"):
            continue
        assert "APP_HOST=0.0.0.0" not in stripped, f"the doc still prescribes {stripped!r}"


def test_the_reverse_proxy_routes_the_exapps_prefix() -> None:
    """Without this rule the installation fails at the heartbeat (research pitfall 7)."""
    text = CADDYFILE.read_text(encoding="utf-8")
    assert "/exapps/*" in text
    assert "appapi-harp:8780" in text


# --------------------------------------------------------------------------------------
# The public text of the manifest (plan 05-09)
#
# Two gates, both written as a function over the parsed root for the reason the module
# docstring gives: a gate nobody has seen fail is not a gate, so each one has a counter
# probe below that feeds it a manipulated manifest.
# --------------------------------------------------------------------------------------

#: The three language variants that exist today. ``None`` is the element without a ``lang``
#: attribute, which is the English original the store falls back to.
MANIFEST_LANGS = (None, "de", "fr")

#: XSD ``l10n-string`` for ``summary``, ``maxLength`` 128. ``description`` is ``l10n-text``
#: and has no upper bound, which is why only the summary is measured here.
SUMMARY_MAX_LENGTH = 128

#: Project vocabulary rule: this word must not appear in a public artefact of this repo,
#: and the manifest is the most public one there is. Matched case insensitively, and only
#: against element text, so the explanatory comments of the manifest cannot trip it.
FORBIDDEN_VOCABULARY = "archiv"

#: The four claims of decision D-v1.5-02, which no text of this project may make: that a
#: record here is revision proof, that this app is compliant with the AI Act, that it is
#: compliant with the GDPR, or that anything about it is SIEM certified. Nobody audited,
#: certified or legally assessed this app, and the store description is read by people who
#: have to answer for such a sentence.
#:
#: Forbidden is the claim, not the word, and that distinction is the whole reason this is a
#: list of patterns instead of a second :data:`FORBIDDEN_VOCABULARY`. A bare substring rule
#: would be red today in three places that are all legitimate: ``docs/spike-opendesk.md``
#: writes down "Audit-Log mit SIEM-Ausleitung" as an open negotiation question about what
#: somebody else offers, ``docs/oauth-setup.md:204`` says "specification compliant client",
#: and ``README.fr.md:68`` says "conforme a la specification". A privacy text also has to be
#: able to say that this log has no SIEM connection and that the GDPR binds the operator of
#: the instance. Each of those three has its own case next to the gate below.
#:
#: One pattern per claim, ``re.I``, the German, English and French form of it, and an
#: optional separator between the parts, because English writes "AI Act compliant" with a
#: space where German writes "AI-Act-konform" with a hyphen. Stricter than this list is
#: allowed, laxer is not.
FORBIDDEN_CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "revisionssicher",
        re.compile(r"revisionssicher|tamper[\s-]*proof|audit[\s-]*proof|inviolable", re.I),
    ),
    ("AI-Act-konform", re.compile(r"ai[\s-]*act[\s-]*(?:konform|compliant|conformes?)", re.I)),
    (
        "DSGVO-konform",
        re.compile(
            r"(?:dsgvo|gdpr|rgpd)[\s-]*(?:konform|compliant|conformes?)"
            r"|conformes?[\s-]*(?:au|aux|a la|à la)?[\s-]*(?:rgpd|gdpr|dsgvo)",
            re.I,
        ),
    ),
    (
        "SIEM-zertifiziert",
        re.compile(r"siem[\s-]*(?:zertifiziert|certified|certifi[eé]e?s?)", re.I),
    ),
)

#: A line that renders as a table row or a table separator in either pipeline.
TABLE_LINE = re.compile(r"\|")

#: A markdown or HTML image.
IMAGE_MARKUP = re.compile(r"!\[[^\]]*\]\(|<\s*img", re.IGNORECASE)

#: A thematic break: three or more of -, * or _ alone on a line.
HORIZONTAL_RULE = re.compile(r"^[ \t]{0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$", re.MULTILINE)

#: Any HTML element, opening or closing.
HTML_ELEMENT = re.compile(r"<\s*/?\s*[a-zA-Z]")


def _lang_label(lang: str | None) -> str:
    return lang or "en"


def _localised(root: etree._Element, tag: str, lang: str | None) -> str | None:
    """The text of ``tag`` for one language, or ``None`` when that variant is missing."""
    for element in root.findall(tag):
        if element.get("lang") == lang:
            return element.text or ""
    return None


def element_text_without_comments(root: etree._Element) -> str:
    """Every piece of element text in the manifest, with comments left out.

    The manifest carries long explanatory comments, several of which quote the words a
    gate looks for. A grep over the file would therefore fail on its own documentation,
    so the vocabulary check reads the parsed tree and skips comment and processing
    instruction nodes.
    """
    parts: list[str] = []
    for node in root.iter():
        if isinstance(node, etree._Comment | etree._ProcessingInstruction):
            continue
        if node.text:
            parts.append(node.text)
    return "\n".join(parts)


def description_problems(root: etree._Element) -> list[str]:
    """Return every reason this manifest's public text must not be shipped.

    The store description is the only text a user reads without visiting the repository,
    and it is rendered by two different pipelines. On apps.nextcloud.com it is Python
    ``markdown`` plus ``bleach`` with ``MARKDOWN_ALLOWED_TAGS``, which allows tables,
    ``code`` and ``pre``. In the app detail view of the instance it is ``marked`` with
    ``gfm: false, breaks: false``, followed by ``dompurify.sanitize`` with an allow list of
    ``h1..h6, strong, p, a, ul, ol, li, em, del, blockquote`` and nothing else: no ``code``,
    no ``pre``, no ``table``, no ``br``, no ``img``, no ``hr``. Whatever is written with
    backticks or in a table is not degraded there, it disappears, and ``breaks: false``
    means a single newline produces no break at all, so a text with single line breaks
    arrives as one clump (pitfall 4 of 05-RESEARCH.md).

    So the rule is the smaller common denominator: headings, bold, italic, links, lists,
    blockquote, and paragraphs separated by a blank line.
    """
    problems: list[str] = []

    for lang in MANIFEST_LANGS:
        label = _lang_label(lang)

        summary = _localised(root, "summary", lang)
        if summary is None:
            problems.append(f"the {label} summary is missing")
        elif len(summary.strip()) > SUMMARY_MAX_LENGTH:
            problems.append(
                f"the {label} summary is {len(summary.strip())} characters, "
                f"the schema allows {SUMMARY_MAX_LENGTH}"
            )

        description = _localised(root, "description", lang)
        if description is None:
            problems.append(f"the {label} description is missing")
            continue

        if "`" in description:
            problems.append(f"the {label} description carries a backtick")
        if TABLE_LINE.search(description):
            problems.append(f"the {label} description carries a table")
        if IMAGE_MARKUP.search(description):
            problems.append(f"the {label} description carries an image")
        if HORIZONTAL_RULE.search(description):
            problems.append(f"the {label} description carries a horizontal rule")
        if HTML_ELEMENT.search(description):
            problems.append(f"the {label} description carries an HTML element")

        paragraphs = [
            block for block in re.split(r"\n[ \t]*\n", description.strip()) if block.strip()
        ]
        if len(paragraphs) < 2:
            problems.append(
                f"the {label} description has {len(paragraphs)} paragraph(s); "
                "single line breaks disappear in the instance view, so paragraphs need a "
                "blank line between them"
            )

    text = element_text_without_comments(root)
    if FORBIDDEN_VOCABULARY in text.casefold():
        problems.append(f"the manifest text carries the forbidden word {FORBIDDEN_VOCABULARY!r}")

    return problems


def variable_problems(root: etree._Element) -> list[str]:
    """Return every reason the declared environment variables must not be shipped.

    One rule, and it is not cosmetic. AppAPI 34.0.3 filters a declared default against the
    empty string only, not against "not a scalar", and ``simplexml``/``json`` turns an empty
    XML element into an empty array. So ``<default></default>`` reaches the container as the
    literal value ``Array``: ``NC_MCP_OAUTH_DCR=Array``, which is neither on nor off. AppAPI
    main fixed this in ``ExAppEnvVarsHelper::toString()``; that file does not exist on
    34.0.3. The store answers the same mistake with a 500 on the release upload (fix
    b0ac128), so an empty element costs either a broken deploy environment or a rejected
    upload (pitfall 3 of 05-RESEARCH.md).

    Either fill a default or leave the element out. Which variables that is about is not
    written here as a number: the set is pinned by
    :func:`test_every_variable_the_code_reads_is_declared_in_the_manifest` in this same file,
    and a count in this sentence would be a second truth that the next switch makes wrong
    without a single test noticing (review finding IN-03). Not one of them carries a default
    today, and that is the safe state.
    """
    problems: list[str] = []

    for variable in root.findall(".//variable"):
        name = (variable.findtext("name") or "?").strip()
        for default in variable.findall("default"):
            if not (default.text or "").strip():
                problems.append(
                    f"variable {name!r} declares an empty <default>; AppAPI 34.0.3 exports "
                    "it as the string 'Array' and the store answers with a 500"
                )

    return problems


def test_the_manifest_text_passes_its_own_gate(manifest_root: etree._Element) -> None:
    """Every language variant survives the narrower of the two rendering pipelines."""
    assert description_problems(manifest_root) == []


def test_every_description_carries_the_answer_of_the_faq(manifest_root: etree._Element) -> None:
    """The store text is the only place a user reads without visiting the repository, so
    the answer has to stand there and not only be linked (05-RESEARCH open question 2).

    One marker per fact, in the language of the variant: nothing runs on its own, there is
    a switch per account, and a connection can be ended on its own.

    The fourth triple belongs to the same rule and was added with the Mail family (SEC-01).
    The most important capability statement of that phase is that mail is read only, and a
    reader who decides whether to install this app decides on this text: a sentence that
    lives in the repository alone is not in front of them when they decide.
    """
    markers = {
        None: ("background", "switch", "disconnect", "read only"),
        "de": ("Hintergrund", "Schalter", "trenn", "nur lesen"),
        "fr": ("arrière-plan", "interrupteur", "déconnect", "lecture seule"),
    }

    for lang, expected in markers.items():
        description = _localised(manifest_root, "description", lang)
        assert description is not None
        for marker in expected:
            assert marker in description, f"the {_lang_label(lang)} description misses {marker!r}"


def test_no_description_names_a_blocked_mailbox(manifest_root: etree._Element) -> None:
    """The Mail bullet names the levels of the tool, never the standard folder names.

    This is the one place where a natural sentence walks into
    :data:`FORBIDDEN_VOCABULARY`. That word is matched case insensitively and as a
    substring, and the obvious enumeration of the standard folders of a mail account
    carries it in every one of the three languages at once, so the gate would turn red
    three times over a list nobody needs: the tool navigates accounts, mailboxes and
    messages, and the store text says exactly that.

    ``description_problems`` already refuses the word over the whole manifest. This test
    is narrower on purpose: it names the reason, so the next rewrite of the text reads it
    here instead of rediscovering it against a red run.
    """
    for lang in MANIFEST_LANGS:
        description = _localised(manifest_root, "description", lang)
        assert description is not None
        assert FORBIDDEN_VOCABULARY not in description.casefold(), (
            f"the {_lang_label(lang)} description names a blocked mailbox; "
            "name the levels of mail_browse instead of the standard folders"
        )


def test_no_description_carries_the_rag_acronym(manifest_root: etree._Element) -> None:
    """The store text speaks plain language and never says the acronym (BL-01).

    The audience split of BL-01 sends the acronym to the READMEs and the developer
    documents; the store description addresses a reader who decides on plain words.
    The match is case sensitive and bound to word boundaries on purpose: the lowercase
    substring sits inside "storage", "fragenden" and "interrogeable", so casefolding
    would turn the gate red over ordinary prose.
    """
    for lang in MANIFEST_LANGS:
        description = _localised(manifest_root, "description", lang)
        assert description is not None
        assert re.search(r"\bRAG\b", description) is None, (
            f"the {_lang_label(lang)} description carries the acronym; "
            "the store speaks plain language, the acronym lives in the READMEs "
            "and the developer documents (BL-01 audience split)"
        )


def test_the_text_gate_rejects_a_backtick_and_a_table(manifest_root: etree._Element) -> None:
    """The counter probe: without it, the green run above proves nothing about the gate.

    Exactly the shape pitfall 4 warns about first, a fenced snippet and a table, written
    into the German variant.
    """
    for element in manifest_root.findall("description"):
        if element.get("lang") == "de":
            element.text = (
                "Setzen Sie `NC_MCP_PUBLIC_URL`.\n\n"
                "| Variable | Zweck |\n| --- | --- |\n| NC_MCP_PUBLIC_URL | Adresse |\n"
            )

    problems = description_problems(manifest_root)

    assert any("de description carries a backtick" in problem for problem in problems)
    assert any("de description carries a table" in problem for problem in problems)


def test_the_text_gate_rejects_single_line_breaks(manifest_root: etree._Element) -> None:
    """``breaks: false`` in the instance view: four sentences on four lines are one clump,
    which is what the shipped text looked like before this plan."""
    for element in manifest_root.findall("description"):
        if element.get("lang") is None:
            element.text = "One sentence.\nA second one.\nA third one.\n"

    problems = description_problems(manifest_root)

    assert any("en description has 1 paragraph(s)" in problem for problem in problems)


def test_the_text_gate_rejects_html_an_image_and_a_rule(manifest_root: etree._Element) -> None:
    """``dompurify`` drops all three, so each of them is content that vanishes."""
    for element in manifest_root.findall("description"):
        if element.get("lang") == "fr":
            element.text = (
                "Premier paragraphe.\n\n"
                "---\n\n"
                "<b>Deuxième</b> paragraphe.\n\n"
                "![capture](https://example.org/a.png)\n"
            )

    problems = description_problems(manifest_root)

    assert any("fr description carries an HTML element" in problem for problem in problems)
    assert any("fr description carries an image" in problem for problem in problems)
    assert any("fr description carries a horizontal rule" in problem for problem in problems)


def test_the_text_gate_rejects_a_summary_over_the_schema_limit(
    manifest_root: etree._Element,
) -> None:
    """``l10n-string`` has ``maxLength`` 128; the store rejects a longer one on upload."""
    for element in manifest_root.findall("summary"):
        if element.get("lang") is None:
            element.text = "x" * (SUMMARY_MAX_LENGTH + 1)

    problems = description_problems(manifest_root)

    assert any("en summary is 129 characters" in problem for problem in problems)


def test_the_text_gate_rejects_the_forbidden_vocabulary(manifest_root: etree._Element) -> None:
    """The project vocabulary rule, on the most public artefact of the repository."""
    for element in manifest_root.findall("description"):
        if element.get("lang") is None:
            element.text = "First paragraph.\n\nThe Archive of your data stays untouched.\n"

    problems = description_problems(manifest_root)

    assert any("forbidden word" in problem for problem in problems)


# --------------------------------------------------------------------------------------
# The same rule, at the reach of its own wording (SEC-02c, UF-3, plan 12-03)
#
# The vocabulary rule was always meant for every public artefact of this repository, while
# the gate above reads the manifest only. So the gate grows and the word list stays exactly
# where it is: two places holding the same word would be two truths, which is the mistake
# this project named IN-03 and removed, and moving the list into a new file would rebuild a
# green security gate without making the rule any better. The price is a file name that is
# thematically wider than its content, and that is cheaper than either.
# --------------------------------------------------------------------------------------

#: The public pages outside ``docs/``, named one by one instead of globbed: a glob would
#: silently start or stop covering a page, while this tuple is the statement about reach.
PUBLIC_MARKDOWN = (
    ROOT / "README.md",
    ROOT / "README.de.md",
    ROOT / "README.fr.md",
    ROOT / "CHANGELOG.md",
)

#: The one page exempt by name. Internal release documentation that does not travel in the
#: store archive, holding two dated proof lines (``:124`` and ``:125``) whose later rewording
#: would reverse the direction of the evidence (T-11-63), and a foreign Nextcloud class name
#: in ``:281`` that cannot be renamed without making the sentence false. The exemption is
#: bound to a checkable property below rather than to this comment.
VOCABULARY_EXCEPTION = ROOT / "docs" / "store-submission.md"

#: Verbatim third party text inside the store archive. The AGPL-3.0 wording carries the word
#: in its own sentence about a source link (``LICENSE:653``). It is not this project's prose,
#: and editing a license text to satisfy a house rule would falsify the license, so it is
#: exempt for a sharper reason than the release log.
VERBATIM_ARCHIVE_TEXT = ("LICENSE",)

#: The build script is the only truth about what the store gets, so the list is read from it.
STORE_RELEASE_SCRIPT = ROOT / "scripts" / "build_store_release.sh"

#: One copied file of ``scripts/build_store_release.sh``, as a repository relative path.
ARCHIVE_MEMBER = re.compile(r'cp "\$ROOT/([^"]+)"')


def vocabulary_findings(text: str, name: str) -> list[str]:
    """Return one entry per line of ``text`` carrying the forbidden word, name and line first.

    Text and name are parameters and nothing is read inside, so the gate can point this at a
    real page while its counter probe points the same function at a constructed one. Case is
    ignored exactly as in the manifest gate, and a finding names the line, so a violation is a
    one line correction and not a search through the tree.
    """
    needle = FORBIDDEN_VOCABULARY.casefold()
    return [
        f"{name}:{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        if needle in line.casefold()
    ]


def public_markdown_pages() -> list[Path]:
    """Every markdown page the rule reaches: the four public documents plus all of ``docs/``.

    Markdown and the manifest, and deliberately nothing else. ``scripts/build_store_release.sh``
    and its neighbours stay out: ``ARCHIVE`` is a variable name there and ``tar`` is the tool
    that builds the package, so a check over the scripts would turn the gate red in a place the
    rule never addressed.

    ``rglob`` and not ``glob``, because the claim is "the rest of docs/" and
    ``docs/contrib/227-pr-body.md`` already lives one folder down: a non-recursive glob would
    let every future page under a subfolder escape silently (review finding WR-05). The
    subfolder reach is pinned in the self test below, so a change back to ``glob`` goes red.

    ``.planning`` stays out too, and that is a decision rather than an oversight (SEC-03,
    milestone v1.4). The rule addresses the published surface: what the store receives, and what
    a reader of this repository's documentation gets, which is the three READMEs, the changelog,
    everything under ``docs/`` and the manifest texts. ``.planning`` is the internal planning
    area on the other side of that border. It travels in no store archive, and its filed
    milestone and phase documents carry the word in a technical ``tar`` context as a dated
    measurement, so cleaning them would falsify a record instead of improving a text. The same
    border is already drawn in ``pyproject.toml``, where ruff excludes ``.planning`` for the same
    reason. ``test_the_vocabulary_gate_stops_at_the_internal_planning_area`` below holds it, so
    the reach cannot widen without someone taking the decision again.
    """
    docs = sorted(page for page in (ROOT / "docs").rglob("*.md") if page != VOCABULARY_EXCEPTION)
    pages = [*PUBLIC_MARKDOWN, *docs]
    assert pages, f"no public markdown found under {ROOT}"
    return pages


def archive_members() -> list[str]:
    """The repository relative files ``scripts/build_store_release.sh`` puts into the archive."""
    members = ARCHIVE_MEMBER.findall(STORE_RELEASE_SCRIPT.read_text(encoding="utf-8"))
    assert members, f"no copied files found in {STORE_RELEASE_SCRIPT}"
    return members


def test_no_public_markdown_page_carries_the_forbidden_vocabulary() -> None:
    """UF-3: the rule now reaches the three READMEs, the changelog and the rest of ``docs/``.

    ``CHANGELOG.md`` is covered from here on, which matters for the 0.1.9 entry: it is written
    under this rule instead of being checked after the fact. The single exemption is
    :data:`VOCABULARY_EXCEPTION`, and the reason is not convenience: rewriting a dated proof
    line afterwards would turn a record into a claim.
    """
    findings = [
        finding
        for page in public_markdown_pages()
        for finding in vocabulary_findings(
            page.read_text(encoding="utf-8"), page.relative_to(ROOT).as_posix()
        )
    ]

    assert findings == [], (
        f"a public page carries the forbidden word {FORBIDDEN_VOCABULARY!r}: " + "; ".join(findings)
    )


def test_the_vocabulary_gate_reads_a_list_that_is_not_empty() -> None:
    """Without this, a wrong directory would make the gate above green over nothing.

    That is the way a gate which is green on arrival becomes worthless: it keeps passing, and
    the run that should have caught the word never looked at a file.
    """
    names = {page.relative_to(ROOT).as_posix() for page in public_markdown_pages()}

    assert {"README.md", "README.de.md", "README.fr.md", "CHANGELOG.md"} <= names, names
    assert "docs/store-submission.md" not in names, "the exemption is exempt, not silently read"
    assert "docs/contrib/227-pr-body.md" in names, (
        "the rule claims the rest of docs/, and this page one folder down is the proof that "
        "the walk is recursive (review finding WR-05)"
    )
    assert len(names) > len(PUBLIC_MARKDOWN), "the docs pages belong to the covered set too"
    for page in public_markdown_pages():
        assert page.read_text(encoding="utf-8").strip(), f"{page} was read as empty"


def test_the_store_archive_carries_no_exempt_page() -> None:
    """The exemption hangs on a checkable property instead of on a sentence of prose.

    The list comes from the build script, not from memory: everything the store gets is clean,
    and the exempt release log is not among it. ``LICENSE`` is the one member that carries the
    word and stays untouched, because it is the verbatim AGPL text (:data:`VERBATIM_ARCHIVE_TEXT`).
    """
    members = archive_members()

    assert {"appinfo/info.xml", "CHANGELOG.md", "LICENSE", "README.md"} <= set(members), members
    assert VOCABULARY_EXCEPTION.relative_to(ROOT).as_posix() not in members, (
        "the exempt page must not travel in the store archive"
    )

    findings = [
        finding
        for member in members
        if member not in VERBATIM_ARCHIVE_TEXT
        for finding in vocabulary_findings((ROOT / member).read_text(encoding="utf-8"), member)
    ]
    assert findings == [], "everything the store receives is clean: " + "; ".join(findings)


def test_the_widened_vocabulary_gate_reports_the_word_with_its_line() -> None:
    """Counter proof, and it has to be constructed: no covered page carries the word today.

    A probe against a real file would only prove that the file is clean. This one proves that
    the check sees the word in either spelling and points at the right line.
    """
    constructed = "\n".join(
        [
            "# Release notes",
            "Nothing is deleted and nothing is moved.",
            "The Archive of your data stays untouched.",
            "ARCHIVIERUNG is the same word in shouting.",
        ]
    )

    findings = vocabulary_findings(constructed, "README.md")

    assert [finding.split(": ", 1)[0] for finding in findings] == [
        "README.md:3",
        "README.md:4",
    ], findings


def test_the_vocabulary_gate_stops_at_the_internal_planning_area() -> None:
    """SEC-03: ``.planning`` is out of reach by decision, and the decision hangs on a property.

    The rule addresses the published surface, the store archive and the documentation a reader of
    this repository gets. The internal planning area travels in no archive, and its filed
    milestone documents carry the word as a dated measurement in a technical ``tar`` context, so
    cleaning them would falsify a record. If this goes red the border has moved: take the
    decision again in the open, instead of quietly pushing the border back to where it was.
    """
    for page in public_markdown_pages():
        assert ".planning" not in page.parts, (
            f"{page.relative_to(ROOT).as_posix()} is internal planning, not a published page"
        )

    for member in archive_members():
        assert not member.startswith(".planning/"), (
            f"{member} would carry the internal planning area into the store archive"
        )


# --------------------------------------------------------------------------------------
# The four claims this project cannot keep (AUDIT-06, decision D-v1.5-02, plan 19-03)
#
# Same reach, same message shape and same kind of counter probe as the vocabulary gate
# above, and the list lives next to that one for the reason its own comment gives: two
# places holding the same kind of rule would be two truths. What differs is the rule.
# Forbidden here is the claim and not the word, so :data:`FORBIDDEN_CLAIMS` carries word
# forms per language instead of bare substrings. The three legitimate occurrences a bare
# substring list would hit today are named in the comment of that constant and each one
# has its own case below, so a later tightening of the patterns cannot swallow them
# unnoticed.
# --------------------------------------------------------------------------------------


def claim_findings(text: str, name: str) -> list[str]:
    """Return one entry per line and claim in ``text``, name, line number and claim first.

    The shape of :func:`vocabulary_findings` and for the same reason: a violation is a one
    line correction and not a search through the tree, and the claim is named so the message
    says which promise was made and not only that some pattern matched. Text and name are
    parameters and nothing is read inside, so the gate can point this at a real page while
    the counter probes point the same function at a constructed line and at a manifest that
    exists only in memory.
    """
    return [
        f"{name}:{number}: {claim}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        for claim, pattern in FORBIDDEN_CLAIMS
        if pattern.search(line)
    ]


def test_no_public_text_carries_a_forbidden_claim(manifest_root: etree._Element) -> None:
    """The gate: every public markdown page of this repository plus the manifest text.

    The reach is the one of the vocabulary gate, read from the same function, so a page
    added under ``docs/`` is covered by both rules or by neither. The manifest travels
    through :func:`element_text_without_comments` for the same reason as there: its own
    explanatory comments quote the words a gate looks for.
    """
    findings = [
        finding
        for page in public_markdown_pages()
        for finding in claim_findings(
            page.read_text(encoding="utf-8"), page.relative_to(ROOT).as_posix()
        )
    ]
    findings += claim_findings(element_text_without_comments(manifest_root), "appinfo/info.xml")

    assert findings == [], "a public text carries a claim nobody here can keep: " + "; ".join(
        findings
    )


def test_the_claim_of_a_revision_proof_log_is_reported_with_its_line() -> None:
    """The German compound, and the message names the file and the line, nothing else."""
    findings = claim_findings("This log is revisionssicher.\n", "probe.md")

    assert len(findings) == 1, findings
    assert findings[0].startswith("probe.md:1:"), findings[0]


def test_the_claim_of_gdpr_compliance_is_reported() -> None:
    """The English form of the claim, the one a store description would carry."""
    assert claim_findings("Our store description says GDPR compliant.\n", "probe.md")


def test_the_claim_of_ai_act_compliance_is_reported() -> None:
    """Two words with a space between them, which is how English writes this claim."""
    assert claim_findings("The app is AI Act compliant.\n", "probe.md")


def test_the_french_claim_of_gdpr_compliance_is_reported() -> None:
    """French puts the regulation last, so the pattern has to read both word orders."""
    assert claim_findings("conforme au RGPD\n", "probe.md")


def test_the_claim_of_a_siem_certification_is_reported() -> None:
    """Nobody certified this log for anything, in any language."""
    assert claim_findings("SIEM certified\n", "probe.md")


def test_the_siem_readout_question_of_the_spike_is_no_claim() -> None:
    """``docs/spike-opendesk.md`` records an open question about a SIEM readout.

    That page is inside the reach of the gate, and a bare substring list would turn it
    red for writing down what somebody else offers. A text of this project may also say
    that this log has no SIEM connection at all.
    """
    assert claim_findings("Audit-Log mit SIEM-Ausleitung ist offen.\n", "probe.md") == []


def test_a_specification_compliant_client_is_no_claim() -> None:
    """``docs/oauth-setup.md:204`` says "specification compliant client" and stays."""
    assert claim_findings("a specification compliant client\n", "probe.md") == []


def test_the_french_conformance_to_the_specification_is_no_claim() -> None:
    """``README.fr.md:68`` says "conforme a la specification", with and without accents."""
    assert claim_findings("conforme a la specification\n", "probe.md") == []
    assert claim_findings("conforme à la spécification d'autorisation MCP\n", "x.md") == []


def test_a_plain_sentence_about_the_audit_log_is_no_claim() -> None:
    """The wording "Audit-Log" itself stays allowed: the phase writes it into three texts."""
    assert claim_findings("Das Audit-Log hält seine Einträge hash-verkettet.\n", "probe.md") == []


def test_the_claim_gate_fires_on_a_constructed_line() -> None:
    """Counter probe, and it has to be constructed: no covered page carries a claim today.

    Without it the green run of the gate above says that the check ran, not that it checks.
    Once per claim rather than once for the list, so a red line names the pattern that
    stopped matching instead of the fact that some pattern did.

    The count comes first for the same reason
    :func:`test_the_vocabulary_gate_reads_a_list_that_is_not_empty` exists: a loop over an
    emptied list passes without looking at anything, so the four claims of decision
    D-v1.5-02 are stated here as a number. Adding a fifth claim is meant to make this line
    red once, in the open, and not to slip past a probe that measures nothing.
    """
    assert len(FORBIDDEN_CLAIMS) == 4, FORBIDDEN_CLAIMS

    for claim, _ in FORBIDDEN_CLAIMS:
        findings = claim_findings(f"This log is {claim}.\n", "probe.md")

        assert findings, f"the pattern of {claim} matches its own claim no more"
        assert any(claim in finding for finding in findings), (
            f"a finding has to name the claim it is about, {claim} is missing: {findings}"
        )


def test_the_claim_gate_fires_on_the_manifest_text(manifest_root: etree._Element) -> None:
    """The second half of the reach, probed the way the vocabulary gate probes it.

    The tree is changed in memory and the file on disk is not touched, so this proves that a
    claim written into the English store description is found, without a fixture that has to
    be cleaned up afterwards.
    """
    for element in manifest_root.findall("description"):
        if element.get("lang") is None:
            element.text = "First paragraph.\n\nThis app is GDPR compliant.\n"

    findings = claim_findings(element_text_without_comments(manifest_root), "appinfo/info.xml")

    assert findings, "a claim in the store description has to be found"
    assert any("DSGVO-konform" in finding for finding in findings), findings


def test_no_declared_variable_carries_an_empty_default(manifest_root: etree._Element) -> None:
    """The shipped state: nine variables, not one default among them."""
    assert variable_problems(manifest_root) == []


def test_every_variable_the_code_reads_is_declared_in_the_manifest(
    manifest_root: etree._Element,
) -> None:
    """The most expensive silent mistake of this package, held as set equality.

    The deploy daemon injects a variable into the container if, and only if, the manifest
    declares it (AppAPI ``ExAppService::getAppInfo``, measured against 34.0.0 in plan 03-08).
    An undeclared one is accepted by ``occ app_api:app:register --env`` and dropped without a
    word, so the switch stands on its code default forever and the administrator has no way
    to see why. Set equality rather than a subset: a variable declared here and read nowhere
    is an offer this app does not keep either.

    Six became nine with plan 19-07, and the reason is not convenience. The retention window
    and the upper bound of the audit log are described in public for the first time in this
    phase, in the pages of AUDIT-06 and in the labels of AUDIT-05. A limit that is described
    and cannot be set, because the deploy daemon drops what this manifest does not declare,
    would be half of a promise. The way meant for an administrator stays the admin settings
    of this app (BL-06); these three are the way of an installation set up by hand.
    """
    declared = {
        (variable.findtext("name") or "").strip()
        for variable in manifest_root.findall(".//environment-variables/variable")
    }

    assert declared == {
        config.ENV_PUBLIC_URL,
        registry.ENV_DCR,
        registry.ENV_CIMD,
        registry.ENV_ALLOWLIST_ONLY,
        registry.ENV_ALLOWED_CLIENTS,
        config.ENV_TALK_SEND,
        config.ENV_AUDIT_LOG,
        config.ENV_AUDIT_RETENTION_DAYS,
        config.ENV_AUDIT_MAX_BYTES,
    }


def test_every_declared_variable_carries_the_three_elements_an_admin_reads(
    manifest_root: etree._Element,
) -> None:
    """A declaration without a label is a nameless input field in the deploy dialogue."""
    for variable in manifest_root.findall(".//environment-variables/variable"):
        name = (variable.findtext("name") or "").strip()
        assert name, "a declared variable has no name"
        for element in ("display-name", "description"):
            assert (variable.findtext(element) or "").strip(), f"{name} has no {element}"


def test_the_cimd_declaration_names_the_switch_it_is_coupled_to(
    manifest_root: etree._Element,
) -> None:
    """``cimd_enabled`` is derived from both switches, so the text has to say the other name.

    An administrator who switches self registration off switches the metadata document way
    off with it. Without that sentence in the description she reads two independent switches,
    turns the second one on, and measures a state the code never produces.
    """
    for variable in manifest_root.findall(".//environment-variables/variable"):
        if (variable.findtext("name") or "").strip() == registry.ENV_CIMD:
            assert registry.ENV_DCR in (variable.findtext("description") or "")
            return
    pytest.fail(f"{registry.ENV_CIMD} is not declared in the manifest")


def test_the_variable_gate_rejects_an_empty_default(manifest_root: etree._Element) -> None:
    """The counter probe for the second gate, with the exact element somebody adds for
    documentation purposes and which then arrives in the container as ``Array``."""
    variable = manifest_root.find(".//variable")
    assert variable is not None
    etree.SubElement(variable, "default")

    problems = variable_problems(manifest_root)

    assert any("empty <default>" in problem for problem in problems)


def test_the_variable_gate_accepts_a_filled_default(manifest_root: etree._Element) -> None:
    """The other half of the rule: a default with content is allowed, only an empty
    element is the trap, so the gate must not simply forbid the element."""
    variable = manifest_root.find(".//variable")
    assert variable is not None
    etree.SubElement(variable, "default").text = "off"

    assert variable_problems(manifest_root) == []


# --------------------------------------------------------------------------------------
# The Enterprise paragraph, held together at six places (AUDIT-06, plan 19-08)
#
# One paragraph, three languages, two files each: the three descriptions of the manifest
# and the three READMEs. The 0.1.10 entry of the changelog records that this paragraph was
# always maintained across all six of them at once, and a reader ever sees only one of the
# six, so a drift between them is a repudiation risk and not an untidiness (T-19-31).
#
# The sentence this paragraph carried until phase 19 said that the audit log is planned as
# a commercial add-on. Phase 18 built it, which made that sentence false, and the second
# test below is the reason a text truth of this kind survives the next phase: it forbids
# the word for planned in any line that also carries the word for the audit log. What is
# still planned are group policies and sign in through the identity provider of the
# organisation, and neither of them is the record this app now keeps.
#
# The manifest way goes over the descriptions and their ``lang`` attribute rather than over
# :func:`element_text_without_comments`: here the language is the distinction, and the
# comments of the manifest are not part of any of the six places.
# --------------------------------------------------------------------------------------

#: Per language: the ``lang`` attribute of the manifest description, the README of that
#: language, the three markers the paragraph owes, and the word forms for "planned".
#:
#: The markers are the load bearing statements of the paragraph and not decoration: the
#: name of the record, that it is off until somebody switches it on, and the first of the
#: two things that are still planned. A rewrite that drops one of the three has dropped a
#: statement, which is exactly when this should go red.
#:
#: The French entry carries the accented and the bare spelling of "planned", because the
#: separation rule has to hold whichever of the two a later hand writes; the markers
#: themselves are accented, because that is the house rule for the text.
ENTERPRISE_MARKERS: tuple[tuple[str | None, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (None, "README.md", ("audit log", "off by default", "group policies"), ("planned",)),
    ("de", "README.de.md", ("Audit-Log", "ab Werk aus", "Gruppen-Policies"), ("geplant",)),
    (
        "fr",
        "README.fr.md",
        ("journal d'audit", "désactivé par défaut", "politiques de groupe"),
        ("prévu", "prevu"),
    ),
)

#: A heading of the Enterprise section, at either of the two levels the two formats use:
#: the READMEs write ``## Enterprise`` and the store descriptions ``### Enterprise``.
ENTERPRISE_HEADING = re.compile(r"^#{2,3}\s+Enterprise\s*$")


def enterprise_section(text: str, name: str) -> str:
    """The lines below the Enterprise heading of ``text``, up to the next heading.

    The section and not the whole document, so a marker that happens to appear elsewhere
    on the page cannot stand in for the paragraph that owes it. Text and name are
    parameters for the reason :func:`vocabulary_findings` states: the same function reads
    a README from disk and a store description out of the parsed tree.
    """
    lines = text.splitlines()
    starts = [number for number, line in enumerate(lines) if ENTERPRISE_HEADING.match(line.strip())]
    assert len(starts) == 1, f"{name} carries {len(starts)} Enterprise headings, expected one"

    start = starts[0]
    end = next(
        (number for number in range(start + 1, len(lines)) if lines[number].startswith("#")),
        len(lines),
    )
    section = "\n".join(lines[start + 1 : end]).strip()
    assert section, f"the Enterprise section of {name} is empty"
    return section


def enterprise_places(manifest_root: etree._Element) -> list[tuple[str, tuple[str, ...], str]]:
    """The six places as (name, markers, section), two per language.

    Six and not three: the manifest half and the README half of one language say the same
    thing to two different readers, and only one of the two is ever in front of a reader.
    """
    places: list[tuple[str, tuple[str, ...], str]] = []
    for lang, readme, markers, _ in ENTERPRISE_MARKERS:
        description = _localised(manifest_root, "description", lang)
        assert description is not None, f"the {_lang_label(lang)} description is missing"
        manifest_name = f"appinfo/info.xml ({_lang_label(lang)})"
        places.append((manifest_name, markers, enterprise_section(description, manifest_name)))
        places.append(
            (readme, markers, enterprise_section((ROOT / readme).read_text("utf-8"), readme))
        )
    return places


def test_the_enterprise_paragraph_carries_its_markers_at_all_six_places(
    manifest_root: etree._Element,
) -> None:
    """The three languages and the two formats say the same thing or this goes red.

    Every gap is collected before the assertion, so one red line names all of them with
    file and marker instead of stopping at the first one: whoever rewrites this paragraph
    rewrites six places, and finding out about the fifth one run after run is the way the
    six drift apart in the first place.

    The section is flattened to single spaces before the search, because the READMEs wrap
    their lines and a marker split over a line break is present in the text a reader sees.
    The count of the languages comes first for the reason
    :func:`test_the_claim_gate_fires_on_a_constructed_line` states: a loop over an emptied
    list passes without looking at anything.
    """
    assert len(ENTERPRISE_MARKERS) == 3, ENTERPRISE_MARKERS

    missing = [
        f"{name}: {marker!r}"
        for name, markers, section in enterprise_places(manifest_root)
        for marker in markers
        if marker not in " ".join(section.split())
    ]

    assert missing == [], (
        "the Enterprise paragraph lost a statement at one of its six places: " + "; ".join(missing)
    )


def test_no_place_calls_the_audit_log_planned(manifest_root: etree._Element) -> None:
    """The sentence phase 18 made false must not come back, in any of the six places.

    Until this phase all six said that the audit log is planned as a commercial add-on.
    The log exists since phase 18, it is part of this app under the AGPL, and a text is
    the one part of a project that no build breaks when it goes stale. So the rule is
    written down instead of remembered: no line carries the word for the audit log and the
    word for planned at the same time. What is still planned keeps its own sentence, and
    that sentence does not name the record.

    Line by line and not per section, because the two statements live in two paragraphs on
    purpose: the day somebody joins them into one sentence is the day the old claim is back.
    """
    findings: list[str] = []
    for lang, readme, markers, planned_words in ENTERPRISE_MARKERS:
        audit_word = markers[0].casefold()
        description = _localised(manifest_root, "description", lang)
        assert description is not None
        manifest_name = f"appinfo/info.xml ({_lang_label(lang)})"
        sections = {
            manifest_name: enterprise_section(description, manifest_name),
            readme: enterprise_section((ROOT / readme).read_text("utf-8"), readme),
        }
        for name, section in sections.items():
            for number, line in enumerate(section.splitlines(), start=1):
                lowered = line.casefold()
                if audit_word in lowered and any(word in lowered for word in planned_words):
                    findings.append(f"{name}:{number}: {line.strip()}")

    assert findings == [], (
        "a place calls the audit log planned, which it has not been since phase 18: "
        + "; ".join(findings)
    )
