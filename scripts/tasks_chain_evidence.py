"""The measuring run behind plan 32-07: the tasks bundle over the whole ExApp chain.

``tests/integration/test_tasks_live.py`` calls the tool functions of the working tree in its
own process. This script asks the deployed app where nothing can be arranged::

    MCP client  ->  reverse proxy  ->  HaRP  ->  ExApp container  ->  Nextcloud

The client half is not written here. It is ``scripts/oauth_flow_check.py``, loaded by path the
way ``scripts/folder_chain_evidence.py`` loads it: the OAuth flow of the connector
(registration, PKCE, sign in, consent, code exchange) and the MCP client of the SDK over
Streamable HTTP with the bearer that flow returned.

Run it with the environment of the topology loaded::

    set -a && . ./.env.nc35 && set +a
    uv run --no-sync python scripts/tasks_chain_evidence.py connect --token-file <file>
    uv run --no-sync python scripts/tasks_chain_evidence.py tools --token-file <file>
    uv run --no-sync python scripts/tasks_chain_evidence.py call --token-file <file> \\
        --case anlegen --tool tasks_create --args '{"summary": "x"}' [--out <file>]
    uv run --no-sync python scripts/tasks_chain_evidence.py same <file a> <file b>

``call`` exits 0 when the tool refuses (a refusal is a measurement) and 1 only when the call
does not reach an answer at all. ``--out`` keeps the text of the answer as it came, so two
answers taken at two moments can be compared byte for byte by ``same``, which itself calls
nothing.

**What this script does not do.** It creates nothing but what the tools create, it deletes
nothing, and it never touches docker: setup, counter checks and removal are separate steps of
the run, so a counter check never shares a code path with the call it checks.

**What the protocol never carries.** A token, a client secret or a password. The connection
is written to ``--token-file``, which has to lie outside this repository, and every line this
script prints is built from the tool name, the arguments and the answer of the tool.
"""

import argparse
import asyncio
import importlib.util
import json
import os
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_TOOLS = frozenset({"tasks_search", "tasks_read", "tasks_create"})

#: The app families of the README. A tool whose prefix is none of them belongs to the cloud
#: wide search family (unified_search, search, fetch, prepare_context).
APP_FAMILIES = frozenset(
    {"files", "calendar", "tasks", "notes", "deck", "contacts", "tables", "talk", "mail"}
)
SEARCH_FAMILY = "search"

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


def _outside(raw: str, option: str) -> Path:
    """A file of the run, refused when it lies inside this repository."""
    path = Path(raw).resolve()
    if path.is_relative_to(REPO_ROOT):
        raise SystemExit(f"{option} has to lie outside the repository")
    return path


def _one_line(text: str) -> str:
    """The answer of the tool on one line: compact JSON when it is JSON, escaped otherwise."""
    try:
        decoded = json.loads(text)
    except ValueError:
        return text.replace("\r", "\\r").replace("\n", "\\n")
    return json.dumps(decoded, sort_keys=True, ensure_ascii=False)


def families_of(names: Iterable[str]) -> set[str]:
    """The families a tool list covers, counted the way the README counts them."""
    found: set[str] = set()
    for name in names:
        prefix = name.split("_", 1)[0]
        found.add(prefix if prefix in APP_FAMILIES else SEARCH_FAMILY)
    return found


def connect(args: argparse.Namespace) -> int:
    """Walk the OAuth flow as the account of the connection file and keep the result."""
    env = _environment()
    flow_check = _load_flow_check()
    connection = flow_check.connect(env["base"], env["nc"], env["user"], env["password"])
    target = _outside(args.token_file, "--token-file")
    target.write_text(
        json.dumps({"access_token": connection.access_token, "user": connection.user}),
        encoding="utf-8",
    )
    print(f"VERBINDUNG nutzer={connection.user} weg=oauth ergebnis=ok")
    return 0


def _connection(args: argparse.Namespace) -> tuple[str, str, str]:
    env = _environment()
    stored = json.loads(_outside(args.token_file, "--token-file").read_text(encoding="utf-8"))
    return env["base"], str(stored["access_token"]), str(stored["user"])


def tools(args: argparse.Namespace) -> int:
    """The tool list the deployed app answers with, and whether it knows the tasks bundle."""
    base, token, user = _connection(args)
    flow_check = _load_flow_check()
    names = asyncio.run(flow_check.list_tools(base, token))
    has_tasks = "ja" if set(names) >= TASK_TOOLS else "nein"
    print(f"WERKZEUGE anzahl={len(names)} tasks={has_tasks} familien={len(families_of(names))}")
    print(f"WERKZEUGE nutzer={user} namen={','.join(sorted(names))}")
    return 0


def call(args: argparse.Namespace) -> int:
    """One call of a tool over the chain. A refusal of the tool is a measurement, exit 0."""
    base, token, user = _connection(args)
    try:
        arguments = json.loads(args.args)
    except ValueError as error:
        raise SystemExit(f"--args is not JSON: {error}") from error
    if not isinstance(arguments, dict):
        raise SystemExit("--args has to be a JSON object")
    flow_check = _load_flow_check()
    sent = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    try:
        result: Any = asyncio.run(flow_check.tool_call(base, token, args.tool, arguments))
    except Exception as error:
        print(
            f"{args.label} {args.case} werkzeug={args.tool} nutzer={user} argumente={sent} "
            f"fehler=transport | {type(error).__name__}"
        )
        return 1
    texts = list(flow_check.texts_of(result))
    if args.out:
        _outside(args.out, "--out").write_bytes("\n".join(texts).encode("utf-8"))
    answer = " ".join(_one_line(text) for text in texts)
    failed = "ja" if result.is_error else "nein"
    print(
        f"{args.label} {args.case} werkzeug={args.tool} nutzer={user} argumente={sent} "
        f"fehler={failed} | {answer}"
    )
    return 0


def same(args: argparse.Namespace) -> int:
    """Compare two kept answers byte for byte; calls nothing."""
    first = Path(args.first).read_bytes()
    second = Path(args.second).read_bytes()
    equal = "ja" if first == second else "nein"
    print(f"GLEICH {equal} bytes={len(first)}/{len(second)}")
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
            command.add_argument("--tool", required=True, help="the name of the tool")
            command.add_argument("--args", required=True, help="the arguments as a JSON object")
            command.add_argument("--out", help="keep the text of the answer in this file")
            command.add_argument("--label", default="KETTE", help="the first word of the line")
    compare = commands.add_parser("same")
    compare.add_argument("first")
    compare.add_argument("second")
    compare.set_defaults(handler=same)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
