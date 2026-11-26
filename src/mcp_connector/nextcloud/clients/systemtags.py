"""System tag client: the tag listing and the nodes carrying one tag, free of any policy.

Two Nextcloud calls and nothing else. This module knows no tag name, keeps no cache and
decides nothing; the exclusion guard on top of it does all of that.

Why the REPORT goes to the home root and not through ``dav.files_url``: that helper maps
every path into ``NC_MCP_FILES_ROOT``, and the measurement of phase 25 showed that the
target path of a ``REPORT oc:filter-files`` does not narrow the answer anyway. A tagged
folder above the sandbox has to take effect on everything below it, so the question is
always asked of the whole home.

Why exactly one ``oc:systemtag`` rule per REPORT: Nextcloud's FilesReportPlugin intersects
several rules (``array_uintersect``), so two rules mean "carries both tags". Asking for
two spellings of one tag in one body would silently answer "nothing" for a node that
carries only one of them, which is fail-open. ``filter_files_body`` therefore takes a
single id and cannot be handed a sequence.

Why outcomes come back as values instead of a ``ToolError``: the guard treats 207, 412
and every other status differently (D-25-05), and a raised error would erase exactly that
difference. Only data that cannot be what Nextcloud sends raises: a non-digit id or file
id is a ``ValueError``, an unparsable body is the ``ToolError`` of ``xml.parse_multistatus``.
Transport errors from httpx are not caught here either, with one exception: a timeout of the
admin proof is "not decidable", see :func:`confirm_admin`.

No retry, ever (the rule of ``dav``: Nextcloud counts failed logins per source IP), and
the ``systemtags`` capability is never read (D-25-05): the listing itself is the only
answer that counts.

The audit reads of ``exclusion:check`` (plan 29-03) live here as well and follow the same
rules: policy-free, read-only (PROPFIND, plus one OCS GET for the admin proof), outcomes as
values. They walk the Multi-Status themselves instead of using ``xml.parse_multistatus``,
because that reader drops every non-2xx propstat, and the status of ``oc:groups`` is part
of the answer here. The hardened parser of ``xml.parse_root`` stays the only entrance.
"""

import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from ...errors import ToolError
from ..credentials import Credentials
from . import dav, ocs, xml

TAGS_PATH = "/remote.php/dav/systemtags/"

#: Digits, and only ASCII ones, the same rule as ``dav._DIGITS``: ``str.isdigit`` also
#: accepts a superscript two, and neither a tag id nor a file id ever looks like that.
_DIGITS = re.compile(r"[0-9]+")

_FILEID = f"{{{xml.OC}}}fileid"
_RESOURCETYPE = f"{{{xml.DAV}}}resourcetype"
_TAG_ID = f"{{{xml.OC}}}id"
_TAG_NAME = f"{{{xml.OC}}}display-name"
_TAG_VISIBLE = f"{{{xml.OC}}}user-visible"
_TAG_ASSIGNABLE = f"{{{xml.OC}}}user-assignable"
_TAG_GROUPS = f"{{{xml.OC}}}groups"
_OBJECT_IDS = f"{{{xml.NC}}}object-ids"
_OBJECT_TYPE = f"{{{xml.NC}}}type"
_MULTISTATUS = f"{{{xml.DAV}}}multistatus"
_RESPONSE = f"{{{xml.DAV}}}response"
_HREF = f"{{{xml.DAV}}}href"
_PROPSTAT = f"{{{xml.DAV}}}propstat"
_PROP = f"{{{xml.DAV}}}prop"
_STATUS = f"{{{xml.DAV}}}status"

#: ``HTTP/1.1 403 Forbidden`` -> ``403``.
_STATUS_LINE = re.compile(r"HTTP/[0-9.]+ ([0-9]{3})")

#: The spellings Sabre uses for a true boolean property.
_TRUE = frozenset({"true", "1"})


