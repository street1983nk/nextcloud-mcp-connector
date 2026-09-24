"""The repeatable measuring run behind ``docs/exchange-evidence.md`` (EXCH-07).

Two accounts, two tokens of a foreign issuer, and the one question the evidence document
exists for: can an identity that was born on the token exchange path reach the files of
another identity that was born the same way. The answer has to be measured against a
running Nextcloud, because the boundary is enforced by Nextcloud and not claimed by this
code, and it has to be measured *over the exchange path*, because a proof whose two
identities came from Login Flow v2 or from AppAPI proves only what ``docs/spike-dav.md``
has proven since 2026-08-15 (pitfall 9 of ``24-RESEARCH.md``).

Run it against the Nextcloud 35 topology of ``compose.nc35.yml``::

    docker compose --env-file .env.nc35 -f compose.nc35.yml up -d test-issuer
    uv run --no-sync python scripts/exchange_evidence.py --env-file .env.nc35

The run arms the deployed ExApp with a ``NC_MCP_EXCHANGE_*`` configuration, measures, and
puts the registration back to the one ``scripts/bootstrap_exapp.sh`` writes. The payload of
both registrations is read out of that script at run time and never copied into this file:
a second copy of thirteen routes would drift, and a drifted restore is a topology nobody
can trust again.

**What this run does not put on disk.** The signing key of the test issuer lives in memory
for the length of the run and is never written into the working tree. The tokens are minted
here, live five minutes and are never written down either. What travels into the container
is the public half (the key set) and the root certificate of the test issuer's own CA. A
``git status --short`` after a run shows the three files of the plan and nothing else.

**Why the test issuer is not a Keycloak.** The exchange path needs an HTTPS issuer and
fetches the key set on the origin of that issuer, so the run needs a TLS terminated key set
endpoint inside the compose network. That is all it needs: the tokens are signed here, so
nothing in the run asks the issuer for one. A full Keycloak would only matter for the
golden fixture, which is out of scope (D-v1.6-02).
"""

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator, Coroutine, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

#: The containers of the Nextcloud 35 topology this run measures against.
NC_CONTAINER = "nc35-nc"
EXAPP_CONTAINER = "nc_app_mcp_connector"
ISSUER_CONTAINER = "nc35-test-issuer"
TOPOLOGY_CONTAINERS = (
    NC_CONTAINER,
    EXAPP_CONTAINER,
    "nc35-harp",
    "nc35-caddy",
    ISSUER_CONTAINER,
)

#: The app id is frozen (``docs/app-id-freeze.md``), so every path built from it is a
#: constant here rather than an interpolation.
APP_ID = "mcp_connector"
DAEMON_NAME = "harp_proxy_docker"
APP_PORT = "23000"
BASE_URL = "http://127.0.0.1:8082"
EXAPP_BASE = f"{BASE_URL}/exapps/{APP_ID}"
MCP_URL = f"{EXAPP_BASE}/mcp"

#: The test issuer of ``compose.nc35.yml``. The realm segment is part of the issuer, the
#: way a Keycloak realm URL is, so the key set path below is the one Keycloak publishes.
ISSUER = "https://test-issuer/realms/evidence"
JWKS_PATH = "/realms/evidence/protocol/openid-connect/certs"
DISCOVERY_PATH = "/realms/evidence/.well-known/openid-configuration"
ISSUER_ROOT = "/srv"

#: The acting party of the measuring run, the one value ``NC_MCP_EXCHANGE_AZP`` allows.
ACTING_PARTY = "mcp-evidence-orchestrator"

#: Where the root certificate of the test issuer's own CA lives inside each container.
CADDY_ROOT_IN_ISSUER = "/data/caddy/pki/authorities/local/root.crt"
TRUST_BUNDLE = "/app/.venv/lib/python3.13/site-packages/certifi/cacert.pem"

#: How long a minted token lives. Well inside ``MAX_TOKEN_LIFETIME_SECONDS`` of
#: ``oauth/exchange.py``, and long enough for a whole run.
TOKEN_LIFETIME_SECONDS = 300

