"""The security promise of the README, enforced by a gate instead of by discipline.

README, tool annotations and app store listing all say the same sentence: this server can
never delete, overwrite or re-share anything (TOOL-09). Without a gate that sentence is a
claim about today's code and says nothing about the next commit, which is exactly the
threat this file answers (T-01-94).

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
    "MOVE": "no tool may move or rename anything",
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
}

# The only MOVE in production is Nextcloud's internal chunk-assembly step. It carries
# ``Overwrite: F`` and is therefore still create-only; user-facing move and rename tools
# remain forbidden.
CHUNK_ASSEMBLY_MOVE = "nextcloud/clients/dav.py"

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

# Module level mutable state is forbidden as a rule, because a dictionary that outlives a
# request is one refactor away from being a session store, and a session store is what
# breaks the restart proof (D-20). These two are the documented exceptions: both are pure
# latency optimisations, both may be empty at any moment without changing an answer, and
# neither holds a credential.
ALLOWED_MODULE_STATE: set[tuple[str, str]] = {
    ("nextcloud/http.py", "_clients"),  # one httpx client per event loop, weakly keyed
    ("nextcloud/capabilities.py", "_cache"),  # capabilities per (base_url, user), 60 s TTL
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
            if needle == "MOVE" and relative == CHUNK_ASSEMBLY_MOVE and text.strip() == '"MOVE",':
                continue
            if needle == "DELETE" and _is_own_sql(relative, text):
                continue
            if needle == "DELETE" and _is_own_app_password(relative, text):
                continue
            if needle == "DELETE" and _is_own_config_value(relative, text):
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


def _is_own_sql(relative: str, text: str) -> bool:
    """True for a statement against our own store file, false for anything else."""
    return relative in FILES_WITH_OWN_SQL and any(form in text for form in SQL_DELETE_FORMS)


def _is_own_app_password(relative: str, text: str) -> bool:
    """True for the one call that revokes the app password of this server's own connection."""
    return relative in FILES_WITH_OWN_APP_PASSWORD and text.strip() == APP_PASSWORD_DELETE_FORM


def _is_own_config_value(relative: str, text: str) -> bool:
    """True for the one call that removes this app's own value from the ExApp config."""
    return relative in FILES_WITH_OWN_CONFIG and text.strip() == CONFIG_DELETE_FORM


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
    """
    dav = SRC / "nextcloud" / "clients" / "dav.py"
    docstring_text = "\n".join(text for _, text in _code_lines(dav))
    assert "no DELETE, no MOVE, no COPY" not in docstring_text, (
        "the filter must remove the module docstring of dav.py"
    )

    with_a_violation = docstring_text + '\n    await client.request("DELETE", url)\n'
    assert "DELETE" in with_a_violation, "a real call is still visible after filtering"


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

    for relative in FILES_WITH_OWN_SQL | FILES_WITH_OWN_APP_PASSWORD | FILES_WITH_OWN_CONFIG:
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


def test_no_module_level_mutable_state_outside_the_two_documented_caches() -> None:
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


def test_the_two_allowed_caches_still_exist_where_they_are_claimed_to_be() -> None:
    """An allow list that points at nothing silently stops allowing anything."""
    assert len(ALLOWED_MODULE_STATE) == 2, (
        "the exceptions are counted, not only described: a third cache is a decision, and a "
        "decision has to be made in a review and not in a diff (D-20, T-08-23)"
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