@dataclass(frozen=True, slots=True)
class Tag:
    """One system tag as Nextcloud lists it; the name is passed on unmodified."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class TagListing:
    """The status of the listing and, on 207 only, the tags it carried."""

    status: int
    tags: tuple[Tag, ...]


@dataclass(frozen=True, slots=True)
class TaggedNode:
    """One node carrying the tag. ``path`` is ``None`` when the href is not mappable."""

    path: str | None
    fileid: str
    is_collection: bool


@dataclass(frozen=True, slots=True)
class TaggedSet:
    """The status of one REPORT and, on 207 only, every node it named."""

    status: int
    nodes: tuple[TaggedNode, ...]


@dataclass(frozen=True, slots=True)
class TagDetail:
    """One tag with its access flags, as the audit of ``exclusion:check`` needs it.

    ``groups`` is ``None`` when the groups were not asked for or their propstat was not
    200; ``groups_status`` is that propstat status, ``None`` when not asked for or not
    answered at all.
    """

    id: str
    name: str
    visible: bool
    assignable: bool
    groups: tuple[str, ...] | None
    groups_status: int | None


@dataclass(frozen=True, slots=True)
class TagDetailListing:
    """The status of the detail listing and, on 207 only, the tags it carried."""

    status: int
    tags: tuple[TagDetail, ...]


@dataclass(frozen=True, slots=True)
class ObjectCount:
    """How many files carry one tag; ``files`` only on 207 with a readable property.

    Deliberately a number and nothing else: there is no field an object id could ever
    travel in (threat T-29-10).
    """

    status: int
    files: int | None


def home_url(creds: Credentials) -> str:
    """The WebDAV root of the user's whole home, deliberately outside the sandbox."""
    return f"{creds.base_url}{dav.DAV_FILES_PREFIX}{quote(creds.account, safe='')}/"


