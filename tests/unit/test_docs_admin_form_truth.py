"""The administration form held against every text that describes it.

The form of ``exapp/admin_settings.py`` grew from seven fields to ten (``files_update``,
``tasks_update``, ``profile_fields_read``), and three kinds of text did not follow:

*   **The description of the form itself** (``strings.ADMIN_SETTINGS_DESCRIPTION``) still
    counted "the two switches after them".
*   **The table in docs/oauth-setup.md** still said "six fields".
*   **The place of the form** in the READMEs and in docs/exapp-install.md lacked the security
    section, while ``strings.ADMIN_SETTINGS_PLACE`` and the live page (NC 34.0.3,
    ``/settings/admin/security``) both have it.

Every number here is taken from the real form scheme, never typed in twice, so a new field
that arrives without a text change turns this module red. The counter checks run the same
check functions over the wording before the fix.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from mcp_connector.exapp import admin_settings, config_values
from mcp_connector.exapp.ui import strings

ROOT = Path(__file__).resolve().parents[2]
OAUTH_SETUP = ROOT / "docs" / "oauth-setup.md"

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
WORD_FOR = {value: word for word, value in NUMBER_WORDS.items()}

#: How the description of the form names each switch that is not about connecting an
#: assistant. A key of the form that is missing here fails the test: a new field needs a
#: sentence before it ships.
SWITCH_WORDING = {
    "talk_send": "Talk message",
    "audit_log": "record of tool calls",
    "files_update": "text files",
    "tasks_update": "tasks",
    "profile_fields_read": "Profile Fields",
}

#: The keys that are about connecting an assistant app, the group the description counts
#: first. Derived from the key names, so a new OAuth key lands in the right group by itself.
CONNECT_PREFIXES = ("public_url", "oauth_")

#: Where a page names the place of the administration form, per language: the phrase that
#: starts it, and the full place it has to read.
PLACE = {
    "en": (
        re.compile(r"Administration settings,"),
        re.compile(r"Administration settings, Security, MCP Connector"),
    ),
    "de": (
        re.compile(r"(?:Verwaltungs|Administrations)einstellungen,"),
        re.compile(r"Administrationseinstellungen, Sicherheit, MCP Connector"),
    ),
    "fr": (
        re.compile(r"Paramètres d'administration,"),
        re.compile(r"Paramètres d'administration, Sécurité, MCP Connector"),
    ),
}

PLACE_PAGES = [
    ("README.md", ROOT / "README.md", "en"),
    ("README.de.md", ROOT / "README.de.md", "de"),
    ("README.fr.md", ROOT / "README.fr.md", "fr"),
    ("exapp-install.md", ROOT / "docs" / "exapp-install.md", "en"),
    ("oauth-setup.md", OAUTH_SETUP, "en"),
]

#: The description before this fix, the counter check of the description checks.
OLD_DESCRIPTION = (
    "Settings an installation from the app store needs. A field left empty keeps whatever the "
    "deploy environment of the container sets, and a value set here wins over it. The first "
    "five fields are about connecting an assistant app; the two switches after them are not: "
    "one decides whether an assistant may send a Talk message through this app, the other "
    "whether this app keeps a record of tool calls. Changes take effect after you disable and "
    "enable this app again."
)

#: The place as README.md named it before this fix.
OLD_README_PLACE = (
    "  - Installed from the app store: tick the box under Administration settings, MCP Connector,\n"
    "    or run `occ app_api:app:config:set mcp_connector profile_fields_read --value on`\n"
)

#: The lead sentence of the oauth-setup table before this fix.
OLD_OAUTH_LEAD = (
    "The form sits in **Administration settings, Security, MCP Connector** and carries six\nfields:"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fold(text: str) -> str:
    """Whitespace and markdown emphasis folded, so a place broken over two lines still reads."""
    return " ".join(text.replace("**", "").split())


def fields() -> list[dict[str, Any]]:
    return admin_settings.form_scheme({})["fields"]


def field_ids() -> list[str]:
    return [field["id"] for field in fields()]


def connect_ids() -> list[str]:
    return [key for key in field_ids() if key.startswith(CONNECT_PREFIXES)]


def other_ids() -> list[str]:
    return [key for key in field_ids() if not key.startswith(CONNECT_PREFIXES)]


def counted(text: str, nouns: str) -> list[int]:
    """Every number word that stands right before one of ``nouns`` (one word may sit between)."""
    pattern = re.compile(rf"\b({'|'.join(NUMBER_WORDS)})\s+(?:\w+\s+)?(?:{nouns})\b", re.IGNORECASE)
    return [NUMBER_WORDS[match.group(1).lower()] for match in pattern.finditer(fold(text))]


def description_problems(text: str) -> list[str]:
    """What a description of the form says that the form does not have."""
    problems: list[str] = []
    allowed = {len(field_ids()), len(connect_ids()), len(other_ids())}
    for number in counted(text, "fields?|switch(?:es)?|settings|values"):
        if number not in allowed:
            problems.append(f"counts {number}, the form has {sorted(allowed)}")
    total = WORD_FOR[len(field_ids())]
    if not re.search(rf"\b{total}\s+fields\b", fold(text), re.IGNORECASE):
        problems.append(f"does not say the form has {total} fields")
    for key in other_ids():
        wording = SWITCH_WORDING.get(key)
        if wording is None:
            problems.append(f"no wording known for the new switch {key}")
        elif wording.casefold() not in text.casefold():
            problems.append(f"does not name the switch {key} ({wording!r})")
    return problems


def place_problems(text: str, lang: str) -> list[str]:
    """Every mention of the form's place that leaves out the security section."""
    start, full = PLACE[lang]
    folded = fold(text)
    found = len(start.findall(folded))
    complete = len(full.findall(folded))
    if found != complete:
        return [f"{found - complete} of {found} mentions lack the security section"]
    return []


