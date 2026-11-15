"""The write promise of the three READMEs and of the server instruction, held against the registry.

DOC-05 (phase 34): every tool that changes something existing when all switches are on is
named in the "cannot do" section of each README together with its switch, the delete limit
names tasks, and every point that denies moving names the one exception ``tasks_move``. The
server instruction says that tasks are never deleted. The set of modifying tools comes from
the annotations of a fresh registry, not from a list in another test module, so a new
modifying tool without documentation turns this module red. The README lines this covers are
the MESS-05 inventory lines of plan 34-01 (raw/33-01-inventar.txt, plan=34).

The counter checks run the same check functions over a fixed old wording, never over the
wording the READMEs use now.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from lxml import etree

from mcp_connector.nextcloud.clients.xml import hardened_parser

ROOT = Path(__file__).resolve().parents[2]

SWITCH_BY_PREFIX = {
    "files_": "NC_MCP_FILES_UPDATE",
    "tasks_": "NC_MCP_TASKS_UPDATE",
}
ALL_SWITCHES = ("NC_MCP_FILES_UPDATE", "NC_MCP_TASKS_UPDATE")

#: file, heading of the "cannot do" section, start of the delete point, word for tasks,
#: word that marks a point denying moving.
READMES = [
    ("README.md", "## What this server cannot do", "No deleting", "tasks", "moving"),
    ("README.de.md", "## Was dieser Server nicht kann", "Kein Löschen", "Aufgaben", "Verschieben"),
    (
        "README.fr.md",
        "## Ce que ce serveur ne peut pas faire",
        "Aucune suppression",
        "tâches",
        "déplacement",
    ),
]

README_IDS = [entry[0] for entry in READMES]

_PRINT_MODIFYING = (
    "import json; from mcp_connector.server import mcp; "
    "print(json.dumps(sorted(t.name for t in mcp._tool_manager.list_tools() "
    "if t.annotations is not None and t.annotations.read_only_hint is False "
    "and t.annotations.destructive_hint is True)))"
)
_PRINT_INSTRUCTIONS = (
    "import json; from mcp_connector.server import mcp; print(json.dumps(mcp.instructions))"
)


def _fresh(code: str, switches: dict[str, str]) -> object:
    """Run ``code`` in a fresh interpreter with exactly these switches; the last JSON line."""
    env = os.environ.copy()
    for key in (*ALL_SWITCHES, "NC_MCP_DISABLED_TOOLS"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env.update(switches)
    done = subprocess.run(  # noqa: S603 - the interpreter of this test run, a fixed snippet
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def section(text: str, heading: str) -> str:
    """The text from ``heading`` up to the next ``## `` heading."""
    lines = text.splitlines()
    start = lines.index(heading)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def points(text: str) -> list[str]:
    """The list points of ``text``, each joined with its indented continuation lines."""
    found: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("- "):
            if current is not None:
                found.append(" ".join(current))
            current = [line[2:].strip()]
        elif current is not None and line.startswith("  ") and line.strip():
            current.append(line.strip())
        else:
            if current is not None:
                found.append(" ".join(current))
            current = None
    if current is not None:
        found.append(" ".join(current))
    return found


def switch_of(tool: str) -> str:
    for prefix, switch in SWITCH_BY_PREFIX.items():
        if tool.startswith(prefix):
            return switch
    raise AssertionError(f"no switch known for the modifying tool {tool}")


def missing_tools(text: str, tools: list[str]) -> list[str]:
    """Tools not named in backticks in a point that also names their switch."""
    problems = []
    for tool in tools:
        switch = switch_of(tool)
        if not any(f"`{tool}`" in point and switch in point for point in points(text)):
            problems.append(f"{tool} ({switch})")
    return problems


def delete_point_problems(text: str, start: str, tasks_word: str) -> list[str]:
    """The delete point is missing or does not name tasks."""
    matching = [point for point in points(text) if point.startswith(start)]
    if not matching:
        return [f"no point starts with {start!r}"]
    return [point for point in matching if tasks_word not in point]


def move_point_problems(text: str, word: str) -> list[str]:
    """Points that deny moving (the Mail point aside) without naming ``tasks_move``."""
    return [
        point
        for point in points(text)
        if word in point and "Mail" not in point and "`tasks_move`" not in point
    ]


@pytest.fixture(scope="module")
def modifying_tools() -> list[str]:
    found = _fresh(_PRINT_MODIFYING, {"NC_MCP_FILES_UPDATE": "on", "NC_MCP_TASKS_UPDATE": "on"})
    assert isinstance(found, list)
    return [str(name) for name in found]


def test_the_registry_names_exactly_the_four_modifying_tools(modifying_tools: list[str]) -> None:
    assert modifying_tools, "positive control: the registry must report modifying tools"
    assert "files_update" in modifying_tools
    assert set(modifying_tools) == {"files_update", "tasks_complete", "tasks_update", "tasks_move"}


@pytest.mark.parametrize(
    ("name", "heading", "start", "tasks_word", "move_word"), READMES, ids=README_IDS
)
def test_the_cannot_do_section_names_every_modifying_tool_with_its_switch(
    modifying_tools: list[str], name: str, heading: str, start: str, tasks_word: str, move_word: str
) -> None:
    text = section((ROOT / name).read_text(encoding="utf-8"), heading)
    assert missing_tools(text, modifying_tools) == []


@pytest.mark.parametrize(
    ("name", "heading", "start", "tasks_word", "move_word"), READMES, ids=README_IDS
)
def test_the_delete_limit_names_tasks(
    name: str, heading: str, start: str, tasks_word: str, move_word: str
) -> None:
    text = section((ROOT / name).read_text(encoding="utf-8"), heading)
    assert delete_point_problems(text, start, tasks_word) == []


