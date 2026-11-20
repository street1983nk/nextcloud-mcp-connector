"""The texts a model reads carry no assurances (issue #53, owner approval of 2026-11-20).

ChatGPT Business marked ``files_upload`` as a "Suspicious instruction" because its description
said it "never overwrites": a sentence that promises what a tool will not do reads to an
approval check like an attempt to lower the risk rating. So the descriptions, the parameter
descriptions and the error messages and hints state behaviour as a precondition or an error
in the present tense, and the promises live in the README and the admin docs.

What this gate reads:

- every description and every parameter description of ``tools/list``, in the standard
  registry and in the registry with every switch on (``optional_surface``), so the optional
  tools are seen as well;
- the error messages and hints of ``src/mcp_connector/tools`` and
  ``src/mcp_connector/nextcloud/clients`` (``laufzeit=ja`` in the owner line).

What it leaves out on purpose:

- the server instruction. The owner kept it as it is (``instruktion=A`` in the line
  ``FREIGABE tooltexte-53`` of ``.planning/phases/35-release-0-9-0-profile-fields/raw/
  35-freigaben.txt``): it is the wording of phase 34 (DOC-05), and whether the approval check
  of ChatGPT reads it at all is not documented.
- the output schema of ``search`` and ``fetch``: "``url`` is never empty" describes a field of
  the answer, not the behaviour of a tool, and the owner kept it (``searchhit=lassen``).

The counter proofs go through ``assurance_findings`` and ``runtime_texts``, the same functions
the real texts go through, with sentences written by hand rather than built from the patterns.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from optional_surface import OPTIONAL_TOOLS, annotations_of, switched_on_surface

import mcp_connector
from mcp_connector.errors import ToolError
from mcp_connector.server import mcp

#: The assurance patterns, by name, case-insensitive. "cannot", "read only" and "safe" are not
#: among them: they describe an error or the state of an object in many honest texts.
FORBIDDEN: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in {
        "never": r"\bnever\b",
        "no-verb": r"\bno (?:delete|move|share|overwrite)",
        "nothing-is": r"\bnothing (?:is|gets) (?:overwritten|deleted|changed)\b",
        "create-only": r"\bcreate-only\b",
        "guarantee": r"\bguarantee",
        "without-risk": r"\bwithout risk\b",
        "only-ever": r"\bonly ever\b",
        "reads-only": r"\breads only\b",
    }.items()
}

#: One sentence per pattern, written by hand, that only this pattern catches.
PLANTED: dict[str, str] = {
    "never": "This tool will never touch your data.",
    "no-verb": "There is no overwrite of an existing note.",
    "nothing-is": "Nothing gets deleted by this call.",
    "create-only": "A create-only path for new cards.",
    "guarantee": "We guarantee the upload stays intact.",
    "without-risk": "Call it without risk at any time.",
    "only-ever": "It only ever appends rows.",
    "reads-only": "This tool reads only mail headers.",
}

#: One sentence per pattern in the new style, close to the planted one, that nothing catches.
CLEAN: dict[str, str] = {
    "never": "The path must not exist yet; an existing path returns an error.",
    "no-verb": "An existing note with that title returns a conflict error.",
    "nothing-is": "A timeout does not mean nothing was written.",
    "create-only": "Create a new card in an existing stack.",
    "guarantee": "Whether an older version is kept depends on the storage backend.",
    "without-risk": "A name taken in the target list is refused.",
    "only-ever": "Add one new row to an existing table.",
    "reads-only": "List the messages of one mailbox.",
}

#: A tool that is not annotated read only names what it writes with one of these verbs.
WRITE_VERBS = re.compile(
    r"\b(?:create|add|send|upload|update|replace|complete|reopen|move|write|change)\b",
    re.IGNORECASE,
)

#: The source roots of the runtime texts.
SOURCE = Path(mcp_connector.__file__).resolve().parent
RUNTIME_ROOTS = ("tools", "nextcloud/clients")


def assurance_findings(texts: dict[str, str]) -> list[str]:
    """``<where>: <pattern name>`` for every assurance pattern in ``texts``."""
    return [
        f"{where}: {name}"
        for where, text in texts.items()
        for name, pattern in FORBIDDEN.items()
        if pattern.search(text)
    ]


def write_verb_findings(descriptions: dict[str, tuple[str, bool]]) -> list[str]:
    """Every tool that is not read only and names no write verb in its description.

    ``descriptions`` maps a tool name to its description and whether it is read only.
    """
    return [
        f"{name}: no write verb in the description"
        for name, (text, read_only) in sorted(descriptions.items())
        if not read_only and not WRITE_VERBS.search(text)
    ]


def _schema_texts(prefix: str, node: Any, out: dict[str, str]) -> None:
    """Every ``description`` inside one input schema, nested ones included."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                out[prefix] = value
            else:
                _schema_texts(f"{prefix}.{key}", value, out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _schema_texts(f"{prefix}[{index}]", value, out)


async def standard_texts() -> dict[str, str]:
    """Descriptions and parameter descriptions of the standard registry."""
    texts: dict[str, str] = {}
    async with Client(mcp, raise_exceptions=True) as client:
        for tool in (await client.list_tools()).tools:
            texts[f"{tool.name} description"] = tool.description or ""
            _schema_texts(f"{tool.name} input", tool.input_schema, texts)
    return texts


def switched_on_texts(surface: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Descriptions and parameter descriptions of one measured switched-on surface."""
    texts: dict[str, str] = {}
    for name, entry in surface.items():
        texts[f"{name} switched description"] = entry["description"] or ""
        _schema_texts(f"{name} switched input", entry["input_schema"], texts)
    return texts


def _error_names() -> frozenset[str]:
    """``ToolError`` and every subclass of it that is imported once the server is."""
    names: set[str] = set()
    todo: list[type] = [ToolError]
    while todo:
        cls = todo.pop()
        names.add(cls.__name__)
        todo.extend(cls.__subclasses__())
    return frozenset(names)


def _is_text_keyword(name: str | None) -> bool:
    return name is not None and (name in ("message", "hint") or name.endswith("_hint"))


def _assignments(scope: ast.AST) -> dict[str, list[ast.expr]]:
    """Name -> assigned values, for the plain ``name = value`` statements of one scope."""
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            found.setdefault(node.target.id, []).append(node.value)
    return found


def runtime_texts(source: str, origin: str, errors: frozenset[str]) -> dict[str, str]:
    """``<origin>:<line> -> text`` of every message and hint in one module.

    Collected: string constants (constant parts of f-strings included) in keyword arguments
    ``message``, ``hint`` and ``*_hint``, and in the arguments of the error classes in
    ``errors``. A plain name is followed to its assignments, in the enclosing function first
    and on module level after that, which reaches ``hint=_URI_HINT`` and ``hint=hint``.
    Docstrings and comments are not collected: they are no argument of such a call.
    """
    tree = ast.parse(source)
    module_level = _assignments(tree)
    texts: dict[str, str] = {}

    def collect(expr: ast.expr, local: dict[str, list[ast.expr]]) -> None:
        if isinstance(expr, ast.Name):
            for value in local.get(expr.id) or module_level.get(expr.id) or []:
                collect(value, {})
            return
        for node in ast.walk(expr):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                texts[f"{origin}:{node.lineno}"] = node.value

    scopes: list[tuple[ast.AST, dict[str, list[ast.expr]]]] = [(tree, {})]
    scopes += [
        (node, _assignments(node))
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for scope, local in scopes:
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if _is_text_keyword(keyword.arg):
                    collect(keyword.value, local)
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in errors:
                for argument in node.args:
                    collect(argument, local)
    return texts


def all_runtime_texts() -> dict[str, str]:
    """The runtime texts of every module under the runtime roots."""
    errors = _error_names()
    texts: dict[str, str] = {}
    for root in RUNTIME_ROOTS:
        for path in sorted((SOURCE / root).glob("*.py")):
            origin = path.relative_to(SOURCE).as_posix()
            texts.update(runtime_texts(path.read_text(encoding="utf-8"), origin, errors))
    return texts


# --- counter proofs ----------------------------------------------------------------------


def test_every_pattern_has_exactly_one_planted_sentence_and_one_clean_one() -> None:
    assert set(PLANTED) == set(FORBIDDEN)
    assert set(CLEAN) == set(FORBIDDEN)


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_a_planted_assurance_is_caught_by_its_own_pattern_only(name: str) -> None:
    assert assurance_findings({"planted": PLANTED[name]}) == [f"planted: {name}"]


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_a_sentence_in_the_new_style_is_not_reported(name: str) -> None:
    assert assurance_findings({"clean": CLEAN[name]}) == []


def test_the_old_files_upload_description_is_reported() -> None:
    old = "Create text/base64 or ChatGPT attachments; never overwrites."
    assert assurance_findings({"files_upload": old}) == ["files_upload: never"]


def test_a_writing_tool_without_a_write_verb_is_reported() -> None:
    planted = {
        "tables_create_row": ("List the rows of a table.", False),
        "tables_browse": ("List the rows of a table.", True),
        "talk_send": ("Send one new message into a conversation.", False),
    }
    assert write_verb_findings(planted) == ["tables_create_row: no write verb in the description"]


def test_a_planted_assurance_in_an_optional_tool_is_reported() -> None:
    surface = switched_on_surface()
    surface["files_update"]["description"] += " It never loses data."
    findings = assurance_findings(switched_on_texts(surface))
    assert "files_update switched description: never" in findings


def test_the_runtime_collector_reaches_hints_and_skips_docstrings() -> None:
    planted = '''
"""A module docstring that never counts."""
_HINT = "A module constant that never counts as safe."


def build():
    """A function docstring that never counts."""
    raise ConflictError(message="x", hint="Uploads never overwrite existing files.")


def chosen(chain):
    hint = "Call again; that is fine." if chain else "Nothing gets deleted by this call."
    return ToolError(message="y", hint=hint)


def constant():
    return ToolError("z", _HINT)
'''
    texts = runtime_texts(planted, "planted.py", frozenset({"ToolError", "ConflictError"}))
    findings = assurance_findings(texts)
    assert sorted(findings) == sorted(
        ["planted.py:3: never", "planted.py:8: never", "planted.py:12: nothing-is"]
    )
    assert not any("docstring" in text for text in texts.values())


# --- the real texts ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_standard_tool_texts_carry_no_assurance() -> None:
    assert assurance_findings(await standard_texts()) == []


def test_the_switched_on_tool_texts_carry_no_assurance() -> None:
    texts = switched_on_texts(switched_on_surface())
    seen = {where.split(" ", 1)[0] for where in texts if where.endswith(" switched description")}
    assert set(OPTIONAL_TOOLS) <= seen, "the gate must see the optional tools"
    assert assurance_findings(texts) == []


def test_every_writing_tool_names_what_it_writes() -> None:
    surface = switched_on_surface()
    descriptions = {}
    for name, entry in surface.items():
        annotations = annotations_of(entry)
        read_only = annotations is not None and annotations.read_only_hint is True
        descriptions[name] = (entry["description"] or "", read_only)
    assert any(not read_only for _, read_only in descriptions.values())
    assert write_verb_findings(descriptions) == []


def test_the_runtime_collector_reaches_the_known_places() -> None:
    texts = all_runtime_texts()
    origins = {where.rsplit(":", 1)[0] for where in texts}
    assert {
        "tools/files.py",
        "nextcloud/clients/dav.py",
        "nextcloud/clients/caldav.py",
        "nextcloud/clients/carddav.py",
        "nextcloud/clients/tasks.py",
        "nextcloud/clients/xml.py",
        "nextcloud/clients/mail.py",
    } <= origins
    values = list(texts.values())
    # hint=hint in tools/files.py, a local name, and hint=_URI_HINT, a module constant.
    assert any(text.startswith("Call again with the same path; ") for text in values)
    assert any(text.startswith("Use a calendar exactly as") for text in values)


def test_the_runtime_texts_carry_no_assurance() -> None:
    assert assurance_findings(all_runtime_texts()) == []
