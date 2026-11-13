"""CalDAV client for task lists: discovery, VTODO queries, one read and the task wording.

The tasks bundle talks to the same CalDAV home as the calendar bundle, and the promise of
phase 32 is that the calendar bundle does not change by a single byte (TASK-01). That is why
this module has a discovery of its own, with its own PROPFIND body, its own reader of the
Multi-Status and its own status check, and only calls the URL builders and the one
create-only writer of ``caldav.py`` instead of extending anything there.

**What a task list is.** A collection of the calendar home that has the resourcetype
``calendar`` and ``VTODO`` in its component set. Excluded before that, in this order: Deck
calendars (URI prefix ``app-generated--``; their type and components look exactly like a task
list, E9), the trash bin, deleted calendars, the scheduling inbox and outbox, and
subscriptions. An account without any task list is a result and not an error (E6), and so is
a home that answers 404.

**Shared lists carry personal data.** Nextcloud writes the person who shared a list into it
twice: the URI reads ``<uri>_shared_by_<account id>`` and the display name
``<name> (<display name of the owner>)``. Neither leaves this module as text (D-32-06,
D-32-14). Every list gets a ``key`` (the URI for an own list, a neutral hash for a shared
one, see ``ids.task_list_key``), and the name of a shared list drops the owner suffix, which
is recognised through the ``owner-displayname`` property and never printed. ``TaskList.uri``
exists for request URLs only. The same suffix leaves the subline of a hit of the search
provider ``tasks`` through :func:`clean_subline` (D-32-17).

**Lists the account shares itself.** An own list that the account has shared with other
people or published by link is visible to others, and ``tasks_create`` never writes into it
unless it is named (D-32-18). Plan 32-09 measured on Nextcloud 32 and 35, under an app
password and under impersonation alike, that ``oc:invite`` stands in the 2xx propstat of
every own list: empty while nobody else sees the list, one ``oc:user`` per share and one for
a public link. ``cs:publish-url`` is asked as a second mark of a public link. The entries are
only counted, never kept, and an own list whose ``oc:invite`` is not readable counts as
shared. ``shared`` keeps its meaning (shared into the account); ``shared_out`` is internal.

**Write permission is read, never tried.** ``writable`` comes from ``oc:read-only`` and the
privilege set of the discovery (D-32-06): a read only share answers a PUT with 404, so a
write attempt would not even give a clear answer.

Every request body is built with lxml; there is no XML literal in this file (T-01-45).
"""

from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

import httpx
from lxml import etree

from ... import config, ids
from ...errors import (
    REASON_GUARD_TRIPPED,
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ToolError,
)
from ..credentials import Credentials
from . import caldav, xml

#: The namespace of ``owner-displayname`` and of the trash bin and deleted calendar types.
#: Not ``xml.NC``: that one is ``http://nextcloud.org/ns``, and the sharing plugin of the
#: dav app answers under ``.com``.
NS_NEXTCLOUD_COM = "http://nextcloud.com/ns"

#: The URI prefix of the calendars the Deck app generates for its boards (E9).
DECK_PREFIX = "app-generated--"

#: The marker Nextcloud puts between the URI of a shared list and the account id of its owner.
SHARED_MARKER = ids.SHARED_BY_MARKER

#: Privileges that allow creating an object, decided in plan 32-02 on Nextcloud 32 and 35:
#: at least one of them. ``write-properties`` does not count, it also stands on read only
#: shares and on Deck calendars.
WRITE_PRIVILEGES = frozenset({"write", "write-content", "bind", "all"})

#: The properties a sub task query and a parent lookup may match on.
RELATED_PROPERTIES = ("RELATED-TO", "UID")

#: The collation of every text-match, decided in plan 32-02: it found the same objects as the
#: form without collation on SQLite, PostgreSQL and Nextcloud 35, and it compares bytes. The
#: match is still "contains" on the server, so the caller checks every hit exactly.
TEXT_MATCH_COLLATION = "i;octet"

