"""The security promise of the README, enforced by a gate instead of by discipline.

README, tool annotations and app store listing all say the same sentence: this server can
never delete, overwrite or re-share anything (TOOL-09). Without a gate that sentence is a
claim about today's code and says nothing about the next commit, which is exactly the
threat this file answers (T-01-94).

Since plan 33-03 the sentence is narrower, and this file is where it is exact: deleting,
renaming and re-sharing stay forbidden everywhere; overwriting and relocating are allowed at
exactly the named places, and only under a precondition. The overwriting PUT lives in
``clients/tasks.put_existing_todo`` with ``If-Match`` (counted in ``EXPECTED_PUT_CALLS``),
and a MOVE lives only in the chunk assembly of ``clients/dav.py`` and in
``clients/tasks.move_todo``, each with ``Overwrite: F``, the second with ``If-Match`` as
well (pinned by the syntax tree in ``_move_gate``).

Two things make this test trustworthy rather than decorative:

*   **Comments and docstrings are removed before counting.** ``clients/dav.py`` explains in
    its module docstring that it implements no DELETE, no MOVE, no COPY and no PROPPATCH.
    A naive grep would fail on that sentence, and the usual repair is to delete the
    sentence, which trades documentation for a green check. String literals stay in scope
    on purpose: ``method="DELETE"`` is the real thing this gate is looking for.
*   **Every finding names file and line**, so a violation is a one line fix and never a
    hunt through the tree.

The same parsing gives two more guarantees for free: no module level mutable state that
could act as a session store (D-20), and no tool that stops to ask the user mid call.
"""

import ast
import io
import tokenize
from collections.abc import Iterable
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"

# Destructive HTTP verbs and the one OCS route that changes who may see an object. Upper
# case on purpose: httpx spells a custom method in upper case, and the lower case words
# "move" or "copy" occur in ordinary prose and identifiers.
#
# The five Tables entries at the end are a different kind of needle: they carry no
# forbidden verb, because a POST on a single row route changes that row and a POST on a
# scheme route rewrites a whole table. The verb alone would let all of that through, so
# these name the route instead.
#
# All five are anchored on a **path segment**, not on the opening quote of a literal. An
# earlier version used ``'"/columns/'`` and ``"tables/scheme"``, and the project's own way of
# writing a path walked straight past both of them: a column write reads
# ``f"{V2_PREFIX}/columns/{column_id}"`` and never opens a literal with that segment, and a
# per table scheme export reads ``f"{V2_PREFIX}/tables/{table}/scheme"`` and never puts the
# two words next to each other. The integration tests of this phase build their scaffolding
# routes in exactly that spelling, so the gap was not hypothetical (WR-05). Anchoring on the
# segment costs two exemptions instead, for the two reads the family exists for, and those
# are named as exact literals below.
#
# The ten Talk entries after them are the same kind of needle for a family that needs it more
# than any other, and the reason is a verb that is missing from this list: **PUT** is not
# forbidden in this project, because ``files_upload`` is a PUT. A route that edits a message
# therefore falls through every verb needle there is, and a route that hands a message to the
# app for later delivery ("/schedule") would even walk past the administrative send switch of
# TALK-04, because the app, not this server, would do the sending. So this family is secured
# from both sides: the ten segments below, each with its own counter proof in
# :data:`TALK_ROUTES`, and :data:`ALLOWED_TALK_ROUTES` as the positive statement about the
# exactly three path forms the Talk client really builds.
#
# ``/share`` already stands above and needs no second entry: the attachment route of Talk is
# ``chat/{token}/share``, so the Tables needle covers it. An eleventh needle beside it would
# only look like more security.
#
# The nine Mail entries at the end are the same kind of needle for the family that needs it
# most, and the reason is a route that lies next door to a read: the Mail app declares exactly
# one send path, ``/apps/mail/message/send``, and the full message read is
# ``/apps/mail/message/{id}``. The two share the segment ``/message/`` and only ``send``
# separates them, so the needle has to be the longer segment and the counter proof in
# :data:`MAIL_ROUTES` is what shows that it still hits. The eight ``/api/...`` entries beside
# it are the internal resource routes of the app's own frontend, which this server
# deliberately never builds (see the module docstring of ``clients/mail.py``): a POST there
# creates, a PUT changes and a DELETE removes on the very path a read would use, and no verb
# needle can tell those four apart. ``/api/outbox`` is the second way to send in that app and
# carries no ``send`` in its path at all.
#
# Two needles that already stand above reach into the Mail family without anything being done
# about it, and neither of them gets a second entry beside the nine: ``/attachment`` forbids
# the Mail attachment route the same way it forbids the Talk one, and ``/read`` forbids
# ``/api/mailboxes/{id}/read``, which ``/api/mailboxes`` covers a second time anyway. A tenth
# and eleventh Mail needle for those two would only look like more security.
#
# :data:`ALLOWED_MAIL_ROUTES` is the other half of the proof, and it matters more here than
# for Talk: PUT and POST are allowed verbs in this project, so a needle can never say which
# path forms are meant to exist. That list says it out loud, with the four the client builds.
FORBIDDEN: dict[str, str] = {
    "DELETE": "no tool may delete anything",
    "MOVE": "no tool may rename anything, and a MOVE lives only in its two named places",
    "COPY": "no tool may duplicate anything server side",
    "PROPPATCH": "no tool may change properties of an existing object",
    "ocs/v2.php/apps/files_sharing": "no tool may create or change a share",
    ".delete(": "no client helper may expose a delete call",
    "/rows/": "no tool may address a single Tables row: reading, changing and deleting "
    "one all live on that route",
    "/columns/": "no tool may create, change or delete a Tables column",
    "/scheme": "no tool may import or export a table scheme",
    "/transfer": "no tool may hand a table to another owner",
    "/share": "no tool may create or change a Tables share, and it is the attachment route "
    "of Talk as well",
    "/schedule": "no tool may hand a message to the app for later delivery: the app would "
    "send it, which walks around the administrative switch of TALK-04",
    "/summarize": "no tool may send chat content to an AI provider of the instance",
    "/reminder": "no tool may set or drop a reminder on somebody's message",
    "/pin": "no tool may pin or unpin a message in a conversation",
    "/attachment": "no tool may place a file in a conversation",
    "/read": "no tool may move the read marker of this account or reset it to unread",
    "/favorite": "no tool may mark a conversation as a favourite or take the mark away",
    "/notify": "no tool may push a notification into somebody's conversation",
    "/participants": "no tool may add, remove or re-rank a participant",
    "/archive": "no tool may put a conversation aside or take it back out",
    "/message/send": "no tool may send a mail: this is the one declared send route of the "
    "Mail app, and it lies directly beside the full message read on the same segment",
    "/api/messages": "no tool may reach the internal message resource of Mail: POST drafts, "
    "PUT changes and DELETE removes on the very path a read would use",
    "/api/mailboxes": "no tool may create, sync, clear, repair or mark a mailbox read",
    "/api/accounts": "no tool may change a mail account, its draft settings or its signature",
    "/api/drafts": "no tool may create or move a draft",
    "/api/outbox": "no tool may put a mail into the outbox: that is the second way to send "
    "in this app, and it carries no send in its path",
    "/api/thread": "no tool may move or delete a whole thread",
    "/api/tags": "no tool may create, change or delete a mail tag, or put one on a message",
    "/api/trustedsenders": "no tool may grant or withdraw trust in a sender: that is a "
    "security decision of the account holder",
    # The three entries below guard EXCL-07: the tag ``kein-ki`` is the one fact the
    # exclusion guard trusts, so for this server it is read only. The relation route is what
    # assigns a system tag to a file or takes it away again, and the connector builds no form
    # of it at all. The occ tag commands belong to the integration harness only, which lives
    # in tests/ and therefore outside SRC. The legacy route is ``Api#updateFileTags`` of the
    # Files app, which rewrites the old file tags and the favourite mark with a plain POST.
    # PROPPATCH on ``oc:tags`` and ``oc:favorite`` needs no entry of its own: that verb is
    # forbidden above for every target, and a counter proof below shows it reports both.
    "systemtags-relations": "no tool may assign a system tag to a file or remove it from one",
    "tag:files": "the occ commands tag:files:add and tag:files:delete belong to the test "
    "harness only",
    "/apps/files/api/v1/files": "no tool may change the legacy file tags or the favourite "
    "mark via POST",
}

# The two MOVEs in production, each exempt by file and exact line text only. The first is
# Nextcloud's internal chunk-assembly step: it carries ``Overwrite: F`` and is therefore still
# create-only. The second follows below. Renaming remains forbidden, and any other MOVE is
# reported by the needle and by the syntax tree pin ``_move_gate``.
CHUNK_ASSEMBLY_MOVE = "nextcloud/clients/dav.py"

# The relocation of one task into another list of the same account (TMOD-08, plan 33-03).
# It carries ``Overwrite: F`` and ``If-Match`` and is pinned by the syntax tree below.
TASK_MOVE = "nextcloud/clients/tasks.py"

#: The five needles above that name a Tables route, with a line that would carry them into
#: the code. They stay next to the counter proof rather than next to the dictionary,
#: because their only job is to prove that each needle can still be hit. Every line is
#: written the way this project writes a path, an f-string with the prefix constant in it,
#: because that is the spelling the previous needles missed.
TABLES_ROUTES: dict[str, str] = {
    "/rows/": '    response = await client.get(api_url(creds, f"/tables/{table}/rows/{row_id}"))',
    "/columns/": '    await ocs.ocs_post(client, creds, f"{V2_PREFIX}/columns/{cid}", body)',
    "/scheme": '    url = ocs.ocs_url(creds, f"{V2_PREFIX}/tables/{table}/scheme")',
    "/transfer": '    url = ocs.ocs_url(creds, f"{V2_PREFIX}/tables/{table}/transfer")',
    "/share": '    url = ocs.ocs_url(creds, f"{V2_PREFIX}/{NODE_COLLECTION_TABLES}/{t}/share")',
}

