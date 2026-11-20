"""Namespace constants, a hardened XML parser and the Multi-Status reader.

Every DAV response body is untrusted input. The parser refuses entity resolution, network
access and huge trees, and ``parse_multistatus`` additionally rejects any body that
carries a document type declaration at all: Nextcloud never sends one, so a DTD means the
body is not what we asked for (threat T-01-11, XXE and billion laughs).

Request builders stay in the client module that owns the request, so later plans do not
have to touch this file.
"""

from lxml import etree

from ...errors import ToolError

DAV = "DAV:"
OC = "http://owncloud.org/ns"
NC = "http://nextcloud.org/ns"
CAL = "urn:ietf:params:xml:ns:caldav"
CARD = "urn:ietf:params:xml:ns:carddav"
CS = "http://calendarserver.org/ns/"

NSMAP = {"d": DAV, "oc": OC, "nc": NC, "c": CAL, "card": CARD, "cs": CS}

_PARSE_HINT = "This is a Nextcloud response problem, not a wrong parameter. Retry once."


def hardened_parser() -> etree.XMLParser:
    """Return a parser that cannot be talked into reading files or the network."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=False,
        load_dtd=False,
        dtd_validation=False,
        recover=False,
    )


def parse_root(body: str | bytes) -> etree._Element:
    """Parse a DAV body with every hardening on and return its root element.

    Clients that need more structure than ``parse_multistatus`` exposes (the CalDAV
    component set carries its meaning in attributes, not in text) start here, so the XXE
    and DTD guards stay in one place for every response this project reads.
    """
    payload = body.encode("utf-8") if isinstance(body, str) else body
    try:
        root = etree.fromstring(payload, parser=hardened_parser())
    except etree.XMLSyntaxError as exc:
        raise ToolError(
            message=f"Nextcloud returned XML that could not be parsed ({exc.msg}).",
            hint=_PARSE_HINT,
        ) from None

    tree = root.getroottree()
    if tree.docinfo.internalDTD is not None or tree.docinfo.externalDTD is not None:
        raise ToolError(
            message="Nextcloud response contained a document type declaration and was rejected.",
            hint="A DAV response does not need a DTD; check for a proxy rewriting responses.",
        )
    return root


def parse_multistatus(body: str | bytes) -> list[tuple[str, dict[str, str]]]:
    """Return ``[(href, {qualified-prop-name: text})]`` for every ``d:response``.

    Only ``d:propstat`` blocks with a 2xx status contribute properties; a 404 propstat
    (the usual answer for a property the file does not have) is skipped instead of
    landing in the result as an empty value.
    """
    root = parse_root(body)

    if root.tag != f"{{{DAV}}}multistatus":
        raise ToolError(
            message="Expected a DAV Multi-Status response.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )

    entries: list[tuple[str, dict[str, str]]] = []
    for response in root.findall(f"{{{DAV}}}response"):
        href_el = response.find(f"{{{DAV}}}href")
        href = (href_el.text or "").strip() if href_el is not None else ""
        props: dict[str, str] = {}
        for propstat in response.findall(f"{{{DAV}}}propstat"):
            if not _is_ok(propstat):
                continue
            prop = propstat.find(f"{{{DAV}}}prop")
            if prop is None:
                continue
            for element in prop:
                props[str(element.tag)] = _value_of(element)
        entries.append((href, props))
    return entries


def _is_ok(propstat: etree._Element) -> bool:
    status = propstat.find(f"{{{DAV}}}status")
    if status is None or not status.text:
        return True
    return " 2" in status.text


def _value_of(element: etree._Element) -> str:
    """Text for leaf properties, child tag names for structured ones (resourcetype)."""
    children = [str(child.tag) for child in element if isinstance(child.tag, str)]
    if children:
        return " ".join(children)
    return (element.text or "").strip()