_COMPONENT_TODO = "VTODO"
_TRASH_URI = "trashbin"
_SCHEDULING_URIS = ("inbox", "outbox")
_EXCLUDED_TYPES = frozenset(
    {"trash-bin", "deleted-calendar", "schedule-inbox", "schedule-outbox", "subscribed"}
)
_NOT_READ_ONLY = ("", "0", "false")
_SEARCH_HINT = "Call tasks_search once to see the task lists of this account."
#: The marks of an own list the account shares itself, decided in plan 32-09 (D-32-18).
_INVITE = f"{{{xml.OC}}}invite"
_PUBLISH_URL = f"{{{xml.CS}}}publish-url"


@dataclass(frozen=True, slots=True)
class TaskList:
    """One task list the account can see.

    ``uri`` is for request URLs only. For a shared list it carries the account id of the
    person who shared it, so it must never reach an answer, a message or a log line; ``key``
    and ``name`` are the two values that may.

    ``owner_suffix`` is the suffix `` (<owner>)`` the name rule of D-32-14 recognised and
    removed, empty for an own list and when the rule did not match. It leaves this module
    only through :func:`clean_subline`, never as text. ``shared_out`` marks an own list the
    account shares with others or publishes (D-32-18), always false for a list shared into
    the account. None of these three is in the repr.
    """

    uri: str = field(repr=False)
    key: str
    name: str
    shared: bool
    writable: bool
    owner_suffix: str = field(default="", repr=False)
    shared_out: bool = field(default=False, repr=False)

    @property
    def own(self) -> bool:
        return not self.shared


@dataclass(frozen=True, slots=True)
class TodoObject:
    """One object of a task list: its name from the href and its raw iCalendar bytes."""

    object_name: str
    ics: bytes


#: The sentences of the create-only writer for tasks. The label is always the name of the
#: list (never the URI of a shared one), and the 404 sentence does not claim the list is
#: gone: a read only share answers a PUT with 404 (D-31-09).
TASK_WORDING = caldav.WriteWording(
    replaced=(
        "Nextcloud reports that the write replaced an existing task {name} (status {status})."
    ),
    replaced_hint=(
        "This server sends If-None-Match: * and expects a refusal instead. Report "
        "this instance: it does not honour the precondition."
    ),
    exists="A task object named {name} already exists.",
    exists_hint="This server never overwrites tasks. Create the task again under a new name.",
    forbidden="No permission to write to the task list {label}.",
    forbidden_hint=(
        "Name a list you can write to with list=...; tasks_search shows which lists are writable."
    ),
    missing="The task list {label} was not found or does not allow writing.",
    missing_hint=(
        "Call tasks_search once to see the task lists of this account and which of them are "
        "writable."
    ),
    unsupported="Nextcloud rejected the task as an unsupported media type.",
    unsupported_hint="This is a bug in this connector; please report it with the task data.",
    what="the task list {label}",
    unexpected="Nextcloud answered the new task with an unexpected status {status}.",
    unexpected_hint=(
        "Check the Nextcloud log for that request; the task was probably not created."
    ),
)


def build_task_discovery_body() -> bytes:
    """The PROPFIND body of the task list discovery.

    A body of its own: the calendar discovery asks for less and must stay as it is.
    ``oc:invite`` and ``cs:publish-url`` tell an own list the account shares (D-32-18).
    """
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "c": xml.CAL, "oc": xml.OC, "cs": xml.CS, "nx": NS_NEXTCLOUD_COM},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    etree.SubElement(prop, f"{{{xml.CAL}}}supported-calendar-component-set")
    etree.SubElement(prop, f"{{{xml.DAV}}}current-user-privilege-set")
    etree.SubElement(prop, f"{{{xml.OC}}}read-only")
    etree.SubElement(prop, f"{{{NS_NEXTCLOUD_COM}}}owner-displayname")
    etree.SubElement(prop, _INVITE)
    etree.SubElement(prop, _PUBLISH_URL)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def discover_task_lists(client: httpx.AsyncClient, creds: Credentials) -> list[TaskList]:
    """List the task lists of the account, own and shared, in one request.

    No task list is an empty list and not an error (E6). That includes a calendar home that
    answers 404: plan 32-02 measured a 207 without any collection for an account that never
    logged in, and a 404 means the same for the caller (pitfall 13).
    """
    home = caldav.calendars_home_url(creds)
    response = await client.request(
        "PROPFIND",
        home,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=build_task_discovery_body(),
        auth=creds.auth(),
    )
    if response.status_code == 404:
        return []
    _check(response, "the task lists")
    return parse_task_home(response.content, home_path=urlsplit(home).path)