#: The ten needles above that name a Talk route, with a line that would carry them into the
#: code. Same job as :data:`TABLES_ROUTES` one family earlier: a needle nobody ever hit is
#: indistinguishable from no needle at all, so every one of them gets the line it has to
#: report, written in the f-string spelling this project uses for a path.
TALK_ROUTES: dict[str, str] = {
    "/schedule": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/schedule", b)',
    "/summarize": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/summarize", b)',
    "/reminder": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/{m}/reminder", b)',
    "/pin": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/{m}/pin", b)',
    "/attachment": '    url = ocs.ocs_url(creds, f"{CHAT_PREFIX}/{room}/{m}/attachment")',
    "/read": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/read", b)',
    "/favorite": '    await ocs.ocs_post(client, creds, f"{ROOM_PREFIX}/{room}/favorite", b)',
    "/notify": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/notify", b)',
    "/participants": '    url = ocs.ocs_url(creds, f"{ROOM_PREFIX}/{room}/participants")',
    "/archive": '    await ocs.ocs_post(client, creds, f"{ROOM_PREFIX}/{room}/archive", b)',
}

#: The nine needles above that name a Mail route, with a line that would carry them into the
#: code. Same job as :data:`TABLES_ROUTES` and :data:`TALK_ROUTES` two families earlier: a
#: needle nobody ever hit is indistinguishable from no needle at all. The first line is the one
#: MAIL-01 SC4 asks for by name, because the Mail app really does offer that route and this
#: server really does read one segment above it.
MAIL_ROUTES: dict[str, str] = {
    "/message/send": '    await ocs.ocs_post(client, creds, "/apps/mail/message/send", body)',
    "/api/messages": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/messages/{m}", b)',
    "/api/mailboxes": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/mailboxes/{m}", b)',
    "/api/accounts": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/accounts/{a}", b)',
    "/api/drafts": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/drafts/{draft}", body)',
    "/api/outbox": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/outbox/{m}", body)',
    "/api/thread": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/thread/{t}/move", b)',
    "/api/tags": '    await ocs.ocs_post(client, creds, f"/apps/mail/api/tags/{tag}", body)',
    "/api/trustedsenders": '    url = ocs.ocs_url(creds, f"/apps/mail/api/trustedsenders/{s}")',
}

#: The three needles above that name a tag write path (EXCL-07), in a fixed order so the
#: counting test below can compare them against their counter proofs as a set.
SYSTEMTAGS_NEEDLES = ("systemtags-relations", "tag:files", "/apps/files/api/v1/files")

#: The three tag needles with a line that would carry them into the code. Same job as the
#: route dictionaries of Tables, Talk and Mail: a needle nobody ever hit is indistinguishable
#: from no needle at all. Every line is written the way this project writes a path, an
#: f-string with the base URL in it, and the occ line the way the integration harness spells
#: the command it runs inside the container.
SYSTEMTAGS_ROUTES: dict[str, str] = {
    "systemtags-relations": "    await client.put("
    'f"{creds.base_url}/remote.php/dav/systemtags-relations/files/{fileid}/{tag_id}")',
    "tag:files": '    occ("tag:files:add", target, "kein-ki", "public")',
    "/apps/files/api/v1/files": "    await client.post("
    'f"{creds.base_url}/index.php/apps/files/api/v1/files{path}", json={"tags": tags})',
}

#: The two verbs a call on the system tag collection may carry. Everything else that touches
#: that collection writes: POST creates a tag, PROPPATCH renames it or changes who may see
#: and assign it, PUT and DELETE work on relations and tags (EXCL-07).
READ_METHODS = frozenset({"PROPFIND", "REPORT"})

#: The attribute names of an HTTP call on an httpx client. ``get`` is missing on purpose: it
#: is also the name of every dictionary lookup, and a GET changes nothing anyway.
#: ``build_request`` carries verb and target of a request that ``send`` fires later (review
#: WR-06 of phase 28): ``send(req)`` names no target, so the verb has to be read where the
#: request is built.
CALL_ATTRS = frozenset(
    {"request", "build_request", "post", "put", "patch", "delete", "stream", "send"}
)

#: The call names whose first argument is the verb, as in ``client.request("PROPFIND", url)``.
VERB_FIRST_ATTRS = frozenset({"request", "build_request"})

#: The one module that talks to the system tag collection, held to the rule that it reads.
SYSTEMTAGS_MODULE = "nextcloud/clients/systemtags.py"

#: The forms :mod:`mcp_connector.nextcloud.clients.systemtags` really builds, as pairs of
#: verb and target in the spelling ``ast.unparse`` gives them: the tag listing on the
#: collection, the one REPORT on the home root, and since plan 29-03 the two reads of
#: exclusion:check (the detail listing on the collection, hence the listing form twice, and
#: the Depth 0 count of ``nc:object-ids`` on one tag). The line needles cannot deliver this
#: half of the proof, because the calls are written over several lines and a needle never sees
#: the verb and the target on the same one.
ALLOWED_SYSTEMTAGS_FORMS = (
    ("PROPFIND", "f'{creds.base_url}{TAGS_PATH}'"),
    ("PROPFIND", "f'{creds.base_url}{TAGS_PATH}'"),
    ("PROPFIND", "f'{creds.base_url}{TAGS_PATH}{tag_id}'"),
    ("REPORT", "home_url(creds)"),
)

#: The four forms :mod:`mcp_connector.nextcloud.clients.mail` really builds, written the way
#: that module writes them: as the four path constants at the top of the file. This tuple is
#: the half of the proof the needles cannot deliver, and for this family it carries more weight
#: than anywhere else. POST and PUT are allowed verbs in this project (``files_upload`` is a
#: PUT), so no needle can ever say which forms are meant to exist; and the fourth entry below
#: sits one segment away from the send route the first Mail needle forbids. Saying both out
#: loud is what makes the prohibition checkable instead of merely stated.
ALLOWED_MAIL_ROUTES = (
    'ACCOUNTS_PATH = "/apps/mail/account/list"',
    'MAILBOXES_PATH = "/apps/mail/ocs/mailboxes"',
    'MESSAGES_PATH = "/apps/mail/ocs/mailboxes/{mailbox}/messages"',
    'MESSAGE_PATH = "/apps/mail/message/{message}"',
)

#: The two modules of the Mail family, and the call forms that must not appear in either of
#: them. This is the check no needle list can replace: a needle knows one path, and this one
#: says that there is no write **call** at all, whatever path it would address (T-10-39). The
#: pattern is the one ``contacts.py`` has been held to since phase 1 (D-07).
MAIL_MODULES = ("nextcloud/clients/mail.py", "tools/mail.py")
WRITING_CALLS = ("ocs_post", ".post(", ".put(", ".patch(", ".delete(", "client.request")

#: The three forms :mod:`mcp_connector.nextcloud.clients.talk` really builds: the conversation
#: list, one window of history, and the one send. This tuple is the half of the proof the
#: needles cannot deliver, because PUT is not a forbidden verb here (see the block above
#: :data:`FORBIDDEN`): the family says out loud which path forms exist instead of only saying
#: which ones must not.
ALLOWED_TALK_ROUTES = (
    '    await ocs.ocs_get(client, creds, ROOM_PREFIX, params={"noStatusUpdate": 1}),',
    '    await ocs.ocs_get(client, creds, f"{CHAT_PREFIX}/{conversation}", params=params),',
    '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{conversation}", {"message": t}),',
)

#: The three forms :mod:`mcp_connector.nextcloud.clients.tables` really builds. They are the
#: reason the needles are shaped the way they are, so they are asserted, not assumed.
ALLOWED_TABLES_ROUTES = (
    '    api_url(creds, f"/tables/{table}/rows/simple"),',
    '    ocs.ocs_url(creds, f"{V2_PREFIX}/columns/{NODE_TYPE_TABLE}/{table}"),',
    '    ocs.ocs_url(creds, f"{V2_PREFIX}/{NODE_COLLECTION_TABLES}/{table}/rows"),',
)

# The two reads that live below a segment a needle names, and the file they live in. Both are
# GETs, both are what the Tables family exists for, and both are named as the exact literal
# the client writes: the compact row read of generation 1 and the column list of one table.
# A second route below the same segment, in this file as much as in any other, is still a
# finding, which is what keeps the exemption from becoming "ignore Tables routes here".
FILES_WITH_THE_TABLES_READS = frozenset({"nextcloud/clients/tables.py"})
TABLES_READ_FORMS = (
    'f"/tables/{table}/rows/simple"',
    'f"{V2_PREFIX}/columns/{NODE_TYPE_TABLE}/{table}"',
)

#: The needles the read exemption may apply to. ``DELETE`` and the other verbs are never
#: exempt by it, and neither are ``/transfer`` and ``/share``: no read of this server needs
#: either of those segments.
TABLES_READ_NEEDLES = ("/rows/", "/columns/")

# The two files where the word DELETE is not an HTTP verb. TOOL-09 is a promise about what
# this server does to data in Nextcloud, and both of these are our own SQLite files.
#
# oauth/store.py has to drop an expired authorization code and a registration nobody ever
# used, or it grows without a bound (T-03-17).
#
# audit/store.py has to drop rows for the retention window and for the upper bound of
# AUDIT-03. Without them the audit log grows without a bound and fills the volume the OAuth
# store lives in, which would make the store that answers every request unable to write
# (T-18-05). Nothing of any user is removed: what goes is a row this app wrote about a call
# of this app, and a marker in the instance chain says how many rows went and where.
#
# The exemption is deliberately narrow, two exact SQL forms per file, so an HTTP DELETE
# written in either module is still reported, and ``.delete(`` above is never exempt anywhere.
FILES_WITH_OWN_SQL = frozenset({"oauth/store.py", "audit/store.py"})
SQL_DELETE_FORMS = ("DELETE FROM ", "ON DELETE CASCADE")

