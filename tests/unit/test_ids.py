"""Unit tests for the ID codec.

The codec is the only place that builds or reads prefixed IDs. A wrong prefix would
make ``fetch`` resolve a card as a note (silently), so the roundtrip property is
pinned here for all nine kinds.

``mail`` is the one kind with a guard of its own, and the tests below are written against
the reason for it rather than against its shape: a mail id that is not a number has to be
refused by this module, because the call it would otherwise reach is the most expensive of
the whole server (every full message read opens an IMAP session inside the Mail app), and
the app answers a non numeric id with 404 instead of refusing it.
"""

import hashlib
import re

import pytest

from mcp_connector import ids
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError


def test_roundtrip_for_all_nine_kinds() -> None:
    cases = [
        (ids.encode_file("12345"), ("file", ("12345",))),
        (ids.encode_note("42"), ("note", ("42",))),
        (ids.encode_card("7", "13", "99"), ("card", ("7", "13", "99"))),
        (ids.encode_card_short("99"), ("card", ("99",))),
        (ids.encode_event("personal", "abcd-1234.ics"), ("event", ("personal", "abcd-1234.ics"))),
        (ids.encode_mail("4711"), ("mail", ("4711",))),
        (ids.encode_message("abcd1234", "42"), ("message", ("abcd1234", "42"))),
        (ids.encode_table("7"), ("table", ("7",))),
        (ids.encode_task("tasks", "a b.ics"), ("task", ("tasks", "a b.ics"))),
        (
            ids.encode_url("https://nc.test/index.php/apps/notes/note/42"),
            ("url", ("https://nc.test/index.php/apps/notes/note/42",)),
        ),
    ]
    for encoded, expected in cases:
        assert ids.parse(encoded) == expected


def test_encoded_prefixes_are_stable() -> None:
    assert ids.encode_file("1") == "file:1"
    assert ids.encode_note("1") == "note:1"
    assert ids.encode_card("1", "2", "3") == "card:1:2:3"
    assert ids.encode_card_short("3") == "card:3"
    assert ids.encode_event("personal", "x.ics") == "event:personal:x.ics"
    assert ids.encode_mail("1") == "mail:1"
    assert ids.encode_message("abcd1234", "1") == "message:abcd1234:1"
    assert ids.encode_table("1") == "table:1"
    assert ids.encode_task("tasks", "x.ics") == "task:tasks:x.ics"
    assert ids.encode_url("https://nc.test/x") == "url:https://nc.test/x"


def test_a_mail_id_reads_the_same_from_a_number_and_from_a_string() -> None:
    """``mail_browse`` builds the id from an int and a model hands it back as text."""
    assert ids.encode_mail(4711) == "mail:4711" == ids.encode_mail("4711")
    assert ids.parse("mail:4711") == ("mail", ("4711",))


def test_a_mail_id_of_zero_is_a_number_and_the_database_decides_the_rest() -> None:
    """Refusing a zero would be a statement about the Mail database, not about a form.

    This module knows what a mail id looks like; whether a row with that number exists is
    the app's answer to give, and it gives it as a 404 with a sentence of its own.
    """
    assert ids.parse("mail:0") == ("mail", ("0",))


@pytest.mark.parametrize(
    "raw",
    [
        "mail:abc",
        "mail:4711a",
        "mail:-1",
        "mail: ",
        "mail:",
        "mail:47:11",
        "mail: 4711",
        "mail:٤٢",
        "mail:²",
    ],
)
def test_a_mail_id_that_is_not_a_number_is_refused_with_the_format_list(raw: str) -> None:
    """Not a single request may leave for one of these (threat T-10-31).

    The last two are the WR-04 pair: an Arabic-Indic forty-two and a superscript two are
    both true under ``str.isdigit``, and both are not an id the Mail app could ever have
    handed out, so the guard has to measure "numeric" in ASCII digits like the timestamp
    filters do.
    """
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)

    assert "mail:" in excinfo.value.hint, "the rejection hands back the form that works"


def test_a_message_id_reads_the_same_from_a_number_and_from_a_string() -> None:
    """A search hit builds the id from the int the app sent and a model hands it back as text."""
    assert (
        ids.encode_message("abcd1234", 42)
        == "message:abcd1234:42"
        == ids.encode_message("abcd1234", "42")
    )
    assert ids.parse("message:abcd1234:42") == ("message", ("abcd1234", "42"))