def parse_task_home(body: str | bytes, home_path: str = "") -> list[TaskList]:
    """Read the discovery Multi-Status and keep the task lists, own and shared."""
    root = xml.parse_root(body)
    if root.tag != f"{{{xml.DAV}}}multistatus":
        raise ToolError(
            message="Expected a DAV Multi-Status response for the task lists.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )

    home = (home_path or "").rstrip("/")
    found: list[TaskList] = []
    for response in root.findall(f"{{{xml.DAV}}}response"):
        href = (response.findtext(f"{{{xml.DAV}}}href") or "").strip()
        path = urlsplit(href).path.rstrip("/")
        if not path or (home and path == home):
            continue
        uri = unquote(path.rsplit("/", 1)[-1])
        if not uri:
            continue

        props = _collect_props(response)
        if not _is_task_list(uri, props):
            continue

        read_only = props.get(f"{{{xml.OC}}}read-only")
        read_only_text = (read_only.text or "").strip().lower() if read_only is not None else ""
        # Either mark makes a list shared, and the stricter reading wins: the read-only
        # property stands in a 2xx propstat only on a share, and the marker in the URI is
        # what puts the account id of the owner there in the first place.
        shared = read_only is not None or SHARED_MARKER in uri
        writable = read_only_text in _NOT_READ_ONLY and bool(WRITE_PRIVILEGES & _privileges(props))
        key = ids.task_list_key(uri)
        name, owner_suffix = _list_name(uri, key, props, shared=shared)
        found.append(
            TaskList(
                uri=uri,
                key=key,
                name=name,
                shared=shared,
                writable=writable,
                owner_suffix=owner_suffix,
                shared_out=False if shared else _shares_itself(props),
            )
        )
    return found


def _shares_itself(props: dict[str, etree._Element]) -> bool:
    """Whether an own list is shared with others or published, by the measured marks.

    ``oc:invite`` outside a 2xx propstat means the state is not readable, and then the list
    counts as shared (point 6 of D-32-18). Only counted: no entry is kept or returned.
    """
    invite = props.get(_INVITE)
    if invite is None:
        return True
    if any(
        isinstance(child.tag, str) and etree.QName(child).localname == "user" for child in invite
    ):
        return True
    published = props.get(_PUBLISH_URL)
    if published is None:
        return False
    return bool((published.text or "").strip()) or any(
        isinstance(child.tag, str) and (child.text or "").strip() for child in published
    )


def _collect_props(response: etree._Element) -> dict[str, etree._Element]:
    """Every property of every 2xx propstat of one response.

    All of them and not only the first: ``oc:read-only`` tells a share by standing in a 2xx
    propstat, while an own list reports it in the 404 propstat.
    """
    props: dict[str, etree._Element] = {}
    for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
        if " 2" not in (propstat.findtext(f"{{{xml.DAV}}}status") or ""):
            continue
        for child in propstat.findall(f"{{{xml.DAV}}}prop/*"):
            if isinstance(child.tag, str):
                props[child.tag] = child
    return props


def _local_names(element: etree._Element | None) -> set[str]:
    if element is None:
        return set()
    return {etree.QName(child).localname for child in element if isinstance(child.tag, str)}


def _privileges(props: dict[str, etree._Element]) -> set[str]:
    privilege_set = props.get(f"{{{xml.DAV}}}current-user-privilege-set")
    names: set[str] = set()
    if privilege_set is not None:
        for privilege in privilege_set:
            if isinstance(privilege.tag, str):
                names |= _local_names(privilege)
    return names


def _is_task_list(uri: str, props: dict[str, etree._Element]) -> bool:
    """The order of exclusion measured in the spike of phase 30, Deck first."""
    if uri.startswith(DECK_PREFIX):
        return False
    resourcetype = props.get(f"{{{xml.DAV}}}resourcetype")
    if uri == _TRASH_URI or uri in _SCHEDULING_URIS or _local_names(resourcetype) & _EXCLUDED_TYPES:
        return False
    if resourcetype is None or resourcetype.find(f"{{{xml.CAL}}}calendar") is None:
        return False
    component_set = props.get(f"{{{xml.CAL}}}supported-calendar-component-set")
    if component_set is None:
        return False
    components = {
        (child.get("name") or "").upper() for child in component_set if isinstance(child.tag, str)
    }
    return _COMPONENT_TODO in components


def _list_name(
    uri: str, key: str, props: dict[str, etree._Element], *, shared: bool
) -> tuple[str, str]:
    """The name of a list as a person sees it, without the owner of a shared one.

    Own list: the display name, or the URI when there is none. Shared list: the display name
    without exactly `` (<owner-displayname>)`` at its end, the rule plan 32-02 measured on
    Nextcloud 32 and 35. When that suffix does not match or the owner name is missing, the
    raw display name is never used; the name is then the part of the URI before the share
    marker, and the key when nothing is left of it.

    The second value is the suffix that was removed, empty whenever the rule did not carry;
    :func:`clean_subline` needs it and nothing else may print it (D-32-17).
    """
    display_element = props.get(f"{{{xml.DAV}}}displayname")
    display = (display_element.text or "").strip() if display_element is not None else ""
    if not shared:
        return display or uri, ""

    owner_element = props.get(f"{{{NS_NEXTCLOUD_COM}}}owner-displayname")
    owner = (owner_element.text or "").strip() if owner_element is not None else ""
    if owner:
        suffix = f" ({owner})"
        if display.endswith(suffix):
            stripped = display[: -len(suffix)].strip()
            if stripped:
                return stripped, suffix
    fallback = uri.split(SHARED_MARKER, 1)[0].strip()
    return fallback or key, ""


def clean_subline(subline: str, task_list: TaskList) -> str | None:
    """The subline of a search provider hit from a shared list, without its owner (D-32-17).

    Nextcloud 34 and 35 append `` (<display name of the list>)`` to the subline, and the
    display name of a shared list ends with the owner (measured in plan 32-09). When the
    subline ends with the raw name, that end becomes `` (<name>)``. A subline that ends
    otherwise and names neither the owner nor the share marker stays as it is (the form of
    Nextcloud 32, the due date only). ``None`` in every other case: an own list, a suffix the
    name rule did not recognise, or the owner still in the text after the replacement. The
    caller then drops the line rather than pass it on unchecked.
    """
    suffix = task_list.owner_suffix
    if not task_list.shared or len(suffix) < 4:
        return None
    owner = suffix[2:-1].casefold()
    raw_tail = f" ({task_list.name}{suffix})"
    cleaned = subline
    if subline.endswith(raw_tail):
        cleaned = f"{subline[: -len(raw_tail)]} ({task_list.name})"
    if owner in cleaned.casefold() or SHARED_MARKER in cleaned:
        return None
    return cleaned


def build_todo_query(completed: bool | None = None) -> bytes:
    """A ``calendar-query`` for the VTODOs of one list, without time-range and expansion.

    ``completed=None`` asks for every task; ``False`` only for tasks without ``COMPLETED``,
    the filter the Tasks app uses for open tasks (it still lets cancelled tasks through, the
    caller sorts those out); ``True`` only for tasks that carry ``COMPLETED``.
    """
    root, todo = _todo_query_root()
    if completed is not None:
        completed_filter = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name="COMPLETED")
        if not completed:
            etree.SubElement(completed_filter, f"{{{xml.CAL}}}is-not-defined")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def build_related_query(prop: str, value: str) -> bytes:
    """A ``calendar-query`` for the VTODOs whose ``RELATED-TO`` or ``UID`` contains ``value``.

    The server matches "contains", so a hit is a candidate and the caller checks it exactly.
    """
    if prop not in RELATED_PROPERTIES:
        raise ValueError(f"prop must be one of {', '.join(RELATED_PROPERTIES)}, not {prop!r}")
    if not (value or "").strip():
        raise ToolError(
            message="A task without a UID cannot be matched to other tasks.",
            hint=_SEARCH_HINT,
            reason=REASON_GUARD_TRIPPED,
        )
    root, todo = _todo_query_root()
    matched = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name=prop)
    match = etree.SubElement(
        matched,
        f"{{{xml.CAL}}}text-match",
        attrib={"collation": TEXT_MATCH_COLLATION, "match-type": "contains"},
    )
    match.text = value
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _todo_query_root() -> tuple[etree._Element, etree._Element]:
    root = etree.Element(f"{{{xml.CAL}}}calendar-query", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop, f"{{{xml.CAL}}}calendar-data")
    scope = etree.SubElement(root, f"{{{xml.CAL}}}filter")
    vcalendar = etree.SubElement(scope, f"{{{xml.CAL}}}comp-filter", name="VCALENDAR")
    todo = etree.SubElement(vcalendar, f"{{{xml.CAL}}}comp-filter", name=_COMPONENT_TODO)
    return root, todo