# The second file where DELETE is not a tool deleting user data: the login flow revokes the
# app password it created itself, authenticated with exactly that app password (D-34 and
# D-36, plan 03-04). Nothing of the user is removed, only the credential this server was
# handed, and being unable to hand it back would mean a connection a user revoked stays
# usable in Nextcloud. The exemption is one exact call form in one file, so a DELETE written
# against any other target in the same module is still reported, and ``.delete(`` above is
# never exempt anywhere.
FILES_WITH_OWN_APP_PASSWORD = frozenset({"oauth/loginflow.py"})

#: The verb on a line of its own, which is how the formatter writes the one call that is
#: meant. A DELETE written inline, against any target, does not match and stays a finding.
APP_PASSWORD_DELETE_FORM = '"DELETE",'

# The third file where DELETE is not a tool deleting user data: the purge of plan 05-06
# removes the data key of this app from Nextcloud's own ExApp configuration
# (``oauth/crypto.py::delete_key``, DELETE on the resource whose write and read halves
# already live in that module). What goes is a value this app wrote about itself, and its
# removal is what makes an uninstall honest: a key left behind still opens the ciphertexts
# in a copied volume. Nothing of any user is touched, and no promise of TOOL-09 is about
# it. The exemption is one exact call form in one file, exactly like the one above, so a
# DELETE written against any other target in the same module is still reported, and
# ``.delete(`` is never exempt anywhere.
FILES_WITH_OWN_CONFIG = frozenset({"oauth/crypto.py"})

#: The same shape as :data:`APP_PASSWORD_DELETE_FORM` and written out a second time rather
#: than shared: the two exemptions are independent, and one of them widening must not widen
#: the other.
CONFIG_DELETE_FORM = '"DELETE",'

# The fourth file (issue #34): the enable hook removes the admin form registration this app
# made under its id up to 0.6.1 (``exapp/admin_settings.py::retire_legacy_admin_form``,
# DELETE on ``ui/settings``, whose POST half lives in the same module). What goes is a
# registration this app wrote about itself in the AppAPI control plane; the values an
# administrator saved are keyed on the field id and stay. The same one exact call form as
# the two exemptions above, so any other DELETE in that module is still reported.
FILES_WITH_OWN_FORM = frozenset({"exapp/admin_settings.py"})

#: Written out a fourth time for the reason given at :data:`CONFIG_DELETE_FORM`.
FORM_DELETE_FORM = '"DELETE",'

# Module level mutable state is forbidden as a rule, because a dictionary that outlives a
# request is one refactor away from being a session store, and a session store is what
# breaks the restart proof (D-20). These three are the documented exceptions: all are pure
# latency optimisations, all may be empty at any moment without changing an answer, and
# none of them holds a credential.
ALLOWED_MODULE_STATE: set[tuple[str, str]] = {
    ("nextcloud/http.py", "_clients"),  # one httpx client per event loop, weakly keyed
    ("nextcloud/capabilities.py", "_cache"),  # capabilities per (base_url, user), 60 s TTL
    # tag name to ids per (base_url, user), 60 s TTL, positive only (E3, EXCL-02)
    ("nextcloud/exclusion.py", "_tag_ids"),
}

_MUTABLE_FACTORIES = {
    "dict",
    "list",
    "set",
    "defaultdict",
    "WeakKeyDictionary",
    "WeakValueDictionary",
}


def _source_files() -> list[Path]:
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no production sources found under {SRC}"
    return files


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Return the source lines with comments and docstrings blanked out.

    Only these two are removed. A string literal that is not a docstring stays, because a
    destructive call is written as a string: ``client.request("DELETE", url)``.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    blanked = list(lines)

    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        first = node.body[0]
        end = first.end_lineno or first.lineno
        for lineno in range(first.lineno, end + 1):
            blanked[lineno - 1] = ""

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        lineno, col = token.start
        blanked[lineno - 1] = blanked[lineno - 1][:col]

    return [(number, text) for number, text in enumerate(blanked, start=1) if text.strip()]


def _violations(relative: str, lines: Iterable[tuple[int, str]]) -> list[str]:
    """Every finding in already filtered lines, in the form the failure message prints.

    Shared by the gate and by its counter proofs on purpose: a counter proof that
    reimplements the check proves something about the counter proof.
    """
    findings: list[str] = []
    for number, text in lines:
        for needle, why in FORBIDDEN.items():
            if needle not in text:
                continue
            if (
                needle == "MOVE"
                and relative in (CHUNK_ASSEMBLY_MOVE, TASK_MOVE)
                and text.strip() == '"MOVE",'
            ):
                continue
            if needle == "DELETE" and _is_own_sql(relative, text):
                continue
            if needle == "DELETE" and _is_own_app_password(relative, text):
                continue
            if needle == "DELETE" and _is_own_config_value(relative, text):
                continue
            if needle == "DELETE" and _is_own_form_registration(relative, text):
                continue
            if needle in TABLES_READ_NEEDLES and _is_a_tables_read(relative, text):
                continue
            findings.append(f"{relative}:{number}: {needle!r} ({why}): {text.strip()}")
    return findings


