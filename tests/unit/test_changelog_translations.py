"""The German and French changelog keep step with the English one.

The store reads ``CHANGELOG.<code>.md`` per language at upload time and imports
only the section of the released version (nextcloudappstore developer docs,
"Changelog"), and the app management in Nextcloud shows that entry in the
language of the signed-in user. A release whose translation lags behind would
therefore show an old or empty German entry next to a current English one.

Two properties hold that together: the newest version of ``CHANGELOG.md`` is
the first version of each translation, and every version a translation carries
has as many list items as the English section. The item count is a proxy for
completeness, not a proof of the wording; it catches the common mistake, a
bullet added in English after the translation was written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "CHANGELOG.md"
TRANSLATIONS: dict[str, Path] = {
    "de": REPO_ROOT / "CHANGELOG.de.md",
    "fr": REPO_ROOT / "CHANGELOG.fr.md",
}

# The store matches release headings with ``^## (\d+\.\d+\.\d+)`` and the
# unreleased block with ``^## [Unreleased]``; the brackets of Keep a Changelog
# are accepted (the 0.7.2 entry was imported from exactly this form).
VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)
UNRELEASED_HEADING = "## [Unreleased]"
LIST_ITEM = re.compile(r"^- ", re.MULTILINE)


def sections(text: str) -> dict[str, str]:
    """Version -> body of its section, in file order."""
    matches = list(VERSION_HEADING.finditer(text))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1)] = text[match.end() : end]
    return result


@pytest.fixture(scope="module")
def english() -> dict[str, str]:
    return sections(SOURCE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", sorted(TRANSLATIONS))
def test_translation_starts_at_the_newest_version(code: str, english: dict[str, str]) -> None:
    """The version about to be released is translated, so the store imports it."""
    text = TRANSLATIONS[code].read_text(encoding="utf-8")
    assert UNRELEASED_HEADING in text, f"CHANGELOG.{code}.md lacks the {UNRELEASED_HEADING} block"
    translated = list(sections(text))
    assert translated, f"CHANGELOG.{code}.md carries no version section"
    newest = next(iter(english))
    assert translated[0] == newest, (
        f"CHANGELOG.{code}.md starts at {translated[0]}, CHANGELOG.md at {newest}: "
        f"translate the {newest} section before the release"
    )


@pytest.mark.parametrize("code", sorted(TRANSLATIONS))
def test_translated_sections_carry_every_item(code: str, english: dict[str, str]) -> None:
    """Each translated version has as many list items as the English section."""
    text = TRANSLATIONS[code].read_text(encoding="utf-8")
    for version, body in sections(text).items():
        assert version in english, f"CHANGELOG.{code}.md names {version}, CHANGELOG.md does not"
        expected = len(LIST_ITEM.findall(english[version]))
        found = len(LIST_ITEM.findall(body))
        assert found == expected, (
            f"CHANGELOG.{code}.md {version}: {found} items, CHANGELOG.md has {expected}"
        )


@pytest.mark.parametrize("code", sorted(TRANSLATIONS))
def test_translation_has_no_dash_and_no_tab(code: str) -> None:
    """The house rules for prose: no em or en dash, no tab."""
    text = TRANSLATIONS[code].read_text(encoding="utf-8")
    # Em dash, en dash and tab, spelled by code point so the test file itself
    # does not carry the characters it forbids.
    for needle in (chr(0x2014), chr(0x2013), chr(0x09)):
        assert needle not in text, f"CHANGELOG.{code}.md carries {needle!r}"
