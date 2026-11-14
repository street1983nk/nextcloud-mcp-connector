"""The security pages held against the task family of 0.8.0 (DOC-04, DOC-05, plan 34-03).

Phase 33 added three tools that change an existing task (``tasks_complete``,
``tasks_update``, ``tasks_move``) behind the switch ``NC_MCP_TASKS_UPDATE``, off by default.
Before 0.8.0 the threat model, the three hardening guides and the privacy page said that no
tool moves anything, and none of them named text from shared task lists as a way in for a
prompt injection. This module holds what can be held mechanically:

*   **The names.** The threat model, the three hardening guides and the privacy page name the
    switch and ``tasks_move``; the threat model names all three tools and links the live
    findings in ``tasks-evidence.md``.
*   **No blanket denial of moving.** A paragraph or list point that says no tool moves
    anything also names ``tasks_move``, in every language, so the one exception cannot drop
    out of a sentence again.
*   **The way in.** The prompt injection section of the threat model has a paragraph about
    shared task lists, and the threat model keeps deleting a task as a limit.

The counter checks run the same check functions over the fixed wording these pages carried
before 0.8.0, never over the wording they carry now.
"""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

THREAT_MODEL = DOCS / "threat-model.md"
PRIVACY = DOCS / "privacy.md"
HARDENING = {
    "en": DOCS / "hardening.md",
    "de": DOCS / "hardening.de.md",
    "fr": DOCS / "hardening.fr.md",
}

SWITCH = "NC_MCP_TASKS_UPDATE"
MOVE_TOOL = "tasks_move"
MODIFYING_TASK_TOOLS = ("tasks_complete", "tasks_update", MOVE_TOOL)
EVIDENCE = "tasks-evidence.md"

#: The word for a task each hardening guide has to use.
TASK_WORD = {"en": "task", "de": "Aufgabe", "fr": "tâche"}

#: How each language denies moving across the board. A paragraph that matches has to name
#: ``tasks_move`` as well.
DENIES_MOVING = {
    "en": re.compile(r"no tool deletes,? moves", re.IGNORECASE),
    "de": re.compile(r"kein Werkzeug löscht\b.*\bverschiebt", re.IGNORECASE),
    "fr": re.compile(r"aucun outil ne supprime\b.*\bne déplace", re.IGNORECASE),
}

#: The pages and the language their denial is written in.
DENIAL_PAGES = [
    ("threat-model.md", THREAT_MODEL, "en"),
    ("privacy.md", PRIVACY, "en"),
    ("hardening.md", HARDENING["en"], "en"),
    ("hardening.de.md", HARDENING["de"], "de"),
    ("hardening.fr.md", HARDENING["fr"], "fr"),
]

#: The wording of threat-model.md before 0.8.0, the counter check of the paragraph check.
OLD_THREAT_MODEL_POINT = (
    "- No tool deletes, moves, renames, re-shares or changes permissions.\n"
    "  `files_upload` remains create-only. When `NC_MCP_FILES_UPDATE` is\n"
    "  enabled, `files_update` can replace existing UTF-8 text files only\n"
    "  with a matching ETag. Contract tests guard conditional file writes,\n"
    "  and `tests/contract/test_tool_classes.py` keeps every tool classified.\n"
)

#: The wording of hardening.de.md and hardening.fr.md before 0.8.0.
OLD_GERMAN_POINT = (
    "- kein Werkzeug löscht, überschreibt, verschiebt, benennt um oder ändert\n"
    "  Freigaben oder Rechte; Schreiben ist nur Anlegen, und ein Contract-Test\n"
    "  fällt beim ersten destruktiven Aufruf durch,\n"
)
OLD_FRENCH_POINT = (
    "- aucun outil ne supprime, n'écrase, ne déplace, ne renomme ni ne modifie\n"
    "  des partages ou des droits ; l'écriture est création seule, et un test de\n"
    "  contrat échoue au premier appel destructif,\n"
)

#: The prompt injection section of the threat model before 0.8.0.
OLD_INJECTION_SECTION = (
    "### Prompt injection, the one that spans all of the above\n\n"
    "A1 through A4 meet here: untrusted content carries an instruction, the\n"
    "model follows it, and the question is only what the instruction can reach.\n"
)

INJECTION_HEADING = "### Prompt injection"
ITEM_START = re.compile(r"^(?:[-*]|\d+\.) ", re.MULTILINE)


def read(path: Path) -> str:
    """A page, read the way every gate of this repository reads it."""
    return path.read_text(encoding="utf-8")