def test_the_production_code_contains_no_destructive_request() -> None:
    """TOOL-09: the promise holds in the code, not only in the README."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        findings.extend(_violations(relative, _code_lines(path)))

    assert findings == [], "destructive call found:\n" + "\n".join(findings)


def test_file_updates_keep_create_and_compare_and_swap_puts_distinct() -> None:
    """A file update must stay compare-and-swap while file creation stays create-only."""
    path = SRC / "nextcloud" / "clients" / "dav.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}

    create = ast.unparse(functions["put_new_file"])
    update = ast.unparse(functions["update_file"])

    assert "If-None-Match" in create
    assert "*" in create
    assert ".put(" in create

    assert "If-Match" in update
    assert "etag" in update
    assert ".put(" in update


#: A PUT that runs without a precondition header, pinned by file and function. The chunk
#: protocol writes into Nextcloud's temporary upload folder and its final MOVE carries
#: ``Overwrite: F``; the init-progress push is the ExApp talking about itself to the
#: AppAPI control plane, never user content. A third entry here is a review event.
UNCONDITIONAL_PUTS = {
    ("nextcloud/clients/dav.py", "put_upload_chunk"),
    ("exapp/status.py", "report_init_progress"),
}

#: Every PUT call in the production code, counted. A new PUT that this gate somehow does
#: not flag still changes the count, so it cannot slip in silently. Seven since plan 33-03:
#: the one overwriting PUT of ``clients/tasks.put_existing_todo`` (TMOD-01, D-33-03), which
#: always carries ``If-Match`` on a normalized strong ETag and is pinned below against the
#: create-only writer of ``caldav.py``. It has no entry in ``UNCONDITIONAL_PUTS``.
EXPECTED_PUT_CALLS = 7


def _usable_precondition(call: ast.Call) -> bool:
    """A literal headers dict with one If-Match/If-None-Match pair SabreDAV honours.

    A vacuous literal, an empty string, a bare ``*`` for ``If-Match`` or a weak ``W/``
    validator, is the exact shape SabreDAV waves through, so it counts as absent.
    """
    headers = next((kw.value for kw in call.keywords if kw.arg == "headers"), None)
    if not isinstance(headers, ast.Dict):
        return False
    for key, value in zip(headers.keys, headers.values, strict=True):
        if not isinstance(key, ast.Constant) or key.value not in ("If-Match", "If-None-Match"):
            continue
        if isinstance(value, ast.Constant):
            text = str(value.value).strip()
            if key.value == "If-Match" and (not text or text == "*" or text.startswith("W/")):
                return False
            if key.value == "If-None-Match" and text != "*":
                return False
        return True
    return False


def _unconditional_puts(relative: str, tree: ast.AST) -> tuple[list[str], int]:
    """Every PUT in ``tree`` that could overwrite without a precondition, plus the count.

    Flags ``.put(...)`` calls and ``.request("PUT", ...)`` calls without a usable
    ``If-Match``/``If-None-Match`` header. The rule deliberately ignores the URL: a PUT
    through a variable or a helper is held exactly like a spelled-out one, and the two
    PUTs that legitimately run unconditioned are pinned by name in
    ``UNCONDITIONAL_PUTS``.
    """
    findings: list[str] = []
    seen = 0

    def _is_put(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Attribute) and call.func.attr == "put":
            return True
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "request"
            and bool(call.args)
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == "PUT"
        )

    class Walker(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._function(node)

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            nonlocal seen
            if _is_put(node):
                seen += 1
                where = self.stack[-1] if self.stack else "<module>"
                if (relative, where) not in UNCONDITIONAL_PUTS and not _usable_precondition(node):
                    findings.append(
                        f"{relative}:{node.lineno} in {where}: "
                        "PUT without a usable If-Match/If-None-Match header"
                    )
            self.generic_visit(node)

    Walker().visit(tree)
    return findings, seen


def test_every_put_carries_a_usable_precondition() -> None:
    """No PUT anywhere in the production code may overwrite unconditionally."""
    findings: list[str] = []
    total = 0
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found, seen = _unconditional_puts(relative, tree)
        findings.extend(found)
        total += seen

    assert findings == [], "unconditional PUT found:\n" + "\n".join(findings)
    assert total == EXPECTED_PUT_CALLS, (
        f"the production code carries {total} PUT calls, the gate expects "
        f"{EXPECTED_PUT_CALLS}; a new PUT is a review event, update the pin deliberately"
    )


#: Shapes the gate must flag (counter proofs) and the two legitimate forms it must not.
_PLANTED_PUTS = [
    "async def f(client, url, data):\n    await client.put(url, content=data)\n",
    'async def f(client, url, data):\n    await client.request("PUT", url, content=data)\n',
    'async def f(client, url):\n    await client.put(url, headers={"Content-Type": "x"})\n',
    'async def f(client, url):\n    await client.put(url, headers={"If-Match": ""})\n',
    'async def f(client, url):\n    await client.put(url, headers={"If-Match": "*"})\n',
    'async def f(client, url):\n    await client.put(url, headers={"If-Match": \'W/"1"\'})\n',
    'async def f(client, url):\n    await client.put(url, headers={"X-Note": "If-Match"})\n',
    "async def f(c, u):\n    target = u\n    await c.put(target)\n",
]
_HONEST_PUTS = [
    'async def f(client, url, etag):\n    await client.put(url, headers={"If-Match": etag})\n',
    'async def f(client, url):\n    await client.put(url, headers={"If-None-Match": "*"})\n',
]


def test_the_put_gate_flags_each_planted_bypass() -> None:
    """The gate is proven against the shapes it exists for, not assumed (counter proof)."""
    for source in _PLANTED_PUTS:
        findings, seen = _unconditional_puts("planted.py", ast.parse(source))
        assert seen == 1, source
        assert findings, f"the gate missed a planted bypass:\n{source}"
    for source in _HONEST_PUTS:
        findings, seen = _unconditional_puts("planted.py", ast.parse(source))
        assert seen == 1, source
        assert findings == [], f"the gate flagged a legitimate PUT:\n{source}"


#: Every MKCOL call in the production code, counted. MKCOL is the one verb besides PUT that
#: creates something in the user's files, so it gets a positive statement instead of a
#: needle: where it may live, what it may carry, and how many of them there are (FOLD-05,
#: T-31-10). A third call is a review event.
EXPECTED_MKCOL_CALLS = 2  # chunk staging folder + files_create_folder

#: The one module that may send a MKCOL, in the spelling of :data:`CHUNK_ASSEMBLY_MOVE`.
MKCOL_HOME = "nextcloud/clients/dav.py"

#: The keywords that give an httpx request a body. A MKCOL with a body is an extended MKCOL
#: (RFC 5689) that can set properties on the new collection, which no tool here may do.
_MKCOL_BODY_KEYWORDS = frozenset({"content", "data", "json", "files"})


def _is_mkcol_constant(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value == "MKCOL"


def _mkcol_findings(relative: str, tree: ast.AST) -> tuple[list[str], int]:
    """Every MKCOL in ``tree`` that leaves the one allowed form, plus the count.

    The allowed form is ``<client>.request("MKCOL", ...)`` inside :data:`MKCOL_HOME` with
    spelled-out keywords, none of which carries a body. The verb passed as ``method=`` is
    reported instead of counted: the pin only sees the positional spelling, so the keyword
    spelling would be a MKCOL the count never notices.
    """
    findings: list[str] = []
    seen = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if any(kw.arg == "method" and _is_mkcol_constant(kw.value) for kw in node.keywords):
            findings.append(f"{relative}:{node.lineno}: MKCOL passed as keyword")
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "request"
            and bool(node.args)
            and _is_mkcol_constant(node.args[0])
        ):
            continue
        seen += 1
        if relative != MKCOL_HOME:
            findings.append(f"{relative}:{node.lineno}: MKCOL outside {MKCOL_HOME}")
        if any(kw.arg in _MKCOL_BODY_KEYWORDS for kw in node.keywords):
            findings.append(f"{relative}:{node.lineno}: MKCOL with a body")
        if any(kw.arg is None for kw in node.keywords):
            findings.append(
                f"{relative}:{node.lineno}: MKCOL with unpacked keywords, which may hide a body"
            )
    return findings, seen


def _mkcol_literals(tree: ast.AST) -> list[int]:
    """The line of every string constant ``"MKCOL"`` in code; docstrings do not count.

    Comments never reach the syntax tree, and a docstring that merely talks about the verb
    contains it without being equal to it. The pieces of an f-string are constants of their
    own, so ``f"MKCOL"`` is seen as well.
    """
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and _is_mkcol_constant(node)
        and id(node) not in docstrings
    )


def _parsed_sources() -> list[tuple[str, ast.Module]]:
    return [
        (
            path.relative_to(SRC).as_posix(),
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
        )
        for path in _source_files()
    ]


def test_every_mkcol_lives_in_dav_and_carries_no_body() -> None:
    """FOLD-05: two MKCOL calls, both in the DAV client, neither with a body."""
    findings: list[str] = []
    total = 0
    home_literals = 0
    for relative, tree in _parsed_sources():
        found, seen = _mkcol_findings(relative, tree)
        findings.extend(found)
        total += seen
        if relative == MKCOL_HOME:
            home_literals = len(_mkcol_literals(tree))

    assert findings == [], "MKCOL outside its one allowed form:\n" + "\n".join(findings)
    assert total == EXPECTED_MKCOL_CALLS, (
        f"the production code carries {total} MKCOL calls, the gate expects "
        f"{EXPECTED_MKCOL_CALLS}; a new MKCOL is a review event, update the pin deliberately"
    )
    assert home_literals == total, (
        f"{MKCOL_HOME} spells the verb {home_literals} times but sends it in {total} counted "
        "calls; a verb held in a variable or handed to build_request walks past the count"
    )


def test_no_mkcol_literal_outside_dav() -> None:
    """The verb is spelled in one module only, whatever call form would carry it."""
    findings = [
        f"{relative}:{lineno}: the literal MKCOL outside {MKCOL_HOME}"
        for relative, tree in _parsed_sources()
        if relative != MKCOL_HOME
        for lineno in _mkcol_literals(tree)
    ]
    assert findings == [], "MKCOL spelled outside the DAV client:\n" + "\n".join(findings)


#: Shapes the MKCOL gate must flag, as (file, source, counted calls). The third is the
#: keyword spelling: it is reported and deliberately not counted. The fourth hides the
#: keywords from the reader of the call, and a body with them.
_PLANTED_MKCOLS = [
    (
        MKCOL_HOME,
        'async def f(client, url):\n    await client.request("MKCOL", url, content=b"<x/>")\n',
        1,
    ),
    (
        "tools/files.py",
        'async def f(client, url):\n    await client.request("MKCOL", url)\n',
        1,
    ),
    (
        MKCOL_HOME,
        'async def f(client, url):\n    await client.request(method="MKCOL", url=url)\n',
        0,
    ),
    (
        MKCOL_HOME,
        'async def f(client, url, extra):\n    await client.request("MKCOL", url, **extra)\n',
        1,
    ),
]

#: The form the two real calls have, and a docstring that only talks about the verb.
_HONEST_MKCOL = (
    'async def f(client, url, auth):\n    """Send "MKCOL" without a body."""\n'
    '    await client.request("MKCOL", url, headers={"Destination": url}, auth=auth)\n'
)

#: Spellings of the verb no call check sees, each of which the literal check must report.
_PLANTED_MKCOL_LITERALS = [
    'VERB = "MKCOL"\n',
    'async def f(client, url):\n    await client.send(client.build_request("MKCOL", url))\n',
    'async def f(client, url):\n    await client.request(f"MKCOL", url)\n',
    'def f():\n    """Explain."""\n    return "MKCOL"\n',
]


def test_the_mkcol_gate_flags_each_planted_bypass() -> None:
    """The needle is proven against the shapes it exists for, not assumed (counter proof)."""
    for relative, source, counted in _PLANTED_MKCOLS:
        findings, seen = _mkcol_findings(relative, ast.parse(source))
        assert seen == counted, source
        assert findings, f"the gate missed a planted MKCOL bypass in {relative}:\n{source}"

    findings, seen = _mkcol_findings(MKCOL_HOME, ast.parse(_HONEST_MKCOL))
    assert seen == 1, _HONEST_MKCOL
    assert findings == [], f"the gate flagged the legitimate MKCOL form:\n{_HONEST_MKCOL}"
    assert len(_mkcol_literals(ast.parse(_HONEST_MKCOL))) == 1, (
        "the one literal is the verb of the call; the docstring does not count"
    )

    for source in _PLANTED_MKCOL_LITERALS:
        assert _mkcol_literals(ast.parse(source)), (
            f"the literal check missed a planted spelling:\n{source}"
        )
    assert _mkcol_literals(ast.parse('"""MKCOL"""\n')) == [], (
        "a docstring is prose, even one that is exactly the verb"
    )


# --- Plan 33-03: the overwriting PUT and the relocation of a task --------------------------
#
# Deleting and renaming stay forbidden everywhere. Overwriting and relocating are allowed at
# exactly the named places below, and always under a precondition: the PUT of
# ``clients/tasks.put_existing_todo`` with ``If-Match``, the relocation of
# ``clients/tasks.move_todo`` with ``Overwrite: F`` and ``If-Match``. The needle gate above
# exempts a line by file and text only, so a second ``"MOVE",`` line in the same file would
# walk through it; the syntax tree pins below are what close that gap.

#: Every MOVE call in the production code, by file and function. A third one, or one of
#: these two in another function, is a review event.
MOVE_HOMES = frozenset(
    {
        (CHUNK_ASSEMBLY_MOVE, "finish_chunked_upload"),
        (TASK_MOVE, "move_todo"),
    }
)
EXPECTED_MOVE_CALLS = 2  # chunk assembly + move_todo


def _verb_literals(tree: ast.AST, verb: str) -> list[int]:
    """The line of every string constant equal to ``verb`` in code; docstrings do not count."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == verb and id(node) not in docstrings
    )


def _literal_headers(call: ast.Call) -> dict[str, ast.expr] | None:
    """The literal headers dict of a call by constant key, or ``None`` when it is not one."""
    headers = next((kw.value for kw in call.keywords if kw.arg == "headers"), None)
    if not isinstance(headers, ast.Dict):
        return None
    found: dict[str, ast.expr] = {}
    for key, value in zip(headers.keys, headers.values, strict=True):
        if key is None:
            return None  # ``**more`` inside the dict hides what the request carries
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found[key.value] = value
    return found