def filter_files_body(tag_id: str) -> bytes:
    """Build a ``REPORT oc:filter-files`` body with exactly one tag rule, with lxml."""
    if not _DIGITS.fullmatch(tag_id):
        raise ValueError(f"a tag id must be ASCII digits only (got {tag_id!r})")
    root = etree.Element(
        f"{{{xml.OC}}}filter-files",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, _FILEID)
    etree.SubElement(prop, _RESOURCETYPE)
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _listing_body() -> bytes:
    """Build the PROPFIND body of the tag listing with lxml (threat T-01-11)."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, _TAG_ID)
    etree.SubElement(prop, _TAG_NAME)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def list_tags(client: httpx.AsyncClient, creds: Credentials) -> TagListing:
    """List every system tag the user can see, with Depth 1 on the tag collection.

    The collection itself answers without ``oc:id`` and is recognised by its href; any
    other response without an id raises, because a tag whose id cannot be read must end
    in ``unverifiable``, never in ``untagged`` (the listing would otherwise be the one
    entrance where missing mandatory data is tolerated silently). Any status other than
    207 comes back as a value with no tags; what it means is the caller's decision.
    """
    response = await client.request(
        "PROPFIND",
        f"{creds.base_url}{TAGS_PATH}",
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=_listing_body(),
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return TagListing(status=response.status_code, tags=())
    tags: list[Tag] = []
    for href, props in xml.parse_multistatus(response.content):
        tag_id = props.get(_TAG_ID, "")
        if not tag_id:
            if unquote(urlsplit(href).path).rstrip("/").endswith("/systemtags"):
                continue  # the collection itself carries no oc:id
            raise ValueError(f"Nextcloud listed a tag without an id: {href!r}")
        if not _DIGITS.fullmatch(tag_id):
            raise ValueError(f"Nextcloud listed a tag id that is not ASCII digits: {tag_id!r}")
        tags.append(Tag(id=tag_id, name=props.get(_TAG_NAME, "")))
    return TagListing(status=207, tags=tuple(tags))


async def tagged_nodes(client: httpx.AsyncClient, creds: Credentials, tag_id: str) -> TaggedSet:
    """Ask the whole home for the nodes carrying one tag, with one rule in one REPORT.

    The body is built before the request, so an invalid id raises before any traffic.
    Every ``d:response`` becomes one node; a href that does not map onto the home keeps
    the path ``None`` (see ``dav.home_entries``). A node without a digit file id raises.
    """
    body = filter_files_body(tag_id)
    response = await client.request(
        "REPORT",
        home_url(creds),
        headers={"Content-Type": "application/xml"},
        content=body,
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return TaggedSet(status=response.status_code, nodes=())
    nodes: list[TaggedNode] = []
    for path, props in dav.home_entries(response.content, creds):
        fileid = props.get(_FILEID, "")
        if not _DIGITS.fullmatch(fileid):
            raise ValueError(f"Nextcloud named a tagged node without a digit file id: {fileid!r}")
        nodes.append(
            TaggedNode(
                path=path,
                fileid=fileid,
                is_collection=f"{{{xml.DAV}}}collection" in props.get(_RESOURCETYPE, ""),
            )
        )
    return TaggedSet(status=207, nodes=tuple(nodes))


def _details_body(*, with_groups: bool) -> bytes:
    """Build the PROPFIND body of the detail listing with lxml; groups only on request."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, _PROP)
    for name in (_TAG_ID, _TAG_NAME, _TAG_VISIBLE, _TAG_ASSIGNABLE):
        etree.SubElement(prop, name)
    if with_groups:
        etree.SubElement(prop, _TAG_GROUPS)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _object_ids_body() -> bytes:
    """Build the PROPFIND body that asks one tag for its ``nc:object-ids``, with lxml."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, _PROP)
    etree.SubElement(prop, _OBJECT_IDS)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _multistatus_responses(body: bytes) -> list[etree._Element]:
    """Parse with the hardened parser and return every ``d:response`` of a Multi-Status."""
    root = xml.parse_root(body)
    if root.tag != _MULTISTATUS:
        raise ToolError(
            message="Expected a DAV Multi-Status response.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )
    return list(root.iterchildren(_RESPONSE))


def _propstat_status(propstat: etree._Element) -> int:
    """The status of one propstat; a propstat without a status line counts as 200.

    That is the reading of ``xml._is_ok`` as well. A status line that is present but not
    of the form ``HTTP/x.y nnn`` cannot come from Nextcloud and raises.
    """
    text = (propstat.findtext(_STATUS) or "").strip()
    if not text:
        return 200
    match = _STATUS_LINE.match(text)
    if match is None:
        raise ValueError(f"Nextcloud sent a propstat status that is no status line: {text!r}")
    return int(match.group(1))


def _props_by_status(response: etree._Element) -> dict[str, tuple[int, etree._Element]]:
    """Map every property of one response to its propstat status and its element."""
    props: dict[str, tuple[int, etree._Element]] = {}
    for propstat in response.iterchildren(_PROPSTAT):
        status = _propstat_status(propstat)
        prop = propstat.find(_PROP)
        if prop is None:
            continue
        for element in prop:
            if isinstance(element.tag, str):
                props[element.tag] = (status, element)
    return props


def _ok_text(props: dict[str, tuple[int, etree._Element]], name: str) -> str:
    """The stripped text of a property answered with 200, else an empty string."""
    entry = props.get(name)
    if entry is None or entry[0] != 200:
        return ""
    return (entry[1].text or "").strip()


def _detail_of(
    href: str, props: dict[str, tuple[int, etree._Element]], *, with_groups: bool
) -> TagDetail | None:
    """One ``TagDetail``, or ``None`` for the collection itself (the rule of list_tags)."""
    tag_id = _ok_text(props, _TAG_ID)
    if not tag_id:
        if unquote(urlsplit(href).path).rstrip("/").endswith("/systemtags"):
            return None
        raise ValueError(f"Nextcloud listed a tag without an id: {href!r}")
    if not _DIGITS.fullmatch(tag_id):
        raise ValueError(f"Nextcloud listed a tag id that is not ASCII digits: {tag_id!r}")
    groups: tuple[str, ...] | None = None
    groups_status: int | None = None
    if with_groups and _TAG_GROUPS in props:
        groups_status = props[_TAG_GROUPS][0]
        if groups_status == 200:
            # Sabre joins the group ids with a pipe (SystemTagPlugin); empty means none.
            groups = tuple(gid for gid in _ok_text(props, _TAG_GROUPS).split("|") if gid)
    return TagDetail(
        id=tag_id,
        name=_ok_text(props, _TAG_NAME),
        visible=_ok_text(props, _TAG_VISIBLE).lower() in _TRUE,
        assignable=_ok_text(props, _TAG_ASSIGNABLE).lower() in _TRUE,
        groups=groups,
        groups_status=groups_status,
    )


async def list_tag_details(
    client: httpx.AsyncClient, creds: Credentials, *, with_groups: bool
) -> TagDetailListing:
    """List every tag the account can see, with its access flags, by PROPFIND Depth 1.

    Policy-free and read-only. ``oc:groups`` is asked for only with ``with_groups``: the
    measurement of plan 29-01 (M2) showed that a non-admin asking for it does not get a
    403 propstat but a 403 for the whole PROPFIND, so the caller must have proven admin
    rights first. Any status other than 207 comes back as a value with no tags. The id
    rules are those of :func:`list_tags`: the collection is skipped by its href, any other
    entry without a digit id raises.
    """
    response = await client.request(
        "PROPFIND",
        f"{creds.base_url}{TAGS_PATH}",
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=_details_body(with_groups=with_groups),
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return TagDetailListing(status=response.status_code, tags=())
    tags: list[TagDetail] = []
    for entry in _multistatus_responses(response.content):
        href = (entry.findtext(_HREF) or "").strip()
        detail = _detail_of(href, _props_by_status(entry), with_groups=with_groups)
        if detail is not None:
            tags.append(detail)
    return TagDetailListing(status=207, tags=tuple(tags))


async def count_tag_objects(
    client: httpx.AsyncClient, creds: Credentials, tag_id: str
) -> ObjectCount:
    """Count the files carrying one tag, by PROPFIND Depth 0 on ``nc:object-ids``.

    Policy-free and read-only, and it returns a number, never an id: the assignments are
    summed while walking, never collected. Nextcloud serialises every assignment as an
    inner ``nc:object-ids`` with ``nc:id`` and ``nc:type`` (29-01, M3); ``nc:id`` is a
    running index, not a file id. The count is instance-wide, the same for every account,
    and includes files in the trash bin (29-01, M3b and M4).

    Why not ``nc:files-assigned``: on ``/systemtags/<id>`` it always answers -1 (pitfall
    P4). Why not a ``REPORT oc:filter-files``: that counts only the asking user's own files
    and runs for minutes on SQLite. An invalid id raises before any request; a status
    other than 207, or a 207 without a readable property, leaves ``files`` at ``None``.
    """
    if not _DIGITS.fullmatch(tag_id):
        raise ValueError(f"a tag id must be ASCII digits only (got {tag_id!r})")
    response = await client.request(
        "PROPFIND",
        f"{creds.base_url}{TAGS_PATH}{tag_id}",
        headers={"Depth": "0", "Content-Type": "application/xml"},
        content=_object_ids_body(),
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return ObjectCount(status=response.status_code, files=None)
    for entry in _multistatus_responses(response.content):
        outer = _props_by_status(entry).get(_OBJECT_IDS)
        if outer is not None and outer[0] == 200:
            files = sum(
                1
                for inner in outer[1].iterchildren(_OBJECT_IDS)
                if (inner.findtext(_OBJECT_TYPE) or "").strip() == "files"
            )
            return ObjectCount(status=207, files=files)
    return ObjectCount(status=207, files=None)


#: The OCS route of the admin proof, below ``/ocs/v2.php``.
ADMIN_USERS_PATH = "/cloud/groups/admin/users"


def _ocs_statuscode(response: httpx.Response) -> int | None:
    """``ocs.meta.statuscode`` of an OCS answer, ``None`` when the body is not that shape."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    envelope = payload.get("ocs")
    meta = envelope.get("meta") if isinstance(envelope, dict) else None
    code = meta.get("statuscode") if isinstance(meta, dict) else None
    return code if isinstance(code, int) else None


