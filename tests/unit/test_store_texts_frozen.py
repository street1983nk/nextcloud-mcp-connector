"""Pin the App Store texts in appinfo/info.xml to their state of release 0.4.0.

EXCL-F02: the store texts (``summary`` and ``description`` in English, German
and French, the direct children of the root element ``info``) only travel to
the Nextcloud App Store with the next release. Phase 29 kept them byte-identical
to ca157b4; release 0.4.0 renewed the pin with the owner's decision of 2026-10-01
(the kein-ki bullet and Office and PDF in the tools bullet, in all three languages);
release 0.6.0 renewed it with the owner's decision of 2026-10-18 (the files_update
bullet, and the summary now says read, search, create and edit as the signed-in user).

Why a hash instead of ``git show ca157b4:appinfo/info.xml``: the CI job
``unit`` checks out with depth 1, the reference commit is not available there.
The hash pins the extracted texts, so a comment or route added elsewhere in
info.xml does not trip the test, while any change to a store text does.

Renewing the pin is a deliberate act: only together with the owner's decision
on the store texts of the next release. Then recompute the hash with
``_store_texts`` on the new info.xml and update ``FROZEN_AT``,
``EXPECTED_SHA256`` and, if needed, ``EXPECTED_COUNT``.

The ten further ``description`` elements deeper in info.xml (route and option
descriptions) are not store texts and are deliberately not covered.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from lxml import etree

from mcp_connector.nextcloud.clients.xml import hardened_parser

ROOT = Path(__file__).resolve().parents[2]
INFO_XML = ROOT / "appinfo" / "info.xml"

FROZEN_AT = "release 0.7.0"
EXPECTED_SHA256 = "bc1dbc16ae2bbbb796ef1565540205520f0e29096d053285b01713ee02a8b96a"
EXPECTED_COUNT = 6

_STORE_TAGS = ("summary", "description")


def _store_texts(payload: bytes) -> list[str]:
    """Return ``<tag>|<lang or en>|<text>`` for each direct store text child of ``info``."""
    root = etree.fromstring(payload, hardened_parser())
    return [
        f"{child.tag}|{child.get('lang') or 'en'}|{child.text or ''}"
        for child in root
        if child.tag in _STORE_TAGS
    ]


def test_store_texts_are_the_six_expected_elements() -> None:
    texts = _store_texts(INFO_XML.read_bytes())
    assert len(texts) == EXPECTED_COUNT
    keys = [entry.split("|", 2)[0] + "|" + entry.split("|", 2)[1] for entry in texts]
    assert keys == [
        "summary|en",
        "summary|de",
        "summary|fr",
        "description|en",
        "description|de",
        "description|fr",
    ]


def test_store_texts_are_unchanged_since_the_frozen_commit() -> None:
    texts = _store_texts(INFO_XML.read_bytes())
    digest = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    assert digest == EXPECTED_SHA256, (
        f"Store texts in appinfo/info.xml differ from {FROZEN_AT}. They only change "
        "with an owner decision for the next release (EXCL-F02); see the module docstring."
    )