def paragraphs(text: str) -> list[str]:
    """Blocks between empty lines, each list point a block of its own, blanks folded."""
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        starts = [match.start() for match in ITEM_START.finditer(block)]
        if not starts or starts[0] != 0:
            starts = [0, *starts]
        bounds = [*starts, len(block)]
        for begin, end in pairwise(bounds):
            piece = " ".join(block[begin:end].split())
            if piece:
                blocks.append(piece)
    return blocks


def blanket_denials(text: str, lang: str) -> list[str]:
    """Every paragraph that denies moving across the board without naming ``tasks_move``."""
    pattern = DENIES_MOVING[lang]
    return [block for block in paragraphs(text) if pattern.search(block) and MOVE_TOOL not in block]


def section(text: str, heading: str) -> str:
    """From a heading that starts with ``heading`` to the next heading of any level."""
    start = text.index(heading)
    following = re.search(r"^#{1,6} ", text[start + len(heading) :], re.MULTILINE)
    end = start + len(heading) + following.start() if following else len(text)
    return text[start:end]


def shared_task_paragraphs(text: str) -> list[str]:
    """The paragraphs of a section that speak about shared task lists."""
    return [
        block
        for block in paragraphs(text)
        if "shared" in block.casefold() and "task" in block.casefold()
    ]


# --- the threat model ----------------------------------------------------------------------


@pytest.mark.parametrize("name", [*MODIFYING_TASK_TOOLS, SWITCH, EVIDENCE])
def test_the_threat_model_names_the_task_family(name: str) -> None:
    """DOC-04: the three tools, their switch and the live findings stand in the threat model."""
    assert name in read(THREAT_MODEL), f"threat-model.md does not name {name}"


def test_the_threat_model_names_shared_task_lists_as_a_way_in() -> None:
    """DOC-04: text from task lists other accounts share reaches the model."""
    found = shared_task_paragraphs(section(read(THREAT_MODEL), INJECTION_HEADING))

    assert found, "the prompt injection section says nothing about shared task lists"


def test_the_threat_model_keeps_deleting_a_task_as_a_limit() -> None:
    """E13: deleting a task is not offered, and the threat model says so."""
    found = [
        block
        for block in paragraphs(read(THREAT_MODEL))
        if "delete" in block.casefold() and "task" in block.casefold()
    ]

    assert found, "threat-model.md does not say that no task is deleted"


def test_the_shared_list_check_can_go_red() -> None:
    """The counter check: the injection section before 0.8.0 has no such paragraph."""
    assert shared_task_paragraphs(section(OLD_INJECTION_SECTION, INJECTION_HEADING)) == []


# --- no blanket denial of moving -------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "path", "lang"), DENIAL_PAGES, ids=[entry[0] for entry in DENIAL_PAGES]
)
def test_no_paragraph_denies_moving_without_the_task_exception(
    name: str, path: Path, lang: str
) -> None:
    """DOC-05: "no tool moves" is false since tasks_move, unless the sentence names it."""
    found = blanket_denials(read(path), lang)

    assert found == [], f"{name} denies moving without naming {MOVE_TOOL}: {found}"


@pytest.mark.parametrize(
    ("old", "lang"),
    [(OLD_THREAT_MODEL_POINT, "en"), (OLD_GERMAN_POINT, "de"), (OLD_FRENCH_POINT, "fr")],
    ids=["en", "de", "fr"],
)
def test_the_denial_check_can_go_red(old: str, lang: str) -> None:
    """The counter check: the fixed wording before 0.8.0 is reported, one point per language."""
    assert len(blanket_denials(old, lang)) == 1


def test_the_denial_check_keeps_list_points_apart() -> None:
    """A tasks_move in the next list point does not excuse a blanket denial in this one."""
    planted = OLD_THREAT_MODEL_POINT + "- `tasks_move` relocates one task.\n"

    assert len(blanket_denials(planted, "en")) == 1


# --- hardening and privacy ---------------------------------------------------------------------


@pytest.mark.parametrize("lang", list(HARDENING), ids=list(HARDENING))
def test_each_hardening_guide_names_the_switch_and_the_move_tool(lang: str) -> None:
    """DOC-05: the guide an operator follows names the task switch in every language."""
    text = read(HARDENING[lang])
    missing = [needle for needle in (SWITCH, MOVE_TOOL, TASK_WORD[lang]) if needle not in text]

    assert missing == [], f"{HARDENING[lang].name} does not name {missing}"


@pytest.mark.parametrize("needle", [SWITCH, MOVE_TOOL])
def test_the_privacy_page_names_the_modifying_task_tools(needle: str) -> None:
    """DOC-04: the chain of foreign text and modifying task tools stands in privacy.md."""
    assert needle in read(PRIVACY), f"privacy.md does not name {needle}"
