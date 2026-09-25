"""The parameter names an audit entry may carry, one frozen set per tool.

This file names names and never values: it says which argument *names* of a tool call may
appear in an entry, and nothing here can say what was in one of them (D-06, T-18-01). It is
data only, and that is the second half of its job: no line reads a value, no function takes
an argument out of a request, because there is no function here at all. The boundary itself
is held by ``tests/contract/test_audit_surface.py``, which measures this list against the
live tool surface rather than trusting that both were kept in step by hand.
"""

from collections.abc import Mapping

#: The names whose bare mention already carries content, and which therefore never enter a
#: set above. ``content`` and ``content_base64`` on ``files_upload``, ``content`` on
#: ``notes_create`` and ``message`` on
#: ``talk_send`` are the clear three (18-RESEARCH.md:428-433): that a body was handed along
#: is trivially true for a write tool, so the name carries no information at all and would
#: stand in the entry for one reason only, to grow a value next to it one day by accident.
#: ``description``, ``location``, ``summary``, ``title`` and ``values`` join for exactly the
#: same reason: they are the payload fields of ``calendar_create_event``, ``deck_create_card``,
#: ``notes_create`` and ``tables_create_row``, the text a person typed, and the presence of
#: the payload is already said by the tool name.
FORBIDDEN_PARAMS: frozenset[str] = frozenset(
    {
        "content",
        "content_base64",
        "description",
        "location",
        "message",
        "summary",
        "title",
        "values",
    }
)

#: Every registered tool with the argument names that may be recorded as *set*, in
#: alphabetical order, taken from the measured surface of 2026-08-29 minus
#: :data:`FORBIDDEN_PARAMS`. A tool without an entry here is a failure of the contract test
#: and not a silently empty set, because an empty set would look like a decision.
#:
#: The name has to be spelled in capitals, and that is not taste:
#: ``tests/contract/test_no_destructive_calls.py:635`` takes ``target.id.isupper()`` as the
#: only exemption from the ban on module level mutable state (D-20), so a lowercase
#: ``_param_allowlist`` on module level would turn that gate red.
PARAM_ALLOWLIST: Mapping[str, frozenset[str]] = {
    "calendar_create_event": frozenset({"all_day", "calendar", "end", "start", "timezone"}),
    "calendar_list_events": frozenset({"calendar", "end", "limit", "start", "timezone"}),
    "contacts_search": frozenset({"limit", "query"}),
    "deck_browse": frozenset({"board_id", "level", "limit", "stack_id"}),
    "deck_create_card": frozenset({"board_id", "duedate", "stack_id"}),
    "fetch": frozenset({"id"}),
    "files_download": frozenset({"chunk_bytes", "offset", "path"}),
    "files_list": frozenset({"cursor", "limit", "path"}),
    "files_read": frozenset({"offset", "path"}),
    "files_search": frozenset({"cursor", "folder", "limit", "query"}),
    "files_upload": frozenset(
        {"chunk_index", "content_type", "final", "path", "total_bytes", "upload_id"}
    ),
    "mail_browse": frozenset({"account_id", "cursor", "filter", "level", "limit", "mailbox_id"}),
    "notes_create": frozenset({"category"}),
    "notes_read": frozenset({"note_id"}),
    "notes_search": frozenset({"limit", "query"}),
    "prepare_context": frozenset({"detail", "query"}),
    "search": frozenset({"query"}),
    "tables_browse": frozenset({"cursor", "level", "limit", "table_id"}),
    "tables_create_row": frozenset({"table_id"}),
    "talk_browse": frozenset({"cursor", "level", "limit", "token"}),
    "talk_send": frozenset({"token"}),
    "unified_search": frozenset({"limit", "providers", "query"}),
}
