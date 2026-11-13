"""Byte pin of the two request bodies the calendar bundle sends (TASK-01).

The tasks bundle shares the CalDAV module with the calendar bundle, and the promise of
phase 32 is that the calendar bundle does not change its behaviour by a single byte. The
structural tests in ``test_caldav_client.py`` check what the bodies mean; this file pins what
they are. The hashes were taken from a run on the unchanged module, before the first change
of phase 32 touched it, and they are hashes of the bytes the functions return, never of a
file on disk (a checkout with ``core.autocrlf`` would change those).
"""

import hashlib
from datetime import UTC, datetime

from mcp_connector.nextcloud.clients import caldav

#: sha256 of ``caldav.build_discovery_body()`` before phase 32.
DISCOVERY_BODY_SHA256 = "d330153d5aeba138fc371ccaa08463647af48396c05f6853f9e26da5eb563446"

#: sha256 of ``caldav.build_calendar_query(QUERY_START, QUERY_END)`` before phase 32.
CALENDAR_QUERY_SHA256 = "2352e0a21fb5507150507c56a1a4b6008e4792f9327e952c2dae5fb0ead6a795"

QUERY_START = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
QUERY_END = datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC)


def test_the_calendar_discovery_body_is_byte_for_byte_unchanged() -> None:
    body = caldav.build_discovery_body()
    assert hashlib.sha256(body).hexdigest() == DISCOVERY_BODY_SHA256


def test_the_calendar_query_body_is_byte_for_byte_unchanged() -> None:
    body = caldav.build_calendar_query(QUERY_START, QUERY_END)
    assert hashlib.sha256(body).hexdigest() == CALENDAR_QUERY_SHA256


def test_the_pinned_query_carries_the_two_fixed_instants() -> None:
    """A guard on the pin itself: the inputs above are the ones the hash was taken from."""
    body = caldav.build_calendar_query(QUERY_START, QUERY_END)
    assert b'start="20260901T000000Z"' in body
    assert b'end="20260930T235959Z"' in body