def _admin_members(response: httpx.Response) -> list[str] | None:
    """``ocs.data.users`` of the admin member list, ``None`` when it is not a list of uids."""
    try:
        payload = response.json()
    except ValueError:
        return None
    envelope = payload.get("ocs") if isinstance(payload, dict) else None
    data = envelope.get("data") if isinstance(envelope, dict) else None
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, list) or not all(isinstance(uid, str) for uid in users):
        return None
    return users


async def confirm_admin(client: httpx.AsyncClient, creds: Credentials) -> bool | None:
    """Prove whether the account of ``creds`` is an administrator: True, False or None.

    ENTSCHEID admin-nachweis=b of plan 29-01 (measured on nc35 on 2026-10-01, block M2b of
    raw/29-01-messungen.txt): ``GET /ocs/v2.php/cloud/groups/admin/users`` under the given
    credentials answers 200 with OCS status 200 for an admin and 403 with OCS status 403
    for anyone else. Candidate a (reading the ``oc:groups`` propstat) was dropped, because
    a non-admin asking for ``oc:groups`` gets a 403 for the whole PROPFIND (M2), so there is
    no propstat to judge; b also decides on an instance without any tag.

    A 200 alone is not the proof, though (29-REVIEW WR-02, measured on nc35 on 2026-10-01,
    raw/29-REVIEW-FIX-live.txt): Nextcloud's ``GroupsController::getGroupUsers`` also answers
    200 to an account with the delegated "Users" administration setting, to a sub-admin of
    the group ``admin`` and to any member. Such a delegated account sees no invisible tag, so
    taking it for an administrator turned an invisible kein-ki into a green "no tag". The
    answer therefore counts as True only when the impersonated uid is itself in the member
    list it carries (compared without case, as Nextcloud keeps uids unique without case); a
    200 without it is False.

    Exactly those answers are True or False. Every other status, a mismatch between HTTP
    and OCS status, an unreadable body or member list and a timeout are ``None``: not
    decidable, which the caller treats as "no admin view", never as a failed check. The
    member list of the admin group is read only for this comparison and is never returned
    or logged.
    """
    try:
        response = await ocs.ocs_get(client, creds, ADMIN_USERS_PATH)
    except httpx.TimeoutException:
        return None
    code = _ocs_statuscode(response)
    if response.status_code == 200 and code == 200:
        members = _admin_members(response)
        if members is None:
            return None
        return creds.account.casefold() in {uid.casefold() for uid in members}
    if response.status_code == 403 and code == 403:
        return False
    return None