async def query_todos(
    client: httpx.AsyncClient, creds: Credentials, task_list: TaskList, body: bytes
) -> list[TodoObject]:
    """Send one ``calendar-query`` to one list and return the objects unparsed.

    The object name comes from the href and never from the UID: the UID is content, the name
    is the address. Parsing is the job of the caller, which skips a damaged object instead of
    losing the whole list.
    """
    response = await client.request(
        "REPORT",
        caldav.calendar_url(creds, task_list.uri),
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=body,
        auth=creds.auth(),
    )
    _check(response, f"the task list {task_list.name}")

    root = xml.parse_root(response.content)
    if root.tag != f"{{{xml.DAV}}}multistatus":
        raise ToolError(
            message="Expected a DAV Multi-Status response for the tasks.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )
    found: list[TodoObject] = []
    for entry in root.findall(f"{{{xml.DAV}}}response"):
        href = (entry.findtext(f"{{{xml.DAV}}}href") or "").strip()
        path = urlsplit(href).path
        # An href that ends with a slash names a collection, never an object of the list.
        object_name = "" if path.endswith("/") else unquote(path.rsplit("/", 1)[-1])
        if not object_name:
            continue
        data = _collect_props(entry).get(f"{{{xml.CAL}}}calendar-data")
        text = data.text if data is not None else None
        if not text or not text.strip():
            continue
        found.append(TodoObject(object_name=object_name, ics=text.encode("utf-8")))
    return found


async def get_todo(
    client: httpx.AsyncClient, creds: Credentials, task_list: TaskList, object_name: str
) -> bytes:
    """GET one object of a task list and return its raw iCalendar bytes."""
    response = await client.get(
        caldav.object_url(creds, task_list.uri, object_name),
        headers={"Accept": "text/calendar"},
        auth=creds.auth(),
    )
    _check(response, f"the task {object_name} in the list {task_list.name}")
    return response.content


def _check(response: httpx.Response, what: str) -> None:
    """Translate a Nextcloud status into message plus hint. No retry, ever.

    ``what`` is built from the name of a list, never from its URI. The hints name only tools
    of this bundle, because the other bundles may be switched off.
    """
    status = response.status_code
    if status in (200, 207):
        return
    if 300 <= status < 400:
        raise ToolError(
            message=f"Nextcloud answered the request for {what} with a redirect ({status}).",
            hint=config.REDIRECT_HINT,
        )
    if status == 401:
        raise ToolError(
            message="Nextcloud rejected the app password.",
            hint=(
                "Generate a new app password in Nextcloud under Settings, Security, "
                "Devices and sessions, then restart the MCP server."
            ),
        )
    if status == 403:
        raise ToolError(
            message=f"No permission to read {what}.",
            hint="Ask the owner of that task list for read permission in Nextcloud.",
            reason=REASON_PERMISSION_DENIED,
        )
    if status == 404:
        raise ToolError(
            message=f"Nextcloud does not know {what}.",
            hint=_SEARCH_HINT,
            reason=REASON_UNKNOWN_ID,
        )
    if status == 429:
        raise ToolError(
            message="Nextcloud is rate limiting this server.",
            hint="Wait about a minute before the next call; do not repeat it immediately.",
        )
    if status >= 500:
        raise ToolError(
            message=f"Nextcloud reported a server error ({status}) for {what}.",
            hint="This is a problem on the Nextcloud side. Retry later or check its log.",
        )
    raise ToolError(
        message=f"Nextcloud answered with an unexpected status {status} for {what}.",
        hint="Retry once; if it persists, check the Nextcloud log for that request.",
    )
