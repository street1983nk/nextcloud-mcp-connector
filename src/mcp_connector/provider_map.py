"""Unified search entries to prefixed ids: the table and the parsing behind pitfall 10.

A unified search entry has **no** ``id`` field. ``CoreUnifiedSearchResultEntry`` carries
``title``, ``subline``, ``resourceUrl``, ``icon``, ``rounded`` and ``attributes``, and only
the files provider fills ``attributes`` with ``fileId`` and ``path``. The notes provider
ships the note id exclusively inside ``resourceUrl``, and the Deck provider is not called
``deck`` but ``search-deck-card-board`` and delivers only the ``cardId``, never board and
stack. Everything in this module follows from those four facts.

Two rules make the ids trustworthy instead of merely present:

**Never guess a kind.** A provider that is not in :data:`PROVIDER_KINDS` produces an id of
kind ``url``, and ``fetch`` answers that honestly with "open the url" instead of resolving
a Talk message as a note (threat T-01-69). The same applies inside a known provider: a
notes entry whose URL has no numeric last segment also becomes a ``url``, because a wrong
note id silently reads a different note.

**Never keep a foreign origin.** ``resourceUrl`` comes from an arbitrary installed app and
is only ever parsed, never fetched. Every URL this module returns is rebuilt from the
configured base URL, so a manipulated entry cannot point the user (or ChatGPT's citation
renderer) at another host (threat T-01-68).

The calendar provider is deliberately **not** in the table. Its entry URL addresses a day
view, not the DAV object name that ``event:<calendarUri>:<objectName>`` needs, so it would
be an id that no ``fetch`` can resolve. It stays in the ``url`` category until a real
instance shows a resolvable form.

A tables hit on a **view** stays in the ``url`` category for the same reason, and it is the
sharper case, because the two links are indistinguishable at a glance: the tables app builds
``#/table/<id>`` and ``#/view/<id>`` from one template, and the client of this project reads
tables only (``get_table``, ``get_columns`` and ``get_rows_simple`` all build a
``tables/{id}`` path). A view id passed off as a table id therefore does not fail loudly, it
reads the table that happens to carry that number (threat T-11-01), which is why
:func:`_tables_node` reads the node type together with the id and accepts only ``table``.

A **mail** hit stays ``url`` on purpose, and the reason is worth naming: ``mail:<databaseId>``
needs the database id of one message, the search entry carries a deep link into a mailbox and
a thread instead, and resolving that link to a database id is unmeasured and an explicit
future requirement. A guessed database id would not answer with an error, it would read
somebody else's mail (threat T-11-05).

``talk-conversations`` is not in the table either: a conversation is not a document, and
``talk_browse`` is the way to it.

A **tasks** hit becomes ``task:<list key>:<object>`` without a single request, and three known
limits stand beside it (K2). The provider also searches subscriptions and shared objects
without ``CLASS:PUBLIC``; such a hit still parses, and ``fetch`` refuses it through the task
discovery exactly like an unknown id, because the discovery holds neither subscriptions nor
foreign lists. Deck never reaches this provider as a task list, and a link into an
``app-generated--`` calendar stays a ``url`` anyway (E9). The URI of a shared list carries
``_shared_by_<account id>``: the id carries the neutral key of :func:`ids.task_list_key`
instead, and the link of such a hit is the start page of the Tasks app (D-32-15).
"""

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from . import ids