def test_a_table_id_reads_the_same_from_a_number_and_from_a_string() -> None:
    """``tables_browse`` builds the id from an int and a model hands it back as text."""
    assert ids.encode_table(7) == "table:7" == ids.encode_table("7")
    assert ids.parse("table:7") == ("table", ("7",))


def test_a_zero_is_a_number_for_both_new_kinds_and_the_app_decides_the_rest() -> None:
    """Refusing a zero would be a statement about a database, not about a form (as with mail)."""
    assert ids.parse("table:0") == ("table", ("0",))
    assert ids.parse("message:abcd1234:0") == ("message", ("abcd1234", "0"))


@pytest.mark.parametrize(
    "raw",
    [
        "message:abcd1234",
        "message:abcd1234:x",
        "message:abcd1234:-1",
        "message:ABC:1",
        "message:abc:1",
        "message::1",
        "message:abcd1234:1:2",
        "message:",
        "message:abcd1234:٤٢",
        "message:abcd1234:²",
    ],
)
def test_a_talk_message_id_of_the_wrong_shape_is_refused_without_a_request(raw: str) -> None:
    """Not a single request may leave for one of these (threat T-11-03).

    ``message:ABC:1`` and ``message:abc:1`` are the two halves of the token guard: the token
    alphabet is lowercase and at least four characters long, so an uppercase or a three
    character segment is not a token the Talk app ever handed out. ``message:abcd1234:1:2``
    shows why the split has ``maxsplit=1``: a third segment must not silently disappear.
    """
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)

    assert "message:" in excinfo.value.hint, "the rejection hands back the form that works"
    assert "table:" in excinfo.value.hint


@pytest.mark.parametrize(
    "raw",
    [
        "table:abc",
        "table:7a",
        "table:-1",
        "table:",
        "table:7:8",
        "table:٤٢",
        "table:²",
    ],
)
def test_a_table_id_that_is_not_a_number_is_refused_without_a_request(raw: str) -> None:
    """The WR-04 pair applies here too: ``str.isdigit`` is true for both of the last two."""
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)

    assert "table:" in excinfo.value.hint
    assert "message:" in excinfo.value.hint


def test_the_hint_every_tool_prints_names_all_nine_forms() -> None:
    """The hint is contract: it is what a caller reads after any id was refused anywhere."""
    forms = ("file:", "note:", "card:", "event:", "mail:", "message:", "table:", "task:", "url:")
    for form in forms:
        assert form in ids._HINT, form
    assert "task:<list>:<object>" in ids._HINT


def test_short_card_form_is_accepted() -> None:
    """Unified search only returns a cardId, without board and stack."""
    assert ids.parse("card:99") == ("card", ("99",))


def test_url_keeps_colons_and_slashes() -> None:
    kind, parts = ids.parse("url:https://nc.test:8443/index.php/apps/deck/#/board/1")
    assert kind == "url"
    assert parts == ("https://nc.test:8443/index.php/apps/deck/#/board/1",)


def test_the_url_kind_reads_exactly_what_encode_url_can_build() -> None:
    """The boundary in both directions, because one rejection alone does not say where it is.

    ``encode_url`` strips and refuses an empty value, so a rest with leading whitespace is a
    value it can never have built and ``parse`` must not hand it back (review finding IN-04).
    Inner whitespace is the other side of the same statement: ``encode_url("https://a b")``
    builds that id, so refusing it here would be stricter than the encode side.
    """
    assert ids.parse("url:https://a b") == ("url", ("https://a b",))

    built = ids.encode_url("   https://x/y   ")
    assert built == "url:https://x/y"
    assert ids.parse(built) == ("url", ("https://x/y",))


@pytest.mark.parametrize(
    "raw",
    [
        "garbage",
        "",
        ":",
        "file:",
        "unknown:1",
        "note:",
        "card:",
        "card:1:2",
        "card:1:2:3:4",
        "event:personal",
        "task:a",
        "task::b",
        "task:a:",
        "url:",
        # The whitespace half of the url kind: a rest that is only whitespace, and a rest that
        # begins with whitespace. Neither is a value ``encode_url`` can build, because it
        # strips (review finding IN-04).
        "url:   ",
        "url:  https://x/y",
        "url:\thttps://x",
    ],
)
def test_invalid_ids_raise_toolerror_with_hint(raw: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)
    assert excinfo.value.hint, "every rejection must carry an actionable hint"


