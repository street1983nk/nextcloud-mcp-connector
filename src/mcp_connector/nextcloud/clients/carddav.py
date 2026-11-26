"""CardDAV client: address book discovery and a server side filtered ``addressbook-query``.

Three decisions carry this module.

**The path has a ``users/`` segment.** Address books live under
``addressbooks/users/<uid>/<addressbookUri>/`` while calendars live under
``calendars/<uid>/<calendarUri>/``. The address book root is a plain collection named
``users`` below ``addressbooks``, and the difference is a classic source of a 404 that
reads like "this account has no contacts". Verified against
``apps/dav/lib/RootCollection.php`` and ``CardDAV/AddressBookRoot.php``.

**The server filters, not this process.** The query carries one filter with a
``text-match`` per property and a result limit, so a large address book stays a small
answer (threat T-01-58). Downloading every card and matching locally would be both slower
and less correct: the ``i;unicode-casemap`` collation is the server's job.

**Every request body is built with lxml and every card is read with vobject.** A search
term that contains ``&`` or ``<`` cannot close a tag this way (threat T-01-53), and RFC
6350 escaping, line folding and multi value properties stay with the library that knows
them (D-17, threat T-01-55). There is no XML literal and no regular expression in this
file.

This module only reads. It sends PROPFIND and REPORT and nothing else, which the unit
tests assert by grep: contacts have no write path in this phase (threat T-01-57).
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
import vobject
from lxml import etree
from vobject.base import ParseError

from ... import config
from ...errors import REASON_PERMISSION_DENIED, REASON_UNKNOWN_ID, ToolError
from ..credentials import Credentials
from . import xml

#: Everything below the CardDAV root of one user. The ``users/`` segment is not a typo.
DAV_ADDRESSBOOKS_PREFIX = "/remote.php/dav/addressbooks/users/"

#: sabre accepts ``anyof`` and ``allof`` here and answers 400 for anything else.
FILTER_TEST = "anyof"

#: Case and accent insensitive matching, as the CardDAV default collation prescribes.
COLLATION = "i;unicode-casemap"

#: The properties a search term is matched against. Order is the order in the body.
SEARCH_PROPERTIES = ("FN", "EMAIL")

#: URI prefixes of the address books Nextcloud generates for every account: the system
#: directory of all accounts and the "recently contacted" collection of the Contacts
#: interaction app. Neither is a book the user created (see :func:`parse_addressbook_home`).
GENERATED_PREFIXES = ("z-server-generated--", "z-app-generated--")

_URI_HINT = (
    "Use an address book exactly as contacts_search reports it, for example 'contacts'. "
    "An address book name is one path segment, not a path."
)

_NO_ADDRESSBOOK = (
    "No address book found for this account.",
    (
        "Open the Contacts app once in the Nextcloud web interface, or ask an administrator "
        "to run 'occ dav:create-addressbook <user> contacts'."
    ),
)

_TERM_HINT = "Give at least one word, for example a last name or a part of a mail address."


@dataclass(frozen=True, slots=True)
class AddressBookRef:
    """One address book of the user: its URI on the wire and its name for humans."""

    uri: str
    display_name: str


def addressbooks_home_url(creds: Credentials) -> str:
    """The CardDAV home collection of the authenticated user."""
    return f"{creds.base_url}{DAV_ADDRESSBOOKS_PREFIX}{quote(creds.account, safe='')}/"


def addressbook_url(creds: Credentials, addressbook_uri: str) -> str:
    """The URL of one address book collection, with the URI checked and quoted."""
    segment = safe_segment(addressbook_uri, "address book")
    return f"{addressbooks_home_url(creds)}{quote(segment, safe='')}/"


def safe_segment(value: str, what: str) -> str:
    """Return a single path segment or raise (threat T-01-59, path traversal).

    Runs before the URL is built, so a name with a separator never becomes a path. The
    tool layer additionally only ever passes URIs that the discovery reported, so this is
    the second of two locks on the same door.
    """
    raw = (value or "").strip()
    if not raw:
        raise ToolError(message=f"No {what} was given.", hint=_URI_HINT)
    if raw in (".", ".."):
        raise ToolError(message=f"{raw!r} is not an {what} name.", hint=_URI_HINT)
    if "/" in raw or "\\" in raw:
        raise ToolError(
            message=f"The {what} name {raw!r} contains a path separator.",
            hint=_URI_HINT,
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ToolError(
            message=f"The {what} name contains a control character.",
            hint=_URI_HINT,
        )
    return raw


def build_discovery_body() -> bytes:
    """Build the PROPFIND body of the address book discovery."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "card": xml.CARD},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def build_addressbook_query(term: str, limit: int) -> bytes:
    """Build the ``addressbook-query`` body for one search term.

    Exactly one filter element, because sabre parses one and answers 400 for a second.
    The term itself never becomes markup: lxml writes it as text and escapes it.
    """
    needle = (term or "").strip()
    if not needle:
        raise ToolError(message="The search term is empty.", hint=_TERM_HINT)
    if limit < 1:
        raise ToolError(
            message=f"The result limit must be at least 1 (got {limit}).",
            hint="Leave the limit out to use the default.",
        )

    root = etree.Element(f"{{{xml.CARD}}}addressbook-query", nsmap={"d": xml.DAV, "card": xml.CARD})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop, f"{{{xml.CARD}}}address-data")

    filter_element = etree.SubElement(root, f"{{{xml.CARD}}}filter", test=FILTER_TEST)
    for name in SEARCH_PROPERTIES:
        prop_filter = etree.SubElement(filter_element, f"{{{xml.CARD}}}prop-filter", name=name)
        match = etree.SubElement(
            prop_filter,
            f"{{{xml.CARD}}}text-match",
            attrib={"collation": COLLATION, "match-type": "contains"},
        )
        match.text = needle

    limit_element = etree.SubElement(root, f"{{{xml.CARD}}}limit")
    nresults = etree.SubElement(limit_element, f"{{{xml.CARD}}}nresults")
    nresults.text = str(limit)

    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def discover_addressbooks(
    client: httpx.AsyncClient, creds: Credentials
) -> list[AddressBookRef]:
    """List the address books of the user, one request.

    An account without a single address book is an error with a way out, not an empty
    list: ``occ user:add`` does not fire the event that creates the default address book,
    so "no address book" and "no matching contact" look identical from the outside
    (pitfall 3).
    """
    home = addressbooks_home_url(creds)
    response = await client.request(
        "PROPFIND",
        home,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=build_discovery_body(),
        auth=creds.auth(),
    )
    _check(response, "the address book list")

    books = parse_addressbook_home(response.content, home_path=urlsplit(home).path)
    if not books:
        message, hint = _NO_ADDRESSBOOK
        raise ToolError(message=message, hint=hint)
    return books


