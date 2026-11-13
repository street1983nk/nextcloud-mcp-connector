"""The classification of every tool against the ``kein-ki`` guard; a data module, not a test.

Every registered tool stands in exactly one of three classes (D-28-01): it reads files, it
writes into the file surface, or it is not affected. Each entry carries one sentence of
reason with a ``file:line`` anchor (D-28-03), explicitly also every "not affected", because
an empty "not affected" is exactly the claim a reviewer cannot check.

One truth for three gates: the freeze in ``test_tool_classes.py`` compares this table with
the live registry of ``mcp_connector.server.mcp`` (D-28-02), and the canary and the pair
tests of phase 28 import the same table instead of keeping their own list. A second copy
would be a second truth, and the day the two disagree nobody notices.

Why a module and not ``conftest.py``: ``tests/conftest.py`` imports nothing from
``mcp_connector`` on purpose, and a fixture there would reach every test layer. This module
is imported by name; ``pyproject.toml`` puts ``tests/contract`` on the import path for it.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from mcp_connector.server import CREATE_ONLY, mcp

# Tools whose answer can carry a name, a path, a content or an id of a Nextcloud file.
FILE_READERS: dict[str, str] = {
    "files_search": (
        "Answers names and paths of the WebDAV SEARCH hits of the user (tools/files.py:145-185)."
    ),
    "files_list": "Answers the children of one folder with name and path (tools/files.py:213-256).",
    "files_read": (
        "Answers the content of one file by path, guarded in _visible_stat "
        "(tools/files.py:316-405, :728-772)."
    ),
    "files_download": (
        "Answers the bytes of one file by path as an embedded resource (tools/files.py:408-481)."
    ),
    "files_read_as_markdown": (
        "Answers the content of one Office or PDF file by path as Markdown, guarded in "
        "_visible_stat (tools/files.py:438-515, :837)."
    ),
    "notes_search": (
        "Notes are files and a note id is a fileid, so a hit names a file (tools/notes.py:71)."
    ),
    "notes_read": "Answers one note by its id, which is a fileid (tools/notes.py:159-210).",
    "unified_search": (
        "The files, comments, notes, systemtags and Findling providers carry files "
        "(tools/search.py:93-189)."
    ),
    "prepare_context": (
        "Bundles search hits and excerpts read through fetch, so it answers file names and "
        "content (tools/context.py:230, :730)."
    ),
    "talk_browse": (
        "Messages share files and a file room carries the file name as its room name "
        "(tools/talk.py:820-882)."
    ),
    "search": "A projection of unified_search that answers titles and urls of files "
    "(tools/chatgpt.py:168-201).",
    "fetch": (
        "The id kinds file, note, message and table address files or file references; "
        "task is a kind without a file (tools/chatgpt.py:258-282)."
    ),
    "tables_browse": (
        "A text/link cell picked through the files provider stores the file name and "
        "/f/<fileid> of a tagged file, D-28-14 (tools/tables.py:411-422)."
    ),
}

# Tools that put something at a target in the file surface of the user.
FILE_WRITERS: dict[str, str] = {
    "files_upload": (
        "Creates a file at a path and checks _writable before every write "
        "(tools/files.py:484-529, :705-725)."
    ),
    "files_create_folder": (
        "Creates folders with MKCOL and checks _writable before every MKCOL "
        "(tools/files.py:669-762, :708, :748)."
    ),
    "notes_create": (
        "Creates a note file in a category folder and checks folder and candidate file "
        "(tools/notes.py:213-298)."
    ),
    "talk_send": (
        "Sends into a room by token, and the token of a file room is refused through one_room "
        "(tools/talk.py:820-858)."
    ),
}

# Tools whose answer cannot name a Nextcloud file; each sentence says why.
UNAFFECTED: dict[str, str] = {
    "calendar_list_events": (
        "Answers id, uid, summary, start, end, all_day, calendar and location only; ATTACH and "
        "DESCRIPTION are never parsed (tools/calendar.py:440-455, clients/caldav.py:391-406)."
    ),
    "calendar_create_event": (
        "Answers the echo of its own arguments plus a read-back of the same fields and takes "
        "no file argument (tools/calendar.py:300-320)."
    ),
    "deck_browse": (
        "Answers id, title, stack, url and duedate only; description and attachments of a card "
        "never leave the tool (tools/deck.py:183-190)."
    ),
    "deck_create_card": (
        "Answers id, title, url and duedate, and board and stack are digit ids "
        "(tools/deck.py:119-126, clients/deck.py:210-218)."
    ),
    "contacts_search": (
        "Answers full_name, emails, phones, organization, addressbook and uid; no PHOTO, no URL "
        "and no raw vCard (tools/contacts.py:132-142)."
    ),
    "tables_create_row": (
        "Answers the own row, and a link value comes back only with the title the caller gave "
        "itself (tools/tables.py:411-422)."
    ),
    "mail_browse": (
        "Messages carry has_attachments only and the attachment list is dropped; mails are IMAP "
        "data, not Nextcloud files (tools/mail.py:459-507)."
    ),
    "tasks_search": (
        "Hits carry id, summary, status, times, priority, tags and the list name; ATTACH is "
        "never read and the description stays out (tools/tasks.py:154-181, :505-520)."
    ),
    "tasks_read": (
        "Answers one task, its ETag and its subtasks; DESCRIPTION is capped foreign text, not a "
        "file, and ATTACH is never read (tools/tasks.py:154-181, :603-645)."
    ),
    "tasks_create": (
        "Answers id, summary, list, created, confirmed, due and start of its own task and "
        "takes no file argument (tools/tasks.py:810-821)."
    ),
}

# The shortest reason the freeze accepts: long enough that "n/a" or "safe" cannot pass.
MIN_REASON = 20

# Every single access of a pair test (case -> family). The list follows D-28-09: every tool
# that addresses one object, plus the writers with a target. files_list is added as the reader
# with a folder target, and fetch(table) follows D-28-14.
PAIR_CASES: dict[tuple[str, str], str] = {
    ("files_read", "path"): "files",
    ("files_download", "path"): "files",
    ("files_read_as_markdown", "path"): "files",
    ("files_list", "folder"): "files",
    ("files_search", "folder"): "files",
    ("files_upload", "text"): "files",
    ("files_upload", "binary_chunk1"): "files",
    ("files_create_folder", "path"): "files",
    ("fetch", "file"): "files",
    ("notes_read", "note"): "apps",
    ("fetch", "note"): "apps",
    ("notes_create", "category"): "apps",
    ("talk_browse", "messages"): "apps",
    ("talk_send", "token"): "apps",
    ("fetch", "message"): "apps",
    ("fetch", "table"): "apps",
}

# Pair cases whose two answers may differ on purpose, each with its reason (D-28-16).
# Plan 28-06 may add B5/B6 here after D-28-19/20.
NAMED_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("notes_create", "category"): (
        "The Notes app creates a category that does not exist and the guard refuses a tagged "
        "one; an accepted residual oracle of the kind T-27-16, documented in phase 29."
    ),
}


def unclassified(names: Iterable[str]) -> list[str]:
    """Every name without an entry in any of the three classes, sorted."""
    known = FILE_READERS.keys() | FILE_WRITERS.keys() | UNAFFECTED.keys()
    return sorted(set(names) - known)


def _reason_problem(reason: str) -> str | None:
    if not reason.strip():
        return "empty reason"
    if len(reason) < MIN_REASON:
        return f"reason shorter than {MIN_REASON} characters"
    if "\n" in reason:
        return "reason spans more than one line"
    if not reason.endswith("."):
        return "reason does not end with a full stop"
    return None


def freeze_findings(names: Iterable[str], *, switched_on: Iterable[str] = ()) -> list[str]:
    """Every finding of the freeze, in the form the failure message prints.

    Shared by the gate and by its counter proofs on purpose: a counter proof that
    reimplements the check proves something about the counter proof.

    ``switched_on`` is the registry with every switch on (phase 33, pitfall 5). An entry for
    an optional tool is stale only when that registry does not list it either; the tools of
    ``names`` still have to be classified as before.
    """
    registered = set(names)
    reachable = registered | set(switched_on)
    classes = {
        "FILE_READERS": FILE_READERS,
        "FILE_WRITERS": FILE_WRITERS,
        "UNAFFECTED": UNAFFECTED,
    }
    findings = [f"unclassified: {name}" for name in unclassified(registered)]

    everywhere: dict[str, list[str]] = {}
    for label, table in classes.items():
        for name, reason in table.items():
            everywhere.setdefault(name, []).append(label)
            problem = _reason_problem(reason)
            if problem is not None:
                findings.append(f"{problem}: {label}[{name}]")
    for name in sorted(everywhere.keys() - reachable):
        findings.append(f"stale: {name}")
    for name, labels in sorted(everywhere.items()):
        if len(labels) > 1:
            findings.append(f"in more than one class: {name} ({', '.join(labels)})")

    affected = FILE_READERS.keys() | FILE_WRITERS.keys()
    for tool, case in sorted(PAIR_CASES):
        if tool not in affected:
            findings.append(f"pair case of a tool that is not a reader or writer: {tool}/{case}")
    paired = {tool for tool, _ in PAIR_CASES}
    for name in sorted(FILE_WRITERS.keys() - paired):
        findings.append(f"writer without a pair case: {name}")

    for key, reason in sorted(NAMED_EXCEPTIONS.items()):
        if key not in PAIR_CASES:
            findings.append(f"named exception without a pair case: {key[0]}/{key[1]}")
        problem = _reason_problem(reason)
        if problem is not None:
            findings.append(f"{problem}: NAMED_EXCEPTIONS[{key[0]}/{key[1]}]")
    return findings


@contextmanager
def probe_tool(name: str = "files_update") -> Iterator[str]:
    """Register a tool without an entry for the length of the block (D-28-04).

    Never at module level (pitfall 4): the ``finally`` removes the probe again, so no other
    registry test ever sees it.
    """

    async def files_update(path: str) -> str:
        return path

    mcp.add_tool(files_update, name=name, annotations=CREATE_ONLY, structured_output=False)
    try:
        yield name
    finally:
        mcp.remove_tool(name)