def _functions(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _calls_in(node: ast.AST) -> list[ast.Call]:
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)]


def _move_findings(relative: str, tree: ast.AST) -> tuple[list[str], list[tuple[str, str]]]:
    """Every MOVE call in one module that leaves its allowed form, plus where each one sits.

    The allowed form is ``<client>.request("MOVE", ...)`` with spelled-out keywords and a
    literal headers dict that carries ``"Overwrite": "F"``; in :data:`TASK_MOVE` it also
    carries ``If-Match`` on a variable, never on a constant. The verb passed as ``method=``
    is reported instead of counted, as in the MKCOL gate.
    """
    findings: list[str] = []
    seen: list[tuple[str, str]] = []

    class Walker(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._function(node)

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            self.generic_visit(node)
            where = self.stack[-1] if self.stack else "<module>"
            at = f"{relative}:{node.lineno} in {where}"
            if any(
                kw.arg == "method"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "MOVE"
                for kw in node.keywords
            ):
                findings.append(f"{at}: MOVE passed as keyword")
                return
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "request"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "MOVE"
            ):
                return
            seen.append((relative, where))
            if (relative, where) not in MOVE_HOMES:
                findings.append(f"{at}: MOVE outside its two named places")
            if any(kw.arg is None for kw in node.keywords):
                findings.append(f"{at}: MOVE with unpacked keywords, which may hide a header")
            headers = _literal_headers(node)
            if headers is None:
                findings.append(f"{at}: MOVE without a literal headers dict")
                return
            overwrite = headers.get("Overwrite")
            if not (isinstance(overwrite, ast.Constant) and overwrite.value == "F"):
                findings.append(f"{at}: MOVE without the literal header Overwrite: F")
            if "Destination" not in headers:
                findings.append(f"{at}: MOVE without a Destination header")
            if relative == TASK_MOVE and not isinstance(headers.get("If-Match"), ast.Name):
                findings.append(f"{at}: task MOVE without If-Match on a variable ETag")

    Walker().visit(tree)
    return findings, seen


def _move_gate(sources: Iterable[tuple[str, ast.AST]]) -> list[str]:
    """The whole MOVE pin over a set of modules, shared by the gate and its counter proofs."""
    findings: list[str] = []
    seen: list[tuple[str, str]] = []
    homes = {relative for relative, _ in MOVE_HOMES}
    for relative, tree in sources:
        found, here = _move_findings(relative, tree)
        findings.extend(found)
        seen.extend(here)
        literals = _verb_literals(tree, "MOVE")
        if relative not in homes:
            findings.extend(
                f"{relative}:{line}: the literal MOVE outside its homes" for line in literals
            )
        elif len(literals) != len(here):
            findings.append(
                f"{relative} spells MOVE {len(literals)} times but sends it in {len(here)} "
                "counted calls; a verb held in a variable walks past the count"
            )
    if sorted(seen) != sorted(MOVE_HOMES):
        findings.append(
            f"expected exactly one MOVE in each of {sorted(MOVE_HOMES)}, found {sorted(seen)}"
        )
    return findings


def test_every_move_lives_in_its_two_named_places_with_its_guards() -> None:
    """TMOD-08: two MOVE calls, chunk assembly and move_todo, each with Overwrite: F."""
    assert len(MOVE_HOMES) == EXPECTED_MOVE_CALLS
    findings = _move_gate(_parsed_sources())
    assert findings == [], "MOVE outside its allowed form:\n" + "\n".join(findings)


def _put_pin_findings(tree: ast.AST, function: str, *, create_only: bool) -> list[str]:
    """The one PUT of ``function`` and its precondition, create-only or compare-and-swap.

    Create-only: ``If-None-Match: *`` and no ``If-Match``. Compare-and-swap: ``If-Match`` on
    the variable ``etag``, which the function first rebinds through ``dav.normalize_etag``,
    and no ``If-None-Match``. Never both on one request.
    """
    node = _functions(tree).get(function)
    if node is None:
        return [f"{function}: not found"]
    puts = [
        call
        for call in _calls_in(node)
        if isinstance(call.func, ast.Attribute) and call.func.attr == "put"
    ]
    if len(puts) != 1:
        return [f"{function}: {len(puts)} PUT calls, expected exactly one"]
    headers = _literal_headers(puts[0])
    if headers is None:
        return [f"{function}: PUT without a literal headers dict"]
    findings: list[str] = []
    if "If-Match" in headers and "If-None-Match" in headers:
        findings.append(f"{function}: PUT with If-Match and If-None-Match at once")
    if create_only:
        value = headers.get("If-None-Match")
        if not (isinstance(value, ast.Constant) and value.value == "*"):
            findings.append(f"{function}: create-only PUT without If-None-Match: *")
        if "If-Match" in headers:
            findings.append(f"{function}: create-only PUT with If-Match")
        return findings
    value = headers.get("If-Match")
    if not (isinstance(value, ast.Name) and value.id == "etag"):
        findings.append(f"{function}: compare-and-swap PUT without If-Match on the variable etag")
    normalized = any(
        isinstance(child, ast.Assign)
        and [ast.unparse(target) for target in child.targets] == ["etag"]
        and ast.unparse(child.value) == "dav.normalize_etag(etag)"
        and child.lineno < puts[0].lineno
        for child in ast.walk(node)
    )
    if not normalized:
        findings.append(f"{function}: etag is not normalized before the PUT")
    if "If-None-Match" in headers:
        findings.append(f"{function}: compare-and-swap PUT with If-None-Match")
    return findings


def _parsed(relative: str) -> ast.Module:
    path = SRC / relative
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_task_writes_keep_create_and_compare_and_swap_puts_distinct() -> None:
    """TMOD-01: the create-only writer of caldav.py and the overwriting PUT of tasks.py."""
    create = _put_pin_findings(
        _parsed("nextcloud/clients/caldav.py"), "put_new_object", create_only=True
    )
    change = _put_pin_findings(_parsed(TASK_MOVE), "put_existing_todo", create_only=False)
    assert create == [], create
    assert change == [], change


#: Planted relocations, each the whole content of :data:`TASK_MOVE` beside the real dav.py.
_MOVE_FN = "async def move_todo(client, url, dest, etag):\n"
_PLANTED_TASK_MOVES = {
    "without Overwrite": _MOVE_FN
    + '    await client.request("MOVE", url, headers={"Destination": dest, "If-Match": etag})\n',
    "Overwrite T": _MOVE_FN + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "T", "If-Match": etag},\n    )\n',
    "If-Match star": _MOVE_FN + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": "*"},\n    )\n',
    "constant ETag": _MOVE_FN + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": \'"abc"\'},\n    )\n',
    "without If-Match": _MOVE_FN + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F"},\n    )\n',
    "second MOVE in move_todo": _MOVE_FN
    + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n'
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n',
    "second MOVE in another function": _MOVE_FN
    + '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n'
    "async def relocate_again(client, url, dest, etag):\n"
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n',
    "method keyword": _MOVE_FN + '    await client.request(\n        method="MOVE",\n'
    '        url=url,\n        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},'
    "\n    )\n",
    "unpacked keywords": _MOVE_FN + "    extra = {}\n"
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n'
    "        **extra,\n    )\n",
    "unpacked headers": _MOVE_FN + "    more = {}\n"
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag, **more},\n    )\n',
    "verb in a variable": _MOVE_FN + '    verb = "MOVE"\n'
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n'
    "    await client.request(verb, url)\n",
}

#: The form the real relocation has; the same check must leave it alone.
_HONEST_TASK_MOVE = (
    _MOVE_FN + '    """Relocate under "MOVE" semantics."""\n'
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n'
)

#: A MOVE in a module that is no home, in the honest form otherwise.
_PLANTED_FOREIGN_MOVE = (
    "async def move_task(client, url, dest, etag):\n"
    '    await client.request(\n        "MOVE",\n        url,\n'
    '        headers={"Destination": dest, "Overwrite": "F", "If-Match": etag},\n    )\n'
)


def _with(**planted: str) -> list[tuple[str, ast.AST]]:
    """The real modules, each named one replaced or added by its planted source.

    Keys are module paths with ``/`` and ``.`` spelled ``__`` and ``_py``, so that a call
    reads ``_with(nextcloud__clients__tasks_py=...)``.
    """
    replaced = {
        key.replace("__", "/").removesuffix("_py") + ".py": src for key, src in planted.items()
    }
    sources: list[tuple[str, ast.AST]] = [
        (name, tree) for name, tree in _parsed_sources() if name not in replaced
    ]
    sources.extend((name, ast.parse(src)) for name, src in replaced.items())
    return sources


@pytest.mark.parametrize("case", sorted(_PLANTED_TASK_MOVES))
def test_the_move_gate_flags_each_planted_task_move(case: str) -> None:
    """Counter proof through the gate's own check, never through the pattern it pins."""
    findings = _move_gate(_with(nextcloud__clients__tasks_py=_PLANTED_TASK_MOVES[case]))
    assert findings, f"the MOVE gate missed a planted bypass ({case})"


def test_the_move_gate_flags_a_move_in_another_file_and_leaves_the_honest_form() -> None:
    honest = _move_gate(_with(nextcloud__clients__tasks_py=_HONEST_TASK_MOVE))
    assert honest == [], honest

    foreign = _move_gate(
        _with(nextcloud__clients__tasks_py=_HONEST_TASK_MOVE, tools__tasks_py=_PLANTED_FOREIGN_MOVE)
    )
    assert any("tools/tasks.py" in finding for finding in foreign), foreign

    without = _move_gate(
        _with(nextcloud__clients__tasks_py="async def move_todo(client):\n    return None\n")
    )
    assert without, "a missing task MOVE changes the count and must be reported"


