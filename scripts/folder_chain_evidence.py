"""The measuring run behind plan 31-07: ``files_create_folder`` over the whole ExApp chain.

``tests/integration/test_files_create_folder_live.py`` calls the tool function of the working
tree in its own process. This script asks the same tool where nothing can be arranged::

    MCP client  ->  reverse proxy  ->  HaRP  ->  ExApp container  ->  Nextcloud

The client half is not written here. It is ``scripts/oauth_flow_check.py``, loaded by path the
way ``tests/integration/test_oauth_flow_exapp.py`` loads it: the OAuth flow of the connector
(registration, PKCE, sign in, consent, code exchange) and the MCP client of the SDK over
Streamable HTTP with the bearer that flow returned.

Run it with the environment of the topology loaded::

    set -a && . ./.env.nc35 && set +a
    uv run --no-sync python scripts/folder_chain_evidence.py connect --token-file <file>
    uv run --no-sync python scripts/folder_chain_evidence.py tools --token-file <file>
    uv run --no-sync python scripts/folder_chain_evidence.py call --token-file <file> \\
        --case frei --path kette31-x/frei

**What this script does not do.** It creates nothing but what the tool creates, it deletes
nothing, and it never touches docker: the setup, the counter checks in the file system of the
Nextcloud container and the removal are separate steps of the run, so a counter check never
shares a code path with the call it checks.

**What the protocol never carries.** A token, a client secret or a password. The connection
is written to ``--token-file``, which has to lie outside this repository, and every line this
script prints is built from the tool name, the arguments and the answer of the tool.

``--path`` is given without its leading slash and the script puts it back: Git Bash rewrites an
argument that looks like an absolute POSIX path when it starts a native process.
"""

import argparse
import asyncio
import importlib.util
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = "files_create_folder"

#: The four values of the connection file a run needs, with the variable each comes from.
REQUIRED = {
    "base": "NC_MCP_EXAPP_BASE",
    "nc": "NC_MCP_URL",
    "user": "NC_MCP_TEST_USER",
    "password": "NC_MCP_TEST_PASSWORD",
}


def _load_flow_check() -> ModuleType:
    """The client half of the flow, loaded from its own file instead of being repeated."""
    path = REPO_ROOT / "scripts" / "oauth_flow_check.py"
    spec = importlib.util.spec_from_file_location("oauth_flow_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{path} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _environment() -> dict[str, str]:
    values = {key: (os.environ.get(name) or "").strip() for key, name in REQUIRED.items()}
    missing = sorted(REQUIRED[key] for key, value in values.items() if not value)
    if missing:
        raise SystemExit(f"no ExApp topology configured (missing: {', '.join(missing)})")
    return values


def _token_file(raw: str) -> Path:
    """The file the connection lives in, refused when it lies inside this repository."""
    path = Path(raw).resolve()
    if path.is_relative_to(REPO_ROOT):
        raise SystemExit("--token-file has to lie outside the repository")
    return path


def _one_line(text: str) -> str:
    """The answer of the tool on one line: compact JSON when it is JSON, escaped otherwise."""
    try:
        decoded = json.loads(text)
    except ValueError:
        return text.replace("\r", "\\r").replace("\n", "\\n")
    return json.dumps(decoded, sort_keys=True, ensure_ascii=False)


def connect(args: argparse.Namespace) -> int:
    """Walk the OAuth flow as the account of the connection file and keep the result."""
    env = _environment()
    flow_check = _load_flow_check()
    connection = flow_check.connect(env["base"], env["nc"], env["user"], env["password"])
    target = _token_file(args.token_file)
    target.write_text(
        json.dumps({"access_token": connection.access_token, "user": connection.user}),
        encoding="utf-8",
    )
    print(f"VERBINDUNG nutzer={connection.user} weg=oauth ergebnis=ok")
    return 0


def _connection(args: argparse.Namespace) -> tuple[str, str, str]:
    env = _environment()
    stored = json.loads(_token_file(args.token_file).read_text(encoding="utf-8"))
    return env["base"], str(stored["access_token"]), str(stored["user"])


def tools(args: argparse.Namespace) -> int:
    """The tool list the deployed app answers with, and whether it knows the tool."""
    base, token, user = _connection(args)
    flow_check = _load_flow_check()
    names = asyncio.run(flow_check.list_tools(base, token))
    known = "ja" if TOOL in names else "nein"
    print(f"WERKZEUGE nutzer={user} anzahl={len(names)} {TOOL}={known}")
    print(f"WERKZEUGE namen={','.join(sorted(names))}")
    return 0


def call(args: argparse.Namespace) -> int:
    """One call of the tool over the chain. A refusal of the tool is a measurement, exit 0."""
    base, token, user = _connection(args)
    flow_check = _load_flow_check()
    arguments: dict[str, Any] = {"path": "/" + args.path}
    if args.parents:
        arguments["parents"] = True
    result = asyncio.run(flow_check.tool_call(base, token, TOOL, arguments))
    answer = " ".join(_one_line(text) for text in flow_check.texts_of(result))
    failed = "ja" if result.is_error else "nein"
    sent = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    print(f"{args.label} {args.case} nutzer={user} argumente={sent} fehler={failed} | {answer}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", maxsplit=1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("connect", connect), ("tools", tools), ("call", call)):
        command = commands.add_parser(name)
        command.add_argument("--token-file", required=True)
        command.set_defaults(handler=handler)
        if name == "call":
            command.add_argument("--case", required=True, help="the label of the case")
            command.add_argument("--path", required=True, help="without the leading slash")
            command.add_argument("--parents", action="store_true")
            command.add_argument("--label", default="KETTE", help="the first word of the line")
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