@pytest.mark.parametrize(
    "raw",
    [
        "note:4:2",
        "file:a:b",
        "event:a:b:c",
        "task:a:b:c",
    ],
)
def test_an_id_the_encode_side_can_never_have_built_is_refused(raw: str) -> None:
    """The url yardstick for the three remaining kinds (review finding WR-03).

    ``_join`` refuses the separator inside every segment, so none of these three ids can
    have come out of this module: ``note:4:2`` and ``file:a:b`` would need a separator
    inside the one segment, and ``event:a:b:c`` a third segment the encoder does not have.
    Each of them used to parse, cost a request one layer down and came back as a 404; the
    refusal here is the zero-request answer the mail and table kinds already give.
    """
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)

    assert excinfo.value.hint, "every rejection must carry an actionable hint"


def test_encode_rejects_empty_parts() -> None:
    for call in (
        lambda: ids.encode_file(""),
        lambda: ids.encode_note(""),
        lambda: ids.encode_card("1", "", "3"),
        lambda: ids.encode_card_short(""),
        lambda: ids.encode_event("", "x.ics"),
        lambda: ids.encode_mail(""),
        lambda: ids.encode_message("", "42"),
        lambda: ids.encode_message("abcd1234", ""),
        lambda: ids.encode_table(""),
        lambda: ids.encode_task("", "x.ics"),
        lambda: ids.encode_task("tasks", ""),
        lambda: ids.encode_url(""),
    ):
        with pytest.raises(ToolError):
            call()


def test_encode_rejects_separator_inside_a_part() -> None:
    """A colon inside an id would make ``parse`` ambiguous.

    ``encode_card_short`` is in this list by name (review finding WR-06): the comment at
    ``provider_map.extract_id`` leans on exactly these ``_join`` refusals, so they are
    pinned here directly instead of only through the provider table.
    """
    with pytest.raises(ToolError):
        ids.encode_note("4:2")
    with pytest.raises(ToolError):
        ids.encode_event("per:sonal", "x.ics")
    with pytest.raises(ToolError):
        ids.encode_card_short("9:9")


def test_encode_task_rejects_a_separator_in_the_object_name() -> None:
    """A foreign object named ``a:b.ics`` cannot get an id; the tool layer skips it (TASK-02)."""
    with pytest.raises(ToolError) as excinfo:
        ids.encode_task("tasks", "a:b.ics")
    assert excinfo.value.reason == REASON_GUARD_TRIPPED


@pytest.mark.parametrize("raw", ["task:a", "task:a:b:c", "task::b"])
def test_a_task_id_of_the_wrong_shape_is_a_guard_refusal(raw: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        ids.parse(raw)
    assert excinfo.value.reason == REASON_GUARD_TRIPPED
    assert "task:" in excinfo.value.hint


# --------------------------------------------------------------------------------------
# The neutral key of a shared task list (D-32-14)
# --------------------------------------------------------------------------------------


def test_the_key_of_an_own_list_is_its_uri() -> None:
    assert ids.task_list_key("tasks") == "tasks"
    assert ids.task_list_key("projekt alpha") == "projekt alpha"


def test_the_key_of_a_shared_list_carries_no_account_id() -> None:
    uri = "spike30-b-rw_shared_by_bob"
    expected = "s" + hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]

    key = ids.task_list_key(uri)

    assert key == expected
    assert len(key) == 17
    assert re.fullmatch(r"s[0-9a-f]{16}", key)
    assert "bob" not in key
    assert "_shared_by_" not in key
    assert ids.task_list_key(uri) == key, "deterministic"
    assert ids.task_list_key("spike30-b-ro_shared_by_bob") != key


def test_a_task_id_roundtrips_for_an_own_and_for_a_shared_list() -> None:
    for key in ("tasks", ids.task_list_key("spike30-b-rw_shared_by_bob")):
        encoded = ids.encode_task(key, "a b.ics")
        assert ids.parse(encoded) == ("task", (key, "a b.ics"))
        assert "bob" not in encoded