def parse_addressbook_home(body: str | bytes, home_path: str = "") -> list[AddressBookRef]:
    """Read a discovery Multi-Status and keep only real address book collections.

    Dropped: the home collection itself and every collection whose resource type does not
    carry ``card:addressbook``. A plain folder below the home is not an address book, and
    querying it would answer 415 instead of a useful error.

    Also dropped: the generated collections. Every account that has ever authenticated
    carries ``z-server-generated--system`` (the directory of all accounts of the instance)
    and ``z-app-generated--contactsinteraction--recent`` (whoever the user wrote to
    lately). Both are address books to sabre, and neither is a book the user keeps. Two
    reasons to leave them out here: they would make the "this account has no address book"
    case unreachable on every real server, and the account directory of a whole
    organisation is not something an assistant should receive as a side effect of a name
    search (threat T-01-56). Reading the directory on purpose is a separate decision with
    its own parameter, not a default.
    """
    root = xml.parse_root(body)
    if root.tag != f"{{{xml.DAV}}}multistatus":
        raise ToolError(
            message="Expected a DAV Multi-Status response for the address book list.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )

    home = (home_path or "").rstrip("/")
    found: list[AddressBookRef] = []
    for response in root.findall(f"{{{xml.DAV}}}response"):
        href_element = response.find(f"{{{xml.DAV}}}href")
        href = (href_element.text or "").strip() if href_element is not None else ""
        path = urlsplit(href).path.rstrip("/")
        if not path or (home and path == home):
            continue

        props = _ok_props(response)
        if props is None or not _is_addressbook(props):
            continue

        uri = unquote(path.rsplit("/", 1)[-1])
        if not uri or uri.startswith(GENERATED_PREFIXES):
            continue
        name_element = props.find(f"{{{xml.DAV}}}displayname")
        display_name = (name_element.text or "").strip() if name_element is not None else ""
        found.append(AddressBookRef(uri=uri, display_name=display_name or uri))
    return found


def _ok_props(response: etree._Element) -> etree._Element | None:
    """Return the ``d:prop`` of the 2xx propstat, or ``None`` if there is none."""
    for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
        status = propstat.find(f"{{{xml.DAV}}}status")
        text = (status.text or "") if status is not None else ""
        if text and " 2" not in text:
            continue
        prop = propstat.find(f"{{{xml.DAV}}}prop")
        if prop is not None and len(prop):
            return prop
    return None


def _is_addressbook(props: etree._Element) -> bool:
    resourcetype = props.find(f"{{{xml.DAV}}}resourcetype")
    if resourcetype is None:
        return False
    types = {str(child.tag) for child in resourcetype if isinstance(child.tag, str)}
    return f"{{{xml.CARD}}}addressbook" in types


async def query_contacts(
    client: httpx.AsyncClient,
    creds: Credentials,
    addressbook_uri: str,
    term: str,
    limit: int,
    addressbook: str | None = None,
) -> list[dict[str, Any]]:
    """Search one address book on the server and return the stable contact shape."""
    body = build_addressbook_query(term, limit)
    url = addressbook_url(creds, addressbook_uri)
    response = await client.request(
        "REPORT",
        url,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=body,
        auth=creds.auth(),
    )
    _check(response, f"the address book {addressbook_uri}")
    return parse_contacts(response.content, addressbook=addressbook or addressbook_uri)


def parse_contacts(body: str | bytes, *, addressbook: str) -> list[dict[str, Any]]:
    """Turn a Multi-Status full of ``card:address-data`` into contacts."""
    contacts: list[dict[str, Any]] = []
    for _href, props in xml.parse_multistatus(body):
        card = props.get(f"{{{xml.CARD}}}address-data")
        if not card:
            continue
        contacts.extend(parse_vcard(card, addressbook=addressbook))
    return contacts


def parse_vcard(text: str, *, addressbook: str) -> list[dict[str, Any]]:
    """Read one ``card:address-data`` payload defensively.

    Every property is optional in practice, so nothing here assumes a field exists. A card
    that cannot be read at all is an error with a hint instead of a half filled contact:
    a wrong mail address is worse than a missing one.
    """
    try:
        cards = list(vobject.readComponents(text))
    except (ParseError, ValueError, UnicodeDecodeError) as exc:
        raise ToolError(
            message=f"Nextcloud returned a contact that could not be read ({exc}).",
            hint="Open that contact in the Nextcloud Contacts app; it may be damaged.",
        ) from None

    found: list[dict[str, Any]] = []
    for card in cards:
        if getattr(card, "name", "").upper() != "VCARD":
            continue
        found.append(
            {
                "full_name": _single(card, "fn"),
                "emails": _many(card, "email"),
                "phones": _many(card, "tel"),
                "organization": _organization(card),
                "addressbook": addressbook,
                "uid": _single(card, "uid"),
            }
        )
    return found


def _entries(card: Any, name: str) -> list[Any]:
    contents = getattr(card, "contents", None)
    if not isinstance(contents, dict):
        return []
    return list(contents.get(name, []))


def _single(card: Any, name: str) -> str:
    for entry in _entries(card, name):
        value = _as_text(getattr(entry, "value", ""))
        if value:
            return value
    return ""


def _many(card: Any, name: str) -> list[str]:
    values: list[str] = []
    for entry in _entries(card, name):
        value = _as_text(getattr(entry, "value", ""))
        if value and value not in values:
            values.append(value)
    return values


def _organization(card: Any) -> str:
    """``ORG`` is a structured property: company, unit, sub unit."""
    for entry in _entries(card, "org"):
        value = getattr(entry, "value", "")
        if isinstance(value, list | tuple):
            parts = [_as_text(part) for part in value]
            joined = ", ".join(part for part in parts if part)
            if joined:
                return joined
            continue
        text = _as_text(value)
        if text:
            return text
    return ""


def _as_text(value: Any) -> str:
    if isinstance(value, list | tuple):
        return ", ".join(_as_text(part) for part in value if _as_text(part))
    return str(value).strip() if value is not None else ""


def _check(response: httpx.Response, what: str) -> None:
    """Translate a Nextcloud status into message plus hint. No retry, ever (pitfall 8)."""
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
            hint="Ask the owner of that address book for read permission in Nextcloud.",
            # Why the identifier sits at the status branches only: see the docstring of
            # ``_status_error`` in ``ocs.py`` (D-17).
            reason=REASON_PERMISSION_DENIED,
        )
    if status == 404:
        raise ToolError(
            message=f"Nextcloud does not know {what}.",
            hint="Call contacts_search without an address book to see the ones this account has.",
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