#: Provider id as Nextcloud reports it at runtime, mapped to our resource kind. This is a
#: translation table, never a list of installed providers: that list is fetched per call.
PROVIDER_KINDS: Mapping[str, str] = {
    # Verified against nextcloud/server v34.0.0, apps/files/lib/Search/FilesSearchProvider.php,
    # class FilesSearchProvider implements IFilteringProvider: getId returns 'files', and search
    # sets addAttribute('fileId', ...) and addAttribute('path', ...) while the link comes from
    # linkToRoute('files.View.showFile', ['fileid' => ...]). That double track is the reason
    # file_id reads attributes.fileId first and only then falls back to the /f/ segment of the
    # URL: both ways carry the same number, and one of them can be missing.
    "files": "file",
    # Verified against nextcloud/notes v6.0.2, lib/AppInfo/SearchProvider.php, class
    # SearchProvider implements IProvider: getId returns Application::APP_ID, and that constant
    # is 'notes' (lib/AppInfo/Application.php:28, read at the same tag). The second sentence is
    # the one that matters: this provider sets no attributes at all, the link is
    # linkToRouteAbsolute('notes.page.indexnote', ['id' => ...]), and that is exactly why this
    # module reads the note id with last_numeric_segment(url) instead of from an attribute.
    "notes": "note",
    # Verified against nextcloud/deck lib/Search/DeckProvider.php. "deck" is wrong.
    "search-deck-card-board": "card",
    # Verified against nextcloud/spreed lib/Search/MessageSearch.php, class MessageSearch:
    # commentToSearchResultEntry adds conversation, messageId, threadId, actorType, actorId and
    # timestamp, and links to spreed.Page.showCall with the fragment "message_" . $id.
    "talk-message": "message",
    # Verified against nextcloud/spreed lib/Search/CurrentMessageSearch.php, class
    # CurrentMessageSearch: it extends MessageSearch and overrides getId, getName, getOrder, the
    # subline template and the room selection only. Its entries are built by the inherited
    # performSearch, so they carry exactly the same attributes. Not an assumption: read.
    "talk-message-current": "message",
    # Verified against nextcloud/tables lib/Search/SearchTablesProvider.php, class
    # SearchTablesProvider: it sets no attributes at all, and getInternalLink builds
    # "#/" . $nodeType . "/" . $nodeId with $nodeType being "table" or "view".
    "tables-search-tables": "table",
    # Verified against nextcloud/server stable32 to stable35
    # apps/dav/lib/Search/TasksSearchProvider.php, class TasksSearchProvider: getId returns
    # 'tasks', it sets no attributes, and the link is linkToRoute('tasks.page.index') .
    # 'calendars/' . <calendar uri> . '/tasks/' . <object uri>. Measured on 32 and 35 in plan
    # 32-02: path form, no index.php, no percent encoding, and a shared list keeps its
    # _shared_by_<account id> URI in the link.
    "tasks": "task",
}

#: The honest rest category for everything the table does not cover.
UNKNOWN_KIND = "url"

#: Web route of a single file, used when an entry carries a fileId but no resourceUrl.
FILE_WEB_PREFIX = "/index.php/f"

#: The token alphabet of a Talk conversation, four to thirty lowercase letters and digits: the
#: path requirement every Talk route declares. A token read out of a foreign app's entry is
#: checked against it before it becomes part of an id.
_TOKEN = re.compile(r"[a-z0-9]{4,30}")

#: Digits, and only ASCII ones. ``str.isdigit`` also accepts a superscript two and an
#: Arabic-Indic digit, and both would build an id that Nextcloud never handed out. Every
#: digit check of this module measures with this pattern, including the file id and the
#: last-segment readers (review finding WR-02): an entry with ``fileId: "٤٢"`` must degrade
#: to the honest ``url`` kind instead of becoming ``file:٤٢``.
_DIGITS = re.compile(r"[0-9]+")

#: The fragment of a Talk search entry: ``message_<id>``.
_MESSAGE_FRAGMENT = re.compile(r"message_([0-9]+)")

#: The fragment of a tables search entry, node type included: ``/table/7`` or ``/view/3``.
_TABLES_NODE = re.compile(r"/?(table|view)/([0-9]+)")

#: Start page of the Tasks app, the only link a task of a shared list gets (D-32-15). The form
#: with index.php is the one plan 32-02 decided on: it opens the app on 32 and 35 and does not
#: depend on pretty URLs.
TASKS_WEB_PREFIX = "/index.php/apps/tasks/"

#: The app route of a tasks link: ``/apps/tasks/`` with or without ``/index.php`` before it, and
#: behind the web root of an instance that lives in a sub path (``/nextcloud/apps/tasks/``).
_TASKS_APP = re.compile(r"(?:/index\.php)?/apps/tasks/")

#: The task inside a tasks link, as path rest or as fragment: ``calendars/<uri>/tasks/<object>``.
_TASKS_NODE = re.compile(r"/?calendars/([^/]+)/tasks/([^/]+)")