def test_the_text_gate_alone_would_let_a_second_task_move_line_through() -> None:
    """Why the syntax tree pin exists: the needle exemption is per file and line text."""
    planted = _PLANTED_TASK_MOVES["second MOVE in another function"]
    lines = [(number, text) for number, text in enumerate(planted.splitlines(), start=1)]
    assert _violations(TASK_MOVE, lines) == []
    assert _move_gate(_with(nextcloud__clients__tasks_py=planted))


#: Planted overwriting PUTs, each the whole of :data:`TASK_MOVE`; the pin must report each.
_PUT_FN = "async def put_existing_todo(client, url, data, etag):\n"
_PLANTED_TASK_PUTS = {
    "If-Match star": _PUT_FN
    + '    etag = dav.normalize_etag(etag)\n    await client.put(url, headers={"If-Match": "*"})\n',
    "constant ETag": _PUT_FN
    + "    etag = dav.normalize_etag(etag)\n"
    + '    await client.put(url, headers={"If-Match": \'"abc"\'})\n',
    "not normalized": _PUT_FN + '    await client.put(url, headers={"If-Match": etag})\n',
    "both preconditions": _PUT_FN
    + "    etag = dav.normalize_etag(etag)\n"
    + '    await client.put(url, headers={"If-Match": etag, "If-None-Match": "*"})\n',
    "two PUTs": _PUT_FN
    + "    etag = dav.normalize_etag(etag)\n"
    + '    await client.put(url, headers={"If-Match": etag})\n'
    + '    await client.put(url, headers={"If-Match": etag})\n',
}
_HONEST_TASK_PUT = (
    _PUT_FN
    + '    etag = dav.normalize_etag(etag)\n    await client.put(url, headers={"If-Match": etag})\n'
)


@pytest.mark.parametrize("case", sorted(_PLANTED_TASK_PUTS))
def test_the_put_pin_flags_each_planted_task_put(case: str) -> None:
    tree = ast.parse(_PLANTED_TASK_PUTS[case])
    assert _put_pin_findings(tree, "put_existing_todo", create_only=False), case


def test_the_put_pin_leaves_the_honest_forms_and_flags_swapped_ones() -> None:
    honest = ast.parse(_HONEST_TASK_PUT)
    assert _put_pin_findings(honest, "put_existing_todo", create_only=False) == []
    assert _put_pin_findings(honest, "put_existing_todo", create_only=True)

    create = ast.parse(
        'async def put_new_object(c, u):\n    await c.put(u, headers={"If-None-Match": "*"})\n'
    )
    assert _put_pin_findings(create, "put_new_object", create_only=True) == []
    assert _put_pin_findings(create, "put_new_object", create_only=False)


def test_the_put_count_gate_also_reports_an_overwriting_put_with_star() -> None:
    """The planted If-Match: * fails the general precondition check as well."""
    findings, seen = _unconditional_puts(TASK_MOVE, ast.parse(_PLANTED_TASK_PUTS["If-Match star"]))
    assert seen == 1
    assert findings


def test_a_planted_eighth_put_changes_the_count() -> None:
    """EXPECTED_PUT_CALLS is a review event: one more honest PUT is seven plus one."""
    total = 0
    for relative, tree in _with(tools__planted_py=_HONEST_TASK_PUT):
        total += _unconditional_puts(relative, tree)[1]
    assert total == EXPECTED_PUT_CALLS + 1


def test_the_gate_would_notice_a_destructive_call_in_the_task_client() -> None:
    """The counter proof of the dav.py test, for clients/tasks.py (plan 33-03).

    The real module carries the one exempt relocation and must report nothing; an injected
    DELETE must be reported through ``_violations``, the function of the real gate.
    """
    real = _code_lines(SRC / TASK_MOVE)
    assert _violations(TASK_MOVE, real) == [], "clients/tasks.py must be clean first"
    assert sum(1 for _, text in real if text.strip() == '"MOVE",') == 1
    findings = _violations(TASK_MOVE, [*real, (10_000, '    await client.request("DELETE", url)')])
    assert any("'DELETE'" in finding for finding in findings)
    findings = _violations(TASK_MOVE, [*real, (10_001, '    await client.request("MOVE", url)')])
    assert any("'MOVE'" in finding for finding in findings), (
        "only the exact line text is exempt, a MOVE in any other spelling is reported"
    )


def _is_own_sql(relative: str, text: str) -> bool:
    """True for a statement against our own store file, false for anything else."""
    return relative in FILES_WITH_OWN_SQL and any(form in text for form in SQL_DELETE_FORMS)


def _is_own_app_password(relative: str, text: str) -> bool:
    """True for the one call that revokes the app password of this server's own connection."""
    return relative in FILES_WITH_OWN_APP_PASSWORD and text.strip() == APP_PASSWORD_DELETE_FORM


def _is_own_config_value(relative: str, text: str) -> bool:
    """True for the one call that removes this app's own value from the ExApp config."""
    return relative in FILES_WITH_OWN_CONFIG and text.strip() == CONFIG_DELETE_FORM


def _is_own_form_registration(relative: str, text: str) -> bool:
    """True for the one call that removes this app's old admin form registration (#34)."""
    return relative in FILES_WITH_OWN_FORM and text.strip() == FORM_DELETE_FORM


def _is_a_tables_read(relative: str, text: str) -> bool:
    """True for the two Tables reads below a named segment, false for anything else."""
    return relative in FILES_WITH_THE_TABLES_READS and any(
        form in text for form in TABLES_READ_FORMS
    )


def test_the_gate_would_notice_a_destructive_call_in_real_code() -> None:
    """Counter proof: the filter removes prose, and only prose.

    Without this test the previous one could be green because the filter eats everything.
    ``clients/dav.py`` is the honest fixture for it: its module docstring names all four
    verbs, and it must still be reported when the same word appears in an actual request.
    The injected line runs through ``_violations`` like every other counter proof in this
    file: a string built with the word DELETE and then searched for the word DELETE would
    stay green even if the gate swallowed every line carrying it. The clean run over the
    real module doubles as the counter proof for the MOVE exemption: dav.py carries the
    exempt chunk-assembly MOVE and must still report nothing. The task client has the same
    proof in ``test_the_gate_would_notice_a_destructive_call_in_the_task_client``.
    """
    relative = "nextcloud/clients/dav.py"
    real = _code_lines(SRC / "nextcloud" / "clients" / "dav.py")
    docstring_text = "\n".join(text for _, text in real)
    assert "no DELETE, no MOVE, no COPY" not in docstring_text, (
        "the filter must remove the module docstring of dav.py"
    )

    assert _violations(relative, real) == [], (
        "dav.py must be clean before the injected call can prove anything; its one MOVE is "
        "the exempt chunk assembly"
    )
    findings = _violations(relative, [*real, (10_000, '    await client.request("DELETE", url)')])
    assert any("'DELETE'" in finding for finding in findings), (
        "the gate must report an injected DELETE through _violations"
    )


def test_the_sql_exemption_covers_sql_and_nothing_else() -> None:
    """Counter proof for the narrow exemption: an HTTP DELETE in the store still counts.

    The exemption exists so the OAuth store may drop its own expired rows. If it were
    written as "ignore DELETE in this file" it would also hide the one line that would
    make this server delete something in Nextcloud from inside the store.
    """
    store = "oauth/store.py"
    assert _is_own_sql(store, 'conn.execute("DELETE FROM flows WHERE expires_at <= ?")')
    assert _is_own_sql(store, "auth_id TEXT NOT NULL REFERENCES x(y) ON DELETE CASCADE,")
    assert not _is_own_sql(store, 'await client.request("DELETE", url)')
    assert not _is_own_sql("tools/files.py", 'conn.execute("DELETE FROM flows")')

    for relative in (
        FILES_WITH_OWN_SQL
        | FILES_WITH_OWN_APP_PASSWORD
        | FILES_WITH_OWN_CONFIG
        | FILES_WITH_OWN_FORM
    ):
        assert (SRC / relative).is_file(), f"{relative} is exempt but does not exist"


def test_the_app_password_exemption_covers_one_call_form_and_nothing_else() -> None:
    """Counter proof for the second exemption: only the revocation of our own credential.

    The login flow deletes the app password it created itself (D-34, D-36). Written as
    "ignore DELETE in that file", the exemption would also hide a request that deletes a
    file of the user from the same module, so it matches the verb on a line of its own and
    nothing else.
    """
    flow = "oauth/loginflow.py"
    assert _is_own_app_password(flow, '            "DELETE",')
    assert not _is_own_app_password(flow, 'await client.request("DELETE", files_url)')
    assert not _is_own_app_password(flow, '            "DELETE", files_url,')
    assert not _is_own_app_password("tools/files.py", '            "DELETE",')


def test_the_config_exemption_covers_one_call_form_and_nothing_else() -> None:
    """Counter proof for the third exemption: only the deletion of our own config value.

    The purge removes the data key this app stored about itself (plan 05-06). Written as
    "ignore DELETE in that file", the exemption would also hide a request that deletes a
    file of the user from the same module, so it matches the verb on a line of its own and
    nothing else, and it does not reach any other file.
    """
    crypto = "oauth/crypto.py"
    assert _is_own_config_value(crypto, '            "DELETE",')
    assert not _is_own_config_value(crypto, 'await client.request("DELETE", files_url)')
    assert not _is_own_config_value(crypto, '            "DELETE", files_url,')
    assert not _is_own_config_value("tools/files.py", '            "DELETE",')
    assert not _is_own_config_value(crypto, 'conn.execute("DELETE FROM flows")')


def test_the_form_exemption_covers_one_call_form_and_nothing_else() -> None:
    """Counter proof for the fourth exemption: only the removal of our own old form (#34)."""
    admin = "exapp/admin_settings.py"
    assert _is_own_form_registration(admin, '            "DELETE",')
    assert not _is_own_form_registration(admin, 'await client.request("DELETE", files_url)')
    assert not _is_own_form_registration(admin, '            "DELETE", files_url,')
    assert not _is_own_form_registration(admin, "await client.delete(url)")
    assert not _is_own_form_registration("tools/files.py", '            "DELETE",')