@pytest.mark.parametrize(
    ("name", "heading", "start", "tasks_word", "move_word"), READMES, ids=README_IDS
)
def test_every_point_denying_moving_names_the_tasks_move_exception(
    name: str, heading: str, start: str, tasks_word: str, move_word: str
) -> None:
    text = section((ROOT / name).read_text(encoding="utf-8"), heading)
    assert any(move_word in point and "Mail" not in point for point in points(text)), (
        "positive control: the section must have a point that denies moving"
    )
    assert move_point_problems(text, move_word) == []


def test_the_instruction_says_tasks_are_never_deleted() -> None:
    off = _fresh(_PRINT_INSTRUCTIONS, {})
    assert isinstance(off, str)
    assert "Tasks are never deleted." in off
    on = _fresh(_PRINT_INSTRUCTIONS, {"NC_MCP_TASKS_UPDATE": "on"})
    assert isinstance(on, str)
    assert "Tasks are never deleted." in on
    assert "only with the ETag from tasks_read" in on


# Counter checks over a fixed old wording (the README.md section as it stood before phase 33).
OLD_SECTION = """## What this server cannot do

- No deleting: no tool issues a DELETE against files, events, notes, cards or contacts
- No unconditional overwriting: `files_upload` refuses existing paths. If the admin enables
  `NC_MCP_FILES_UPDATE`, `files_update` can replace an existing UTF-8 text file only when its
  ETag matches the value read earlier; stale or deleted files are rejected. Version history
  depends on the Nextcloud storage backend.
- No user-visible moving or renaming, no share changes and no permission changes; binary
  uploads use Nextcloud's private chunk assembly and still refuse an existing destination
- Mail is strictly read only: no sending, no draft, no move, no flag, no delete, and no
  attachment download
"""


def test_counter_check_a_move_point_without_tasks_move_is_reported() -> None:
    problems = move_point_problems(OLD_SECTION, "moving")
    assert len(problems) == 1
    assert problems[0].startswith("No user-visible moving or renaming")


def test_counter_check_a_delete_point_without_tasks_is_reported() -> None:
    problems = delete_point_problems(OLD_SECTION, "No deleting", "tasks")
    assert problems == [
        "No deleting: no tool issues a DELETE against files, events, notes, cards or contacts"
    ]


def test_counter_check_a_section_without_the_task_tools_is_reported() -> None:
    problems = missing_tools(OLD_SECTION, ["files_update", "tasks_update"])
    assert problems == ["tasks_update (NC_MCP_TASKS_UPDATE)"]


def test_counter_check_an_unknown_modifying_tool_has_no_switch() -> None:
    with pytest.raises(AssertionError):
        switch_of("contacts_update")


# The store descriptions of appinfo/info.xml (EXAPP-13, plan 34-05): the delete limit names
# tasks, and a point that denies moving names the task as its one exception. Matched case
# insensitively, because German writes "Löschen" as a noun at the start of a clause.

#: lang attribute, word for task, stem for deleting, pattern for a point about moving.
STORE_LANGS = [
    (None, "task", "delet", re.compile(r"\bmov(?:e|es|ed|ing)\b")),
    ("de", "aufgabe", "lösch", re.compile(r"verschieb")),
    ("fr", "tâche", "suppr", re.compile(r"déplac")),
]
STORE_IDS = ["en", "de", "fr"]


def store_description(lang: str | None) -> str:
    root = etree.fromstring((ROOT / "appinfo" / "info.xml").read_bytes(), hardened_parser())
    found = [
        child.text or ""
        for child in root
        if child.tag == "description" and child.get("lang") == lang
    ]
    assert len(found) == 1, f"expected one store description for {lang or 'en'}"
    return found[0]


def store_delete_problems(text: str, task_word: str, delete_stem: str) -> list[str]:
    """No point names deleting together with tasks."""
    if any(task_word in p.casefold() and delete_stem in p.casefold() for p in points(text)):
        return []
    return [f"no point names {delete_stem!r} together with {task_word!r}"]


def store_move_problems(text: str, task_word: str, move: re.Pattern[str]) -> list[str]:
    """Points that speak about moving without naming the task as the exception."""
    return [p for p in points(text) if move.search(p.casefold()) and task_word not in p.casefold()]


@pytest.mark.parametrize(("lang", "task_word", "delete_stem", "move"), STORE_LANGS, ids=STORE_IDS)
def test_the_store_description_names_the_task_delete_limit(
    lang: str | None, task_word: str, delete_stem: str, move: re.Pattern[str]
) -> None:
    assert store_delete_problems(store_description(lang), task_word, delete_stem) == []


@pytest.mark.parametrize(("lang", "task_word", "delete_stem", "move"), STORE_LANGS, ids=STORE_IDS)
def test_every_store_point_about_moving_names_the_task_exception(
    lang: str | None, task_word: str, delete_stem: str, move: re.Pattern[str]
) -> None:
    text = store_description(lang)
    assert any(move.search(p.casefold()) for p in points(text)), (
        "positive control: the description must have a point about moving"
    )
    assert store_move_problems(text, task_word, move) == []


OLD_STORE_POINT = (
    "- Nothing destructive: no delete, no move, no share; nothing in the background, no telemetry\n"
)


def test_counter_check_the_old_store_point_misses_the_task_delete_limit() -> None:
    assert store_delete_problems(OLD_STORE_POINT, "task", "delet") != []


def test_counter_check_the_old_store_point_denies_moving_without_the_task() -> None:
    problems = store_move_problems(OLD_STORE_POINT, "task", STORE_LANGS[0][3])
    assert len(problems) == 1
    assert problems[0].startswith("Nothing destructive")