#: The URI prefix of the calendars Deck generates; never a task list of this server (E9).
_DECK_PREFIX = "app-generated--"


def absolute_url(base_url: str, resource_url: Any) -> str:
    """Rebuild ``resource_url`` on the configured instance, or return an empty string.

    Path, query and fragment survive, the origin never does: ``#message_42`` matters for a
    Talk link, and ``http://evil.test`` must not reach the model.
    """
    if not isinstance(resource_url, str) or not resource_url.strip():
        return ""
    parts = urlsplit(resource_url.strip())
    path = parts.path
    if not path.startswith("/"):
        path = f"/{path}" if path else "/"
    return f"{base_url}{urlunsplit(('', '', path, parts.query, parts.fragment))}"


def extract_id(
    provider_id: str, entry: Mapping[str, Any], base_url: str
) -> tuple[str, str, bool] | None:
    """Return ``(kind, id, canonical)`` for one search entry, or ``None`` if it is unusable.

    ``canonical`` is false when the id cannot be handed to a read tool as it stands: the
    short card form needs a board sweep first, and a ``url`` id cannot be resolved at all.
    An entry without a usable ``resourceUrl`` and without a usable ``fileId`` carries
    nothing to build an id from and is skipped by the caller.
    """
    attributes = entry.get("attributes")
    # The psalm annotation in the server code says list<string>; the wire format is an
    # object, and an app that sets nothing sends an empty list. Both are normal.
    attributes = attributes if isinstance(attributes, dict) else {}
    url = absolute_url(base_url, entry.get("resourceUrl"))
    kind = PROVIDER_KINDS.get(provider_id, UNKNOWN_KIND)

    if kind == "file":
        fileid = file_id(attributes, url)
        if fileid:
            return "file", ids.encode_file(fileid), True
    elif kind == "note":
        note_id = last_numeric_segment(url)
        if note_id:
            return "note", ids.encode_note(note_id), True
    elif kind == "card":
        card_id = last_numeric_segment(url)
        if card_id:
            # Short form on purpose: the provider knows no board and no stack, and an
            # invented one would address a card that does not exist. The form comes from the
            # codec like every other id of this module, so the refusals of ``_join`` apply
            # here too (threat T-12-05).
            return "card", ids.encode_card_short(card_id), False
    elif kind == "message":
        target = _message_target(attributes, url)
        if target is not None:
            return "message", ids.encode_message(*target), True
    elif kind == "table":
        node = _tables_node(url)
        # Only a table, never a view: the readers of this project build "tables/{id}" paths, so
        # a view id used as a table id reads a foreign table (threat T-11-01).
        if node is not None and node[0] == "table":
            return "table", ids.encode_table(node[1]), True
    elif kind == "task":
        target = _tasks_target(url)
        if target is not None:
            uri, object_name = target
            # The key, never the URI: a shared list names its sharer in the URI (D-32-14).
            return "task", ids.encode_task(ids.task_list_key(uri), object_name), True

    if not url:
        return None
    return UNKNOWN_KIND, ids.encode_url(url), False


def hit_url(base_url: str, kind: str, identifier: str, entry: Mapping[str, Any]) -> str:
    """The link a human can open: absolute, non-empty and always on this instance.

    OpenAI only renders a citation when ``url`` is a non-empty string, so a files hit
    without a ``resourceUrl`` still gets the canonical ``/f/<fileid>`` route.
    """
    url = absolute_url(base_url, entry.get("resourceUrl"))
    if kind == "task" and ids.SHARED_BY_MARKER in url:
        # The deep link of a shared list carries the account id of the sharer (D-32-15).
        return f"{base_url}{TASKS_WEB_PREFIX}"
    if url:
        return url
    if kind == "file":
        _, parts = ids.parse(identifier)
        return f"{base_url}{FILE_WEB_PREFIX}/{parts[0]}"
    # A url id carries its own absolute link, and no other kind reaches this line without
    # a resourceUrl, because extract_id would have skipped the entry. The link is read with
    # the codec rather than split on the separator: reading an id is the codec's other half,
    # and a hand split would have handed back the bare id segment of any other kind, which is
    # not a link at all.
    read_kind, parts = ids.parse(identifier)
    return parts[0] if read_kind == UNKNOWN_KIND else base_url