@pytest.mark.parametrize(("needle", "line"), sorted(TABLES_ROUTES.items()))
def test_each_tables_needle_trips_on_its_route_and_leaves_the_real_module_alone(
    needle: str, line: str
) -> None:
    """Counter proof per Tables needle: it hits the route, and it misses today's code.

    A needle that never matches anything is the same as no needle at all, and a needle that
    matches the module as it stands would be repaired by rewriting the module rather than by
    narrowing the needle. Both failures are silent, so both are asserted here: the real
    source of the Tables client stays clean, and the same check reports the route as soon as
    one line carries it (T-08-20).
    """
    relative = "nextcloud/clients/tables.py"
    real = _code_lines(SRC / relative)
    assert _violations(relative, real) == [], (
        f"{relative} must be clean before a needle can prove anything"
    )

    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr(needle) in finding for finding in findings), (
        f"the gate must report {needle!r} for: {line.strip()}"
    )


def test_the_three_routes_the_tables_client_really_builds_stay_allowed() -> None:
    """The other half of the same proof: the create path and the two reads must pass.

    Creating a row, reading rows and reading the columns are the three things this family
    exists for. A needle broad enough to catch them would force the choice between a green
    gate and a working tool, and that choice always ends with the gate losing.
    """
    for line in ALLOWED_TABLES_ROUTES:
        assert _violations("nextcloud/clients/tables.py", [(1, line)]) == [], (
            f"the gate must not report the allowed route: {line.strip()}"
        )


@pytest.mark.parametrize(("needle", "line"), sorted(TALK_ROUTES.items()))
def test_each_talk_needle_trips_on_its_route_and_leaves_the_real_module_alone(
    needle: str, line: str
) -> None:
    """Counter proof per Talk needle: it hits the route, and it misses today's code.

    The Talk app offers every one of these routes, and none of them needs a forbidden verb to
    do its damage: a POST is enough to pin somebody's message, to move a read marker, to push
    a notification or to hand a message to the app for later delivery. So each segment is a
    needle, and each needle is proven here in both directions. If one of them ever reports the
    real module, the fix is a narrower needle and never a rewritten client (T-09-30).
    """
    relative = "nextcloud/clients/talk.py"
    real = _code_lines(SRC / relative)
    assert _violations(relative, real) == [], (
        f"{relative} must be clean before a needle can prove anything"
    )

    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr(needle) in finding for finding in findings), (
        f"the gate must report {needle!r} for: {line.strip()}"
    )


def test_every_talk_needle_of_this_phase_has_a_counter_proof() -> None:
    """A needle without a counter proof is a claim, and this file does not make claims."""
    assert len(TALK_ROUTES) == 10, (
        "ten Talk segments are named in FORBIDDEN, and each of them needs its own line here"
    )
    unbacked = sorted(needle for needle in TALK_ROUTES if needle not in FORBIDDEN)
    assert unbacked == [], f"a counter proof for a needle nobody armed: {unbacked}"


def test_the_three_routes_the_talk_client_really_builds_stay_allowed() -> None:
    """The other half of the same proof: the two reads and the one send must pass.

    Listing conversations, reading one history window and sending one message are the three
    things this family exists for. A needle broad enough to catch them would force the choice
    between a green gate and a working tool, and that choice always ends with the gate losing.
    """
    for line in ALLOWED_TALK_ROUTES:
        assert _violations("nextcloud/clients/talk.py", [(1, line)]) == [], (
            f"the gate must not report the allowed route: {line.strip()}"
        )


@pytest.mark.parametrize(("needle", "line"), sorted(MAIL_ROUTES.items()))
def test_each_mail_needle_trips_on_its_route_and_leaves_the_real_module_alone(
    needle: str, line: str
) -> None:
    """Counter proof per Mail needle: it hits the route, and it misses today's code.

    This is the counter proof MAIL-01 SC4 asks for word by word, and it runs through the real
    check ``_violations`` rather than through a copy of it: a counter proof that reimplements
    the gate proves something about the counter proof. The Mail app declares a send route and
    this server reads one segment above it, so "there is no way to send a mail through this
    app" is only worth saying if the sentence is enforced against the next commit (T-10-37,
    T-10-38).
    """
    relative = "nextcloud/clients/mail.py"
    real = _code_lines(SRC / relative)
    assert _violations(relative, real) == [], (
        f"{relative} must be clean before a needle can prove anything"
    )

    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr(needle) in finding for finding in findings), (
        f"the gate must report {needle!r} for: {line.strip()}"
    )


def test_every_mail_needle_of_this_phase_has_a_counter_proof() -> None:
    """A needle without a counter proof is a claim, and this file does not make claims."""
    assert len(MAIL_ROUTES) == 9, (
        "nine Mail segments are named in FORBIDDEN, and each of them needs its own line here"
    )
    unbacked = sorted(needle for needle in MAIL_ROUTES if needle not in FORBIDDEN)
    assert unbacked == [], f"a counter proof for a needle nobody armed: {unbacked}"


def test_the_four_routes_the_mail_client_really_builds_stay_allowed() -> None:
    """The other half of the same proof: all four reads must pass, and the fourth is the point.

    ``/apps/mail/message/{message}`` is the full text read, and it lives one segment away from
    the send route the first Mail needle forbids. A needle broad enough to catch it would force
    the choice between a green gate and a working tool, and that choice always ends with the
    gate losing. There is no fifth form and no write form: this family reads and nothing else.
    """
    for line in ALLOWED_MAIL_ROUTES:
        assert _violations("nextcloud/clients/mail.py", [(1, line)]) == [], (
            f"the gate must not report the allowed route: {line.strip()}"
        )


@pytest.mark.parametrize("relative", MAIL_MODULES)
def test_the_mail_modules_are_read_only_in_their_source(relative: str) -> None:
    """The first family without a single write path, and the claim is literally checkable.

    A needle knows one path. This test knows none and says something a needle cannot: there is
    no writing **call** in these two files, whatever it would address, so a route nobody
    thought of when the needles were written is covered as well (T-10-39). The raw source is
    read on purpose and not the filtered code lines: the module docstring of ``clients/mail.py``
    names what is deliberately absent, and it says it in prose rather than in call syntax, so
    the two claims cannot start disagreeing.
    """
    text = (SRC / relative).read_text(encoding="utf-8")
    findings = [call for call in WRITING_CALLS if call in text]
    assert findings == [], (
        f"{relative} is a read only module and must contain nothing but GETs: {findings}"
    )


@pytest.mark.parametrize(("needle", "line"), sorted(SYSTEMTAGS_ROUTES.items()))
def test_each_systemtags_needle_trips_on_its_route_and_leaves_the_real_module_alone(
    needle: str, line: str
) -> None:
    """Counter proof per tag needle: it hits the write path, and it misses today's code.

    The tag ``kein-ki`` is the one thing the exclusion guard trusts, so this server must be
    unable to put it on a file or take it away (EXCL-07). A POST or a PUT is enough for
    either, and both are allowed verbs here, which is why the route itself is the needle.
    The real source of the system tag client stays clean, and the same check reports each
    route as soon as one line carries it.
    """
    relative = "nextcloud/clients/systemtags.py"
    real = _code_lines(SRC / relative)
    assert _violations(relative, real) == [], (
        f"{relative} must be clean before a needle can prove anything"
    )

    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr(needle) in finding for finding in findings), (
        f"the gate must report {needle!r} for: {line.strip()}"
    )


def test_every_systemtags_needle_of_this_phase_has_a_counter_proof() -> None:
    """A needle without a counter proof is a claim, and this file does not make claims."""
    assert set(SYSTEMTAGS_ROUTES) == set(SYSTEMTAGS_NEEDLES), (
        "every tag needle needs exactly one line here, and every line exactly one needle"
    )
    unarmed = sorted(needle for needle in SYSTEMTAGS_NEEDLES if needle not in FORBIDDEN)
    assert unarmed == [], f"a tag needle that is not armed in FORBIDDEN: {unarmed}"


@pytest.mark.parametrize(
    "line",
    [
        '    await client.request("PROPPATCH", url, content=b"<oc:tags>kein-ki</oc:tags>")',
        '    await client.request("PROPPATCH", url, content=b"<oc:favorite>1</oc:favorite>")',
    ],
)
def test_legacy_file_tag_writes_are_caught_by_the_global_proppatch_needle(line: str) -> None:
    """The old file tags and the favourite mark are properties, so PROPPATCH already guards them.

    No needle of their own: PROPPATCH is forbidden everywhere, and a second needle for the same
    verb would only look like more security. What this test adds is the proof that the global
    needle really reports both properties in the module where such a write would be written.
    """
    relative = "nextcloud/clients/dav.py"
    real = _code_lines(SRC / relative)
    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr("PROPPATCH") in finding for finding in findings), (
        f"the gate must report 'PROPPATCH' for: {line.strip()}"
    )


def _mentions_tags(node: ast.AST) -> bool:
    """True when a call names the tag collection: the constant, or a literal carrying it.

    ``ast.walk`` descends into the parts of an f-string as well, so a literal piece such as
    ``/remote.php/dav/systemtags/`` inside ``f"{base}/remote.php/dav/systemtags/{id}"`` counts.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "TAGS_PATH":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "TAGS_PATH":
            return True
        if (
            isinstance(sub, ast.Constant)
            and isinstance(sub.value, str)
            and "systemtags" in sub.value
        ):
            return True
    return False


def _is_a_read_request(node: ast.Call) -> bool:
    """True for ``*.request`` or ``*.build_request`` with PROPFIND or REPORT, nothing else."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in VERB_FIRST_ATTRS:
        return False
    verb = node.args[0] if node.args else None
    return isinstance(verb, ast.Constant) and verb.value in READ_METHODS


