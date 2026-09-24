"""The sentences of three documents held against the constants they describe.

Why this file exists and why it belongs to no single module: it binds `docs/privacy.md`,
`docs/uninstall.md` and `docs/faq.md` to `src/mcp_connector/audit/store.py`. The pattern is
not new here, it is taken from `tests/unit/test_oauth_store.py:1490-1509`, where one sentence
of the privacy page is already held against one fact of the OAuth schema, with the reason
that a data protection document may not read worse than the truth. This module says the same
thing in the other direction: after phase 18 those pages read *better* than the truth, and
plan 19-05 rewrote them. A number in a document is a claim, so every number of the new text
is asserted against the constant it came from rather than typed in twice.

What this does not do. It is not a second vocabulary or claim gate: those live in
`tests/unit/test_exapp_env_setup.py` and cover the same pages for forbidden words and
forbidden claims. This module checks whether the pages are true, not how they are worded.
"""

from pathlib import Path

from mcp_connector.audit import refusals, store

ROOT = Path(__file__).resolve().parents[2]
PRIVACY = ROOT / "docs" / "privacy.md"
UNINSTALL = ROOT / "docs" / "uninstall.md"
FAQ = ROOT / "docs" / "faq.md"

#: All three pages of AUDIT-06, for the assertions that have to hold on every one of them.
PAGES = (PRIVACY, UNINSTALL, FAQ)

#: Wordings that had to disappear, each one measured false against the code of phase 18. The
#: message form is the one of the vocabulary gate: file and line number first, so a red run
#: is a one line correction and not a search through three documents.
GONE = (
    "empties every table",
    "the only automatic",
    "leaves behind: nothing",
    "There is no long lived store of personal data",
)


def page(path: Path) -> str:
    """One page, read the way every gate of this repository reads it."""
    return path.read_text(encoding="utf-8")