def file_id(attributes: Mapping[str, Any], url: str) -> str:
    """``attributes.fileId`` first, then the ``/f/<fileid>`` segment of the URL."""
    raw = attributes.get("fileId")
    candidate = str(raw).strip() if raw is not None else ""
    if _DIGITS.fullmatch(candidate):
        return candidate

    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    for index, segment in enumerate(segments[:-1]):
        if segment == "f" and _DIGITS.fullmatch(segments[index + 1]):
            return segments[index + 1]
    return ""


def _message_target(attributes: Mapping[str, Any], url: str) -> tuple[str, str] | None:
    """``attributes.conversation`` and ``attributes.messageId`` first, the URL as the cross check.

    The same shape as :func:`file_id`, only with two values instead of one, and with the honest
    ``None`` when either half is missing after both ways: a Talk entry can arrive with
    ``attributes`` as an empty list (pitfall 7), and a guessed token or a guessed message id
    would address somebody else's conversation (threat T-11-02). ``threadId`` is deliberately
    never read: it names a thread, not a message.
    """
    raw_token = attributes.get("conversation")
    token = str(raw_token).strip() if raw_token is not None else ""
    if not _TOKEN.fullmatch(token):
        # The cross check: the web route of one conversation is ``/call/<token>``.
        segments = [segment for segment in urlsplit(url).path.split("/") if segment]
        token = ""
        for index, segment in enumerate(segments[:-1]):
            if segment == "call" and _TOKEN.fullmatch(segments[index + 1]):
                token = segments[index + 1]
                break

    raw_id = attributes.get("messageId")
    message_id = str(raw_id).strip() if raw_id is not None else ""
    if not _DIGITS.fullmatch(message_id):
        match = _MESSAGE_FRAGMENT.fullmatch(urlsplit(url).fragment)
        message_id = match.group(1) if match is not None else ""

    if not token or not message_id:
        return None
    return token, message_id


def _tables_node(url: str) -> tuple[str, str] | None:
    """Return ``(nodeType, nodeId)`` of a tables link, or ``None``.

    :func:`last_numeric_segment` is unusable here, and that is the whole point of a second
    reader: it looks at ``urlsplit(url).path`` only, while the tables app puts its node into the
    fragment (``#/table/7``). The node type is read together with the id, because ``#/view/3``
    would otherwise become ``table:3`` and read a foreign table (threat T-11-01).
    """
    match = _TABLES_NODE.fullmatch(urlsplit(url).fragment)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _tasks_target(url: str) -> tuple[str, str] | None:
    """Return ``(calendar uri, object name)`` of a tasks link, or ``None``.

    Path and fragment are read apart, like :func:`_tables_node`: the measured form puts the
    task into the path after the app route, older Tasks releases put it into the fragment after
    ``#/``. Exactly one of the two may carry it, and a query is no part of either form. Both
    segments are read with ``unquote``, because the provider sends them raw today and a proxy
    may encode them. Everything else is ``None`` and stays a ``url``: a Deck calendar (E9), a
    segment the codec would refuse, and any link that is not exactly the measured shape.
    """
    parts = urlsplit(url)
    if parts.query:
        return None
    app = _TASKS_APP.search(parts.path)
    if app is None:
        return None
    rest = parts.path[app.end() :]
    if rest and parts.fragment:
        return None
    match = _TASKS_NODE.fullmatch(rest or parts.fragment)
    if match is None:
        return None
    uri, object_name = unquote(match.group(1)), unquote(match.group(2))
    if uri.startswith(_DECK_PREFIX):
        return None
    for segment in (uri, object_name):
        if not segment.strip() or ids.SEPARATOR in segment or "/" in segment:
            return None
    return uri, object_name


def last_numeric_segment(url: str) -> str:
    """Return the trailing numeric path segment of ``url``, or an empty string."""
    path = urlsplit(url).path.rstrip("/")
    if not path:
        return ""
    candidate = path.rsplit("/", 1)[-1]
    return candidate if _DIGITS.fullmatch(candidate) else ""