def _http_calls(source: str) -> list[ast.Call]:
    """Every call whose attribute name is one of :data:`CALL_ATTRS`, in source order."""
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in CALL_ATTRS
    ]


def tag_writes(relative: str, source: str) -> list[str]:
    """Every HTTP call that names the tag collection and is not a PROPFIND or a REPORT.

    The check works on whole call nodes, not on lines: the two real calls are written over
    several lines, so a verb and its target never share one and a line needle would walk
    past a POST written the same way (T-28-22).
    """
    return [
        f"{relative}:{node.lineno}: write on systemtags"
        for node in _http_calls(source)
        if _mentions_tags(node) and not _is_a_read_request(node)
    ]


def systemtags_module_writes(source: str) -> list[str]:
    """Every HTTP call in the system tag client that is not a PROPFIND or a REPORT.

    This is the rule no mention check can replace: the REPORT goes to ``home_url(creds)``,
    which names neither the constant nor the word, so a write on that target would pass
    :func:`tag_writes` unseen (T-28-23).
    """
    return [
        f"{SYSTEMTAGS_MODULE}:{node.lineno}: the system tag client may only read"
        for node in _http_calls(source)
        if not _is_a_read_request(node)
    ]


def _systemtags_request_forms(source: str) -> tuple[tuple[str, str], ...]:
    """The pair of verb and unparsed target of every ``request`` or ``build_request`` call."""
    forms: list[tuple[str, str]] = []
    for node in _http_calls(source):
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in VERB_FIRST_ATTRS:
            continue
        verb = ast.unparse(node.args[0]).strip("'\"") if node.args else ""
        target = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
        forms.append((verb, target))
    return tuple(sorted(forms))


def test_no_module_writes_on_systemtags() -> None:
    """EXCL-07: every call on the tag collection anywhere in src/ is a PROPFIND or a REPORT."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        findings.extend(tag_writes(relative, path.read_text(encoding="utf-8")))

    assert findings == [], "write on the system tag collection found:\n" + "\n".join(findings)


_MULTILINE_TAG_WRITES = {
    "POST on TAGS_PATH": (
        "    await client.request(\n"
        '        "POST",\n'
        '        f"{creds.base_url}{TAGS_PATH}",\n'
        "    )\n"
    ),
    "PROPPATCH on TAGS_PATH": (
        "    await client.request(\n"
        '        "PROPPATCH",\n'
        '        f"{creds.base_url}{TAGS_PATH}{tag_id}",\n'
        '        content=b"<oc:user-assignable>true</oc:user-assignable>",\n'
        "    )\n"
    ),
    "delete on a tag": (
        '    await client.delete(f"{creds.base_url}/remote.php/dav/systemtags/{tag_id}")\n'
    ),
    "put on a relation": (
        "    await client.put(\n"
        '        f"{creds.base_url}/remote.php/dav/systemtags/{tag_id}/files",\n'
        '        content=b"",\n'
        "    )\n"
    ),
    # Review WR-06: the verb sits in build_request, and send(req) names no target at all.
    "build_request plus send on TAGS_PATH": (
        '    req = client.build_request("POST", f"{creds.base_url}{TAGS_PATH}")\n'
        "    await client.send(req)\n"
    ),
    "build_request plus send on a tag": (
        "    req = client.build_request(\n"
        '        "DELETE", f"{creds.base_url}/remote.php/dav/systemtags/{tag_id}"\n'
        "    )\n"
        "    await client.send(req)\n"
    ),
}


@pytest.mark.parametrize(
    "injected", list(_MULTILINE_TAG_WRITES.values()), ids=list(_MULTILINE_TAG_WRITES)
)
def test_the_systemtags_check_would_notice_a_multiline_write_in_real_code(injected: str) -> None:
    """Counter proof: the real client is clean, and a write appended to it is reported.

    The appended function runs through :func:`tag_writes`, the same function the gate uses:
    a counter proof that reimplements the check proves something about the counter proof.
    """
    real = (SRC / SYSTEMTAGS_MODULE).read_text(encoding="utf-8")
    assert tag_writes(SYSTEMTAGS_MODULE, real) == [], (
        f"{SYSTEMTAGS_MODULE} must be clean before the injected call can prove anything"
    )

    source = f"{real}\n\nasync def _injected(client, creds, tag_id):\n{injected}"
    assert tag_writes(SYSTEMTAGS_MODULE, source) != [], (
        f"the check must report the injected write:\n{injected}"
    )


@pytest.mark.parametrize(
    "injected",
    [
        '    await client.put(home_url(creds), content=b"")\n',
        '    await client.request("POST", home_url(creds))\n',
        '    await client.send(client.build_request("POST", home_url(creds)))\n',
    ],
)
def test_the_systemtags_client_only_reads(injected: str) -> None:
    """The module rule: no call in the system tag client writes, whatever it would address.

    ``home_url(creds)`` names neither ``TAGS_PATH`` nor the word systemtags, so the mention
    check alone would let a write on the home root through. This rule sees it.
    """
    real = (SRC / SYSTEMTAGS_MODULE).read_text(encoding="utf-8")
    assert systemtags_module_writes(real) == [], (
        f"{SYSTEMTAGS_MODULE} is a read only module and must contain nothing but reads"
    )

    source = f"{real}\n\nasync def _injected(client, creds):\n{injected}"
    assert systemtags_module_writes(source) != [], (
        f"the module rule must report the injected write: {injected.strip()}"
    )


def test_the_two_forms_the_systemtags_client_really_builds_stay_allowed() -> None:
    """The other half of the proof: exactly the allowed read forms, nothing more.

    A third form is a decision about the tag the guard trusts, and a decision has to be made
    in a review and not in a diff.
    """
    real = (SRC / SYSTEMTAGS_MODULE).read_text(encoding="utf-8")
    assert _systemtags_request_forms(real) == tuple(sorted(ALLOWED_SYSTEMTAGS_FORMS)), (
        "the system tag client builds a request form nobody allowed"
    )


def test_a_third_form_built_with_build_request_is_noticed() -> None:
    """Review WR-06: a read form built with build_request counts as a form like request does."""
    real = (SRC / SYSTEMTAGS_MODULE).read_text(encoding="utf-8")
    source = (
        f"{real}\n\nasync def _injected(client, creds):\n"
        '    req = client.build_request("PROPFIND", f"{creds.base_url}/remote.php/dav/x")\n'
    )
    assert _systemtags_request_forms(source) != tuple(sorted(ALLOWED_SYSTEMTAGS_FORMS))


def test_the_tables_read_exemption_covers_two_call_forms_and_nothing_else() -> None:
    """Counter proof for the segment exemption: only the two reads, only in that one file.

    The needles ``/rows/`` and ``/columns/`` are anchored on the segment, which is what makes
    them catch the project's own f-string spelling (WR-05). The price is an exemption, and
    written as "ignore those segments in the Tables client" it would hide exactly the line
    that turns this server into something that changes a row or a column, in the very module
    where such a line would be written. So it matches two exact literals and nothing else.
    """
    tables = "nextcloud/clients/tables.py"
    assert _is_a_tables_read(tables, '        api_url(creds, f"/tables/{table}/rows/simple"),')
    assert _is_a_tables_read(
        tables, '        ocs.ocs_url(creds, f"{V2_PREFIX}/columns/{NODE_TYPE_TABLE}/{table}"),'
    )
    assert not _is_a_tables_read(tables, '        api_url(creds, f"/tables/{table}/rows/{row}"),')
    assert not _is_a_tables_read(tables, '        ocs.ocs_url(creds, f"{V2_PREFIX}/columns/{c}"),')
    assert not _is_a_tables_read(
        "tools/tables.py", '        api_url(creds, f"/tables/{table}/rows/simple"),'
    )
    for relative in FILES_WITH_THE_TABLES_READS:
        assert (SRC / relative).is_file(), f"{relative} is exempt but does not exist"


def test_no_module_level_mutable_state_outside_the_three_documented_caches() -> None:
    """D-20: nothing between two requests may remember anything about a session."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            if value is None or not _is_mutable(value):
                continue
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if (relative, target.id) in ALLOWED_MODULE_STATE:
                    continue
                if target.id.isupper():  # module constants are configuration, not state
                    continue
                if target.id.startswith("__") and target.id.endswith("__"):
                    continue  # __all__ is the export list of a module, not runtime state
                findings.append(f"{relative}:{node.lineno}: module level mutable {target.id}")

    assert findings == [], "module level mutable state can become a session store:\n" + "\n".join(
        findings
    )


def _is_mutable(value: ast.expr) -> bool:
    if isinstance(value, ast.Dict | ast.List | ast.Set | ast.DictComp | ast.ListComp | ast.SetComp):
        return True
    if isinstance(value, ast.Call):
        func = value.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        return name in _MUTABLE_FACTORIES
    return False


def test_the_three_allowed_caches_still_exist_where_they_are_claimed_to_be() -> None:
    """An allow list that points at nothing silently stops allowing anything."""
    assert len(ALLOWED_MODULE_STATE) == 3, (
        "the exceptions are counted, not only described: another cache is a decision, and a "
        "decision has to be made in a review and not in a diff (D-20, T-08-23); the third "
        "one (_tag_ids) was decided in the owner review E3 of phase 25"
    )
    for relative, name in ALLOWED_MODULE_STATE:
        path = SRC / relative
        assert path.is_file(), f"{relative} is on the allow list but does not exist"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        declared = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        assert name in declared, f"{relative} no longer declares {name}"


def test_no_tool_stops_to_ask_the_user_or_resolves_a_reference() -> None:
    """A tool that elicits mid call cannot survive a restart and blocks stateless HTTP."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        for number, text in _code_lines(path):
            for needle in ("elicit", "Resolve"):
                if needle in text:
                    findings.append(f"{relative}:{number}: {needle!r}: {text.strip()}")

    assert findings == [], (
        "elicitation and reference resolution keep state across a call:\n" + "\n".join(findings)
    )