def name(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def findings(needle: str) -> list[str]:
    """One entry per line of any page carrying ``needle``, name and line number first."""
    return [
        f"{name(path)}:{number}: {line.strip()}"
        for path in PAGES
        for number, line in enumerate(page(path).splitlines(), start=1)
        if needle in line
    ]


# --- the three automatic deletion paths, each against its constant ------------------------


def test_the_privacy_page_names_the_retention_window_of_the_code() -> None:
    """The first of the three deletion paths (D-09), and the number is not typed twice."""
    expected = f"{store.RETENTION_DAYS} days"

    assert expected in page(PRIVACY), (
        f"docs/privacy.md has to name the retention window as {expected!r}, "
        f"because store.RETENTION_DAYS says so"
    )


def test_the_privacy_page_names_the_upper_bound_of_the_code() -> None:
    """The second deletion path (D-10). The text says MB because an administrator reads MB,
    while ``used_bytes`` counts bytes, so the decimal form is the conversion and not a
    rounding: ``SIZE_LIMIT_BYTES`` is a round number of millions on purpose."""
    expected = f"{store.SIZE_LIMIT_BYTES // 1_000_000} MB"

    assert expected in page(PRIVACY), (
        f"docs/privacy.md has to name the upper bound as {expected!r}, "
        f"because store.SIZE_LIMIT_BYTES says so"
    )


def test_the_privacy_page_names_the_silence_window_of_the_code() -> None:
    """The third deletion path (D-12): a chain has to be silent this long before the app
    asks Nextcloud whether the account behind it still exists."""
    expected = f"{store.USER_SILENCE_DAYS} days"

    assert expected in page(PRIVACY), (
        f"docs/privacy.md has to name the silence window as {expected!r}, "
        f"because store.USER_SILENCE_DAYS says so"
    )


def test_the_privacy_page_names_all_three_deletion_paths_together() -> None:
    """Three numbers in one page could still be three unrelated sentences. The retention
    section is where they belong, and all three have to stand in it."""
    section = page(PRIVACY).split("## Retention", maxsplit=1)
    assert len(section) == 2, "docs/privacy.md has a Retention section"
    retention = section[1]

    for expected in (
        f"{store.RETENTION_DAYS} days",
        f"{store.SIZE_LIMIT_BYTES // 1_000_000} MB",
        f"{store.USER_SILENCE_DAYS} days",
    ):
        assert expected in retention, f"the Retention section has to name {expected!r}"


# --- the third kind of chain, and the one number its page may name ------------------------


def test_the_privacy_page_names_the_chain_of_the_refused_attempts() -> None:
    """AUDIT-07 on the page a data protection officer reads: the app writes rows that belong
    to no account of this instance, and a storage table that did not say so would be exactly
    the kind of document this module exists to prevent."""
    text = page(PRIVACY)

    assert store.CHAIN_EXCHANGE in text, (
        f"docs/privacy.md has to name the chain as {store.CHAIN_EXCHANGE!r}, "
        f"because store.CHAIN_EXCHANGE says so"
    )
    assert store.KIND_REFUSAL in text


def test_the_privacy_page_names_the_window_of_the_write_brake_of_the_code() -> None:
    """The one number of the new paragraph, and it is not typed twice. The page says minutes
    because a reader reads minutes, while the constant counts seconds."""
    expected = f"{refusals.REFUSAL_WINDOW_SECONDS // 60} minutes"

    assert expected in page(PRIVACY), (
        f"docs/privacy.md has to name the window of the write brake as {expected!r}, "
        f"because refusals.REFUSAL_WINDOW_SECONDS says so"
    )


def test_the_retention_section_says_the_refusal_chain_falls_under_both_bounds() -> None:
    """The claim that makes the third chain harmless is that it is swept like any other, so
    it belongs in the section that describes the sweeping and not only in the table."""
    section = page(PRIVACY).split("## Retention", maxsplit=1)
    assert len(section) == 2, "docs/privacy.md has a Retention section"

    assert store.CHAIN_EXCHANGE in section[1]


# --- the file both pages have to name -----------------------------------------------------


def test_the_privacy_page_names_the_file_of_the_audit_log() -> None:
    """Two databases, and the second one by its name: a data protection officer who reads
    the storage table has to be able to look for that file in the volume."""
    assert store.AUDIT_FILENAME in page(PRIVACY)
    assert page(PRIVACY).count(store.AUDIT_FILENAME) >= 2, (
        "the intro and the storage table both name the file"
    )


def test_the_runbook_names_the_file_of_the_audit_log() -> None:
    """The check of the runbook reads that file out of the volume, so the file name in the
    command and the constant of the store cannot drift apart."""
    assert page(UNINSTALL).count(store.AUDIT_FILENAME) >= 2, (
        f"docs/uninstall.md has to name {store.AUDIT_FILENAME} in its check and in its text"
    )


def test_the_runbook_mentions_the_audit_log_at_all() -> None:
    """Restpunkt R-18-04 of 18-SECURITY.md, whose measured starting point was exactly this:
    ``grep -ri audit docs/uninstall.md`` found nothing while the log already existed, so the
    one page an administrator follows to delete everything did not know about it.
    """
    hits = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(page(UNINSTALL).splitlines(), start=1)
        if "audit" in line.casefold()
    ]

    assert len(hits) >= 6, f"docs/uninstall.md has to name the audit log, found: {hits}"


def test_the_faq_answer_about_removing_everything_names_the_exception() -> None:
    """The shortest public answer to "how do I get rid of all the data" is this entry, so it
    names both commands and the one file the first of them leaves standing."""
    entries = page(FAQ).split("### ")
    answer = next(entry for entry in entries if entry.startswith("How do I remove the app"))

    assert store.AUDIT_FILENAME in answer
    assert "--rm-data" in answer


# --- what had to disappear ----------------------------------------------------------------


def test_no_page_still_says_the_purge_empties_every_table() -> None:
    """The purge empties the seven tables of the OAuth store; the audit file is not one of
    them (T-18-22). The old wording was true before phase 18 and is false since."""
    assert findings("empties every table") == []


def test_no_page_makes_one_deletion_path_the_only_one() -> None:
    """The narrowed wording of D-v1.5-01. The code has three automatic deletion paths, so a
    sentence about "the only automatic" one would be false whichever one it named.
    """
    assert findings("the only automatic") == []


def test_no_page_still_promises_that_nothing_is_left() -> None:
    """The two sentences that promised an empty instance: the section title of the runbook
    and the retention sentence of the privacy page."""
    assert findings("leaves behind: nothing") == []
    assert findings("There is no long lived store of personal data") == []


def test_every_wording_that_had_to_go_is_gone_from_every_page() -> None:
    """The four of them in one place as well, so a page added later to :data:`PAGES` is
    covered without a new test, and the length of the list is asserted first: a loop over an
    emptied list would pass without a single assertion (the finding of plan 19-03)."""
    assert len(GONE) == 4, GONE

    for needle in GONE:
        assert findings(needle) == [], f"{needle!r} is still there: {findings(needle)}"