#: The line only one account's file carries, kept ASCII so a leak assertion is exact. The
#: same choice ``tests/integration/test_permission_fidelity_exapp.py`` makes.
CONFIDENTIAL_LINE = "Vertrauliche Notiz, nur fuer ein Konto."

TIMEOUT = httpx2.Timeout(30.0, read=300.0)


@dataclass(frozen=True, slots=True)
class Account:
    """One measured account: the Nextcloud user id, its token and the file it owns."""

    user: str
    token: str
    path: str
    marker: str


class RunFailed(RuntimeError):
    """A step did not answer the way a measuring run needs it to."""


def now_stamp() -> str:
    """The moment a block was measured, in the shape the evidence document carries."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def section(title: str) -> None:
    """One heading per measured block, so the raw output can be quoted by the block."""
    print(f"\n== {title} ==")


def run(argv: Sequence[str], *, stdin: str | None = None, check: bool = True) -> str:
    """One external command, no shell, fixed argument list, output as text."""
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and finished.returncode != 0:
        raise RunFailed(
            f"{' '.join(argv[:4])} exited {finished.returncode}: "
            f"{(finished.stderr or finished.stdout).strip()[:400]}"
        )
    return (finished.stdout or "") + (finished.stderr or "")


def docker(*argv: str, stdin: str | None = None, check: bool = True) -> str:
    """One docker call. ``docker`` is on PATH by contract, as in every script here."""
    return run(["docker", *argv], stdin=stdin, check=check)


def occ(*argv: str, check: bool = True) -> str:
    """One ``occ`` call inside the Nextcloud container of this topology."""
    return docker("exec", "-u", "www-data", NC_CONTAINER, "php", "occ", *argv, check=check).strip()


def read_env_file(path: Path) -> dict[str, str]:
    """The values ``scripts/bootstrap_exapp.sh`` wrote, as a mapping. Never printed."""
    if not path.is_file():
        raise RunFailed(f"{path} is not there; run scripts/bootstrap_exapp.sh --nc35 first")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip()
    return values


def bootstrap_payload(env: Mapping[str, str], script: Path, shell: str) -> dict[str, Any]:
    """The registration payload of ``scripts/bootstrap_exapp.sh``, read out of that script.

    The function that builds it is extracted from the shell source and evaluated, so this
    run registers exactly what the bootstrap registers. A copy of the thirteen routes in
    this file would be a second truth about the surface of this app, and the restore at the
    end of a run would put back something the bootstrap never wrote.

    ``shell`` is a parameter and not the bare name ``bash``, because on Windows that name
    resolves to the WSL launcher in ``System32`` before it resolves to the Git Bash this
    repository is developed in, and the launcher answers with an ``execvpe`` error that
    says nothing about the cause. Name the interpreter and the run says what it used.
    """
    source = script.read_text(encoding="utf-8")
    start = source.index("EXCLUDED_HEADERS=")
    end = source.index("\n}\n", start) + len("\n}\n")
    snippet = source[start:end]
    environment = {
        **os.environ,
        "APP_ID": APP_ID,
        "APP_NAME": "MCP Connector",
        "APP_VERSION": env["APP_VERSION"],
        "APP_SECRET": env["APP_SECRET"],
        "REGISTRY": "127.0.0.1:5000",
        "IMAGE_NAME": APP_ID,
        "PUBLIC_URL": EXAPP_BASE,
    }
    # The script travels through stdin and never as an argument, and that is a measured
    # correction rather than a preference: the well known routes of the payload carry four
    # backslashes each, and an MSYS shell on Windows re-parses the command line it is given
    # and eats one level of them. The heredoc then eats the second, and the payload reaches
    # AppAPI with the invalid JSON escape ``\.``. On stdin nothing re-parses anything.
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell string
        [shell, "-s", "--", DAEMON_NAME, APP_PORT],
        input=f'{snippet}\njson_info "$1" "$2"\n',
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if finished.returncode != 0:
        raise RunFailed(f"the bootstrap payload could not be built: {finished.stderr[:400]}")
    return json.loads(finished.stdout)


def with_exchange(payload: dict[str, Any], variables: Mapping[str, str]) -> dict[str, Any]:
    """The bootstrap payload plus the variables that arm this run, and nothing else."""
    armed = json.loads(json.dumps(payload))
    declared = armed["external-app"]["environment-variables"]
    for name, value in variables.items():
        declared[name] = {"name": name, "value": value}
    return armed


def register(payload: Mapping[str, Any]) -> None:
    """Unregister and register again, with the payload through stdin (WR-06).

    The payload carries the app secret, which is bearer equivalent, so it never travels as
    an argument of the docker client on the host. The same rule the bootstrap follows.
    """
    occ("app_api:app:unregister", APP_ID, check=False)
    snippet = (
        'JSON="$(cat)"; exec php occ app_api:app:register "$1" "$2" '
        '--json-info "$JSON" --force-scopes --wait-finish'
    )
    output = docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        NC_CONTAINER,
        "sh",
        "-c",
        snippet,
        "sh",
        APP_ID,
        DAEMON_NAME,
        stdin=json.dumps(payload, separators=(",", ":")),
    )
    print(output.strip()[-400:])
    print(occ("app_api:app:enable", APP_ID))
    print(occ("app_api:app:list"))


def issuer_material() -> tuple[str, str]:
    """A fresh RS256 key pair, published as a key set on the test issuer.

    Returns the private key in PEM form and the ``kid``. The private half never leaves this
    process: it is returned as text, used to sign, and dropped when the run ends.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    numbers = key.public_key().public_numbers()
    kid = f"evidence-{uuid.uuid4().hex[:8]}"
    key_set = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }
    discovery = {
        "issuer": ISSUER,
        "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    _publish(JWKS_PATH, key_set)
    _publish(DISCOVERY_PATH, discovery)
    print(f"key set published with kid {kid}")
    return private_pem, kid


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _publish(path: str, document: Mapping[str, Any]) -> None:
    """Write one static document into the test issuer, through the container's own shell."""
    target = f"{ISSUER_ROOT}{path}"
    parent = target.rsplit("/", 1)[0]
    docker("exec", ISSUER_CONTAINER, "mkdir", "-p", parent)
    docker(
        "exec",
        "-i",
        ISSUER_CONTAINER,
        "sh",
        "-c",
        f"cat > {target}",
        stdin=json.dumps(document),
    )


def trust_the_issuer() -> None:
    """Put the root of the test issuer's own CA where httpx looks for trust anchors.

    ``SSL_CERT_FILE`` is the documented route (assumption A6, measured in
    :func:`probe_the_issuer`), and this run takes it by naming the bundle that is already
    in the image and extending it. The reason is the one thing the assumption does not
    cover: httpx builds an SSL context for *every* client, including the ones this app
    builds on its own way to Nextcloud, and ``ssl.create_default_context`` raises
    ``FileNotFoundError`` for a file that is not there yet. A variable pointing at a file
    that only arrives after the container started would therefore turn the first outgoing
    call of the app into a crash, and the window between "container created by the deploy
    daemon" and "file copied in" is not ours to close.
    """
    root = docker("exec", ISSUER_CONTAINER, "cat", CADDY_ROOT_IN_ISSUER)
    docker(
        "exec",
        "-i",
        "-u",
        "0",
        EXAPP_CONTAINER,
        "sh",
        "-c",
        f"cat >> {TRUST_BUNDLE}",
        stdin=root,
    )
    print(f"the test issuer root is appended to {TRUST_BUNDLE}")


def probe_the_issuer() -> None:
    """Assumption A6, measured in the container instead of read in the source.

    One HTTPS GET on the key set path, from inside the ExApp container, with nothing but
    ``SSL_CERT_FILE`` pointing at the self signed root. A ``200`` here is the whole of the
    assumption; anything else means the run needs a real Keycloak after all.
    """
    root = docker("exec", ISSUER_CONTAINER, "cat", CADDY_ROOT_IN_ISSUER)
    docker(
        "exec",
        "-i",
        "-u",
        "0",
        EXAPP_CONTAINER,
        "sh",
        "-c",
        "cat > /tmp/evidence-issuer-ca.pem && chmod 0644 /tmp/evidence-issuer-ca.pem",
        stdin=root,
    )
    program = (
        "import httpx\n"
        f"r = httpx.get('{ISSUER}/protocol/openid-connect/certs')\n"
        "print(r.status_code, r.headers.get('content-type'), r.text.strip()[:60])\n"
    )
    print(
        docker(
            "exec",
            "-e",
            "SSL_CERT_FILE=/tmp/evidence-issuer-ca.pem",
            EXAPP_CONTAINER,
            "python",
            "-c",
            program,
        ).strip()
    )


def mint(private_pem: str, kid: str, subject: str, *, issuer: str = ISSUER) -> str:
    """One exchanged access token for ``subject``, in the shape Keycloak writes one.

    The account claim is ``sub``, which is the default of ``NC_MCP_EXCHANGE_ACCOUNT_CLAIM``
    and the profile ``account_id_v1``: the provider carries the canonical Nextcloud account
    id. The token lives five minutes and is never written to disk.
    """
    issued = int(time.time())
    claims = {
        "iss": issuer,
        "sub": subject,
        "aud": f"{EXAPP_BASE}/mcp",
        "azp": ACTING_PARTY,
        "typ": "Bearer",
        "iat": issued,
        "exp": issued + TOKEN_LIFETIME_SECONDS,
        "preferred_username": subject,
    }
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


@asynccontextmanager
async def session(headers: Sequence[tuple[str, str]]) -> AsyncIterator[Client]:
    """One MCP session over Streamable HTTP against the deployed ExApp.

    The headers travel as a sequence of pairs and not as a mapping, because one measurement
    needs two ``Authorization`` headers in one request and a mapping cannot carry them.
    """
    async with httpx2.AsyncClient(headers=headers, timeout=TIMEOUT) as http_client:
        transport = streamable_http_client(MCP_URL, http_client=http_client)
        async with Client(transport) as client:
            yield client


def bearer(token: str) -> list[tuple[str, str]]:
    return [("Authorization", f"Bearer {token}")]


def outcome(result: Any) -> str:
    """One line for one tool call: refused or answered, and the first line of the answer."""
    texts = [c.text for c in result.content if getattr(c, "text", None) is not None]
    first = texts[0].replace("\n", " ")[:160] if texts else ""
    return f"{'REFUSED' if result.is_error else 'ANSWERED'} | {first}"


async def call(client: Client, tool: str, arguments: Mapping[str, Any]) -> str:
    """One tool call, reported the way the evidence document quotes it."""
    result = await client.call_tool(tool, dict(arguments))
    line = f"{tool}({json.dumps(arguments, sort_keys=True)}) -> {outcome(result)}"
    print(line)
    return line


async def own_file(account: Account) -> None:
    """Measurement 1 and 3, one direction: the account creates and reads its own file."""
    async with session(bearer(account.token)) as client:
        await call(
            client,
            "files_upload",
            {"path": account.path, "content": f"# {account.marker}\n{CONFIDENTIAL_LINE}\n"},
        )
        await call(client, "files_read", {"path": account.path})


async def cross_read(reader: Account, owner: Account) -> None:
    """Measurement 2 and 3: three ways at the file of the other account, all refused.

    The path of the other account is known in both spellings a caller could try it in: the
    one it has inside its own home, and the one that names the other home explicitly. The
    search is the third way, because a tool that finds what it may not read would leak the
    existence of the file even while the read stays refused.
    """
    async with session(bearer(reader.token)) as client:
        await call(client, "files_read", {"path": owner.path})
        await call(client, "files_read", {"path": f"/../{owner.user}{owner.path}"})
        await call(client, "files_search", {"query": owner.marker})


async def raw_mcp(
    headers: Sequence[tuple[str, str]], tool: str, arguments: Mapping[str, Any]
) -> str:
    """One tool call as a bare HTTP request, so the status code of the answer is visible.

    The MCP client of the SDK negotiates before it calls, and a request the transport
    boundary turns away never reaches a tool: the client then raises about the handshake and
    the status code is lost. The stateless protocol era of 2026-07-28 needs no handshake, so
    one POST carries the whole call and the answer keeps its status.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": dict(arguments),
            # The envelope the 2026-07-28 era puts in place of the handshake. Without it the
            # server answers -32602 before it has looked at any credential, which measures
            # the request and not the boundary (measured on the first run of this script).
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    fixed = [
        ("Accept", "application/json, text/event-stream"),
        ("Content-Type", "application/json"),
        ("MCP-Protocol-Version", "2026-07-28"),
        # The era of 2026-07-28 announces the method in a header as well, and the server
        # refuses a body that says something else. Measured, not read: without it the answer
        # is -32020 and the request never reaches a credential check.
        ("mcp-method", "tools/call"),
        ("mcp-name", tool),
    ]
    async with httpx2.AsyncClient(timeout=TIMEOUT) as http_client:
        response = await http_client.post(
            MCP_URL, headers=[*headers, *fixed], content=json.dumps(body)
        )
    answer = response.text.replace("\n", " ").strip()[:220]
    line = f"HTTP {response.status_code} | {answer}"
    print(line)
    return line


async def confused_deputy(holder: Account, other: Account, basic: str) -> None:
    """Measurement 4: a second, fully valid credential next to the exchange token.

    The oracle is one read of the file ``holder`` owns and ``other`` may not see. Answered
    means the request ran as ``holder``, refused means it ran as ``other``, and the two
    controls establish both readings before the case is asked: a refusal alone would say
    nothing about which of the two credentials decided.
    """
    probe = {"path": holder.path}
    print(f"control, the Basic credential of {holder.user} alone:")
    await raw_mcp([("Authorization", basic)], "files_read", probe)
    print(f"control, the exchange token of {other.user} alone:")
    await raw_mcp(bearer(other.token), "files_read", probe)
    print(f"the case, Basic of {holder.user} first and the exchange token of {other.user} second:")
    await raw_mcp([("Authorization", basic), *bearer(other.token)], "files_read", probe)
    print(f"the case, the exchange token of {other.user} first and Basic of {holder.user} second:")
    await raw_mcp([*bearer(other.token), ("Authorization", basic)], "files_read", probe)
    # Which of the two paths wrote the row that case produced. An AppAPI resolved identity
    # leaves no client id and no acting party; an exchanged identity leaves both. This is
    # the line that says which credential decided, rather than letting the reader guess.
    print("the audit row that case wrote:")
    print(occ("mcp_connector:audit:read", f"--user={holder.user}", "--limit=1"))
    broken = basic_header(holder.user, "not-the-app-password-of-this-account")
    print(f"the same case with a Basic credential {holder.user} never had:")
    await raw_mcp([*bearer(other.token), ("Authorization", broken)], "files_read", probe)


async def mixed_run(account: Account, own_token: str) -> None:
    """The mixed run of success criterion 1: one own token, one exchanged, one principal."""
    async with session(bearer(own_token)) as client:
        await call(client, "files_read", {"path": account.path})
    async with session(bearer(account.token)) as client:
        await call(client, "files_read", {"path": account.path})


async def refused_attempt(private_pem: str, kid: str) -> None:
    """One deliberately refused attempt: a token of an issuer this instance never named."""
    stranger = mint(private_pem, kid, "alice", issuer="https://other-realm.invalid/realms/x")
    async with httpx2.AsyncClient(timeout=TIMEOUT) as http_client:
        response = await http_client.post(
            MCP_URL,
            headers={
                "Authorization": f"Bearer {stranger}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    print(f"POST /mcp with a token of a foreign issuer -> HTTP {response.status_code}")


def basic_header(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def access_lines(since: str, needles: Iterable[str]) -> None:
    """The Apache access log of the Nextcloud container, filtered to the measured paths.

    The status code of the answer Nextcloud gave lives here and nowhere else in this
    topology: the tool answer says refused, and this line says with which code.
    """
    wanted = tuple(needles)
    for line in docker("logs", "--since", since, NC_CONTAINER).splitlines():
        if any(needle in line for needle in wanted):
            print(line.strip())


def impersonation_lines(needles: Iterable[str]) -> None:
    """The Nextcloud side proof: one JSON line per request with the resolved user."""
    wanted = tuple(needles)
    log = docker(
        "exec",
        NC_CONTAINER,
        "tail",
        "-n",
        "400",
        "/var/www/html/data/exapp_impersonation.log",
        check=False,
    )
    for line in log.splitlines():
        if any(needle in line for needle in wanted):
            print(line.strip())


def audit_blocks(principal: str) -> None:
    """The four raw outputs the audit half of the evidence document quotes.

    The read of the account chain is bounded to the two newest entries, which are the two
    calls of the mixed run: the whole chain of a test instance that has been running for
    days is no evidence, it is a haystack.
    """
    section("occ mcp_connector:audit:verify --json")
    print(occ("mcp_connector:audit:verify", "--json"))
    section(f"occ mcp_connector:audit:read --user={principal} --limit=2")
    print(occ("mcp_connector:audit:read", f"--user={principal}", "--limit=2"))
    section(f"occ mcp_connector:audit:read --user={principal} --limit=2 --json")
    print(occ("mcp_connector:audit:read", f"--user={principal}", "--limit=2", "--json"))
    section("occ mcp_connector:audit:read --user=refusals")
    print(occ("mcp_connector:audit:read", "--user=refusals"))


def topology() -> None:
    """What this run measured against, named container by container."""
    section(f"topology, {now_stamp()}")
    print(
        docker(
            "ps",
            "--format",
            "{{.Names}}  {{.Image}}  {{.Status}}",
            *[arg for name in TOPOLOGY_CONTAINERS for arg in ("--filter", f"name=^{name}$")],
        ).strip()
    )
    print(occ("app_api:app:list"))
    print(
        docker("exec", EXAPP_CONTAINER, "printenv", "AA_VERSION", check=False).strip()
        or "AA_VERSION: unset"
    )


async def measure(
    accounts: tuple[Account, Account],
    env: Mapping[str, str],
    keys: tuple[str, str],
) -> None:
    """The four measurements and the refused attempt, in the order of the document.

    Every block stands on its own: a block that ends in an exception is reported as one and
    the run walks on. A measuring run that stops at the first surprise leaves the topology
    armed and the other three measurements unmade, which is the worse of the two failures.
    """
    alice, bob = accounts
    private_pem, kid = keys

    section("measurement 1: each account creates and reads its own file")
    await guarded(own_file(alice))
    await guarded(own_file(bob))

    section("measurement 2: alice's token on the known path of bob's file")
    await guarded(cross_read(alice, bob))

    section("measurement 3: bob's token on the known path of alice's file")
    await guarded(cross_read(bob, alice))

    section("measurement 4: a valid Basic credential of alice next to bob's exchange token")
    await guarded(
        confused_deputy(alice, bob, basic_header(alice.user, env["NC_MCP_TEST_APP_PASSWORD"]))
    )

    section("the refused attempt: a token of an issuer this instance never named")
    await guarded(refused_attempt(private_pem, kid))


async def guarded(work: Coroutine[Any, Any, None]) -> None:
    """One block, and its failure reported as a measured outcome instead of as an abort."""
    try:
        await work
    except Exception as failure:
        print(f"BLOCK FAILED | {type(failure).__name__}: {str(failure)[:200]}")


async def mixed(account: Account, own_token: str) -> None:
    section("the mixed run: one own token and one exchanged token, same principal")
    await guarded(mixed_run(account, own_token))


def own_access_token(env: Mapping[str, str]) -> str:
    """One access token this server issued itself, for the mixed run.

    The whole OAuth flow is walked by ``scripts/oauth_flow_check.py``; it is imported and
    not repeated, because a second sign in automation in this repository would be a second
    truth about a flow that is measured every release.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from oauth_flow_check import connect

    connection = connect(
        EXAPP_BASE,
        BASE_URL,
        env["NC_MCP_TEST_USER"],
        env["NC_MCP_TEST_PASSWORD"],
        name="exchange evidence",
    )
    return connection.access_token


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.nc35", help="the file the bootstrap wrote")
    parser.add_argument(
        "--bootstrap",
        default="scripts/bootstrap_exapp.sh",
        help="the script the registration payload is read out of",
    )
    parser.add_argument(
        "--shell",
        default="bash",
        help="the shell the registration payload is built with (Git Bash on Windows)",
    )
    parser.add_argument(
        "--keep-armed",
        action="store_true",
        help="leave the exchange configuration in place (for a second look, never for a rest)",
    )
    options = parser.parse_args(argv)

    env = read_env_file(Path(options.env_file))
    payload = bootstrap_payload(env, Path(options.bootstrap), options.shell)

    topology()

    section("the test issuer")
    private_pem, kid = issuer_material()

    section("arming the exchange path on the deployed ExApp")
    armed = with_exchange(
        payload,
        {
            "NC_MCP_EXCHANGE_ENABLED": "yes",
            "NC_MCP_EXCHANGE_ISSUER": ISSUER,
            "NC_MCP_EXCHANGE_AZP": ACTING_PARTY,
            "NC_MCP_AUDIT_LOG": "yes",
        },
    )
    print(
        "\n".join(
            f"{name}={entry['value']}"
            for name, entry in sorted(armed["external-app"]["environment-variables"].items())
        )
    )
    # The registration that arms the path, and from here on every way out of this function
    # runs through the ``finally`` below (WR-24-06). Everything between the two used to stand
    # outside it: probing the issuer, trusting it, and two ``mint`` calls that read a key of
    # the environment file. A missing container, a failing ``occ`` or a missing
    # ``NC_MCP_TEST_USER2`` left the development instance armed against a test issuer whose
    # private key died with the aborted process, which is the state ``--keep-armed`` marks as
    # the exception, reached without anybody asking for it.
    register(armed)
    try:
        section("assumption A6: the key set over HTTPS, from inside the ExApp container")
        probe_the_issuer()
        trust_the_issuer()

        marker = uuid.uuid4().hex[:10]
        alice = Account(
            user=env["NC_MCP_TEST_USER"],
            token=mint(private_pem, kid, env["NC_MCP_TEST_USER"]),
            path=f"/exchange-alice-{marker}.md",
            marker=f"exchange-alice-{marker}",
        )
        bob = Account(
            user=env["NC_MCP_TEST_USER2"],
            token=mint(private_pem, kid, env["NC_MCP_TEST_USER2"]),
            path=f"/exchange-bob-{marker}.md",
            marker=f"exchange-bob-{marker}",
        )

        started = now_stamp()
        asyncio.run(measure((alice, bob), env, (private_pem, kid)))

        section("Nextcloud access log, the status code behind every answer")
        access_lines(started, (alice.marker, bob.marker))

        section("Nextcloud side impersonation log, the resolved user per request")
        impersonation_lines((alice.marker, bob.marker))

        asyncio.run(mixed(alice, own_access_token(env)))
        audit_blocks(alice.user)
    finally:
        if not options.keep_armed:
            section("restoring the bootstrap registration")
            register(payload)
            print(occ("mcp_connector:exchange:check", "--token=probe", check=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