def table_rows(text: str) -> list[list[str]]:
    """The rows of the field table that follows the lead sentence of section 3."""
    start = text.index("carries")
    rows: list[list[str]] = []
    in_table = False
    for line in text[start:].splitlines():
        if line.startswith("|"):
            in_table = True
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] in {"Field"} or set(cells[0]) <= {"-"}:
                continue
            rows.append(cells)
        elif in_table:
            break
    return rows


def lead_count(text: str) -> list[int]:
    return counted(text[text.index("The form sits in") :][:200], "fields")


# --- the description of the form -----------------------------------------------------------


def test_the_form_has_one_field_per_config_key() -> None:
    """The reference every other check here measures against."""
    assert field_ids() == list(config_values.CONFIG_KEYS)


def test_the_description_matches_the_form() -> None:
    assert description_problems(strings.ADMIN_SETTINGS_DESCRIPTION) == []


def test_the_description_check_can_go_red() -> None:
    """Counter check: the wording before the fix is reported."""
    assert description_problems(OLD_DESCRIPTION) != []


def test_a_new_field_without_wording_goes_red(monkeypatch: pytest.MonkeyPatch) -> None:
    """Counter check: an eleventh switch without a sentence is reported."""
    extended = [*field_ids(), "calendar_update"]
    monkeypatch.setattr(
        admin_settings,
        "form_scheme",
        lambda env=None: {"fields": [{"id": key} for key in extended]},
    )

    assert description_problems(strings.ADMIN_SETTINGS_DESCRIPTION) != []


# --- the place of the form -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "path", "lang"), PLACE_PAGES, ids=[entry[0] for entry in PLACE_PAGES]
)
def test_every_page_names_the_security_section(name: str, path: Path, lang: str) -> None:
    text = read(path)

    assert PLACE[lang][0].search(fold(text)), f"{name} no longer names the form's place"
    assert place_problems(text, lang) == [], name


#: Nextcloud's German interface calls the area "Administrationseinstellungen" (apps/settings
#: l10n de and de_DE, measured on 34.0.3); a German page that says otherwise sends the reader
#: looking for a menu that does not exist.
GERMAN_PAGES = sorted(ROOT.glob("*.de.md")) + sorted((ROOT / "docs").glob("*.de.md"))


@pytest.mark.parametrize("path", GERMAN_PAGES, ids=[path.name for path in GERMAN_PAGES])
def test_german_pages_use_the_nextcloud_term(path: Path) -> None:
    text = read(path)
    assert "Verwaltungseinstellung" not in text, f"{path.name}: use Administrationseinstellungen"


def test_the_place_constant_is_the_one_the_pages_use() -> None:
    assert PLACE["en"][1].fullmatch(strings.ADMIN_SETTINGS_PLACE)


def test_the_place_check_can_go_red() -> None:
    """Counter check: README.md before the fix is reported."""
    assert place_problems(OLD_README_PLACE, "en") != []


# --- the table in oauth-setup.md ----------------------------------------------------------------


def test_the_oauth_setup_table_lists_every_field() -> None:
    rows = table_rows(read(OAUTH_SETUP))
    keys = [row[1].strip("`") for row in rows]

    assert keys == field_ids()


def test_the_oauth_setup_table_names_the_variable_of_each_key() -> None:
    for row in table_rows(read(OAUTH_SETUP)):
        key = row[1].strip("`")
        assert config_values.KEY_TO_ENV[key] in row[2], key


def test_the_oauth_setup_lead_counts_the_fields() -> None:
    assert lead_count(read(OAUTH_SETUP)) == [len(field_ids())]


def test_the_lead_count_check_can_go_red() -> None:
    """Counter check: the lead sentence before the fix is reported."""
    assert lead_count(OLD_OAUTH_LEAD) != [len(field_ids())]
