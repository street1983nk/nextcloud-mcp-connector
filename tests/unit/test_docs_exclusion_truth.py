"""The operator pages of the kein-ki tag held against the code and the findings they cite.

Phase 29 writes one page per language (`docs/exclusion.md`, `docs/exclusion.de.md`,
`docs/exclusion.fr.md`) and one short section in each of the three READMEs (D-29-06,
D-29-07). Every sentence of those pages is a promise an administrator makes data protection
decisions on (T-29-24), so this module holds what can be held mechanically:

*   **The anchors.** The nine limits of D-29-05, the eight further technical limits of
    D-29-11, the limit of FOLD-06 and four section anchors stand as ``<a id="...">`` in all
    three languages, with the same ids, because the French page and the READMEs of plan
    29-08 link to them.
*   **The evidence.** Every limit section links at least one finding under
    ``../.planning/phases/``, the file it links exists, and the three limits measured in
    phase 25 (share boundary, invisible tag, app disabled) link the measuring report.
    The limit of FOLD-06 (a folder next to a tagged folder) cites a finding under ``docs/``
    instead, a place that outlives the planning folder of its phase.
*   **The links.** Every relative link of a page resolves: files exist, anchors inside the
    page exist. The links of the language switcher are held by their own test and by the
    existence test of the sibling page, not here, so a page written before its sibling is
    not red for the sibling's absence.
*   **The names an operator types.** The command name, its two options, the ``passed`` key
    and the tag name come from the constants that define them, never typed a second time
    (T-29-26); the occ and WebDAV names of the setup (``tag:add``, ``tag:files:add``,
    ``oc:groups``, ``restrict_creation_to_admin``) are held as the strings the raw evidence
    of plan 29-01 ran.
*   **The exit code.** It is always 0 over AppAPI (D-29-04), and each page says so.
*   **The values the pages quote from this code** (29-REVIEW IN-05). The seven step ids,
    the step names and the limit sentence of the quoted output blocks, and the tag query
    budget ``TAG_BUDGET`` in seconds, all read off the constants, so a change of wording or
    of the budget turns this red until the pages follow.
*   **The typography.** No U+2013 and no U+2014 in the pages and the READMEs, and no ASCII
    stand-ins for umlauts in German prose (pitfall P6).
*   **The README sections.** Exactly one section per README links the page of its language,
    with three or four lines of text, naming the tag and the share boundary.

**What this module deliberately does not hold, and why.** The pages quote measured numbers
of somebody else's software: the roughly 240 seconds of a REPORT on SQLite with 140,000
assignments, the menu path of the Nextcloud settings, the wording of occ output. They are
true because a measurement with a date says so (25-MESSBERICHT.md, raw/29-01-messungen.txt,
raw/29-06-live-beweis.txt), not because this code says so, and a constant invented here to
anchor them would turn a measurement into a fiction that a later reader trusts more than the
measurement. They stay held by their date and their source link in the page. This module is
also not a vocabulary gate; it checks whether the pages are true and complete, not how well
they read.
"""

import re
from itertools import pairwise
from pathlib import Path

import pytest

from mcp_connector.exapp.exclusion_check import (
    ADMIN_OPTION,
    JSON_OPTION,
    LIMIT_SENTENCE,
    STEP_NAMES,
)
from mcp_connector.exapp.occ import OCC_EXCLUSION_CHECK_COMMAND_NAME
from mcp_connector.nextcloud.exclusion import EXCLUDE_TAG, TAG_BUDGET
from mcp_connector.nextcloud.exclusion_audit import STEPS

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

#: The three pages, keyed by the ids the ``-k`` filters of plans 29-07 and 29-08 select on.
PAGES: dict[str, Path] = {
    "lang_en": DOCS / "exclusion.md",
    "lang_de": DOCS / "exclusion.de.md",
    "lang_fr": DOCS / "exclusion.fr.md",
}

#: The nine limits of D-29-05, in the order of the pages.
LIMIT_ANCHORS = (
    "limit-share-boundary",
    "limit-invisible-tag",
    "limit-app-disabled",
    "limit-timing",
    "limit-search-outage",
    "limit-notes-create",
    "limit-third-party-providers",
    "limit-tables-free-text",
    "limit-talk-file-room",
)

#: The eight further technical limits of D-29-11 (28-SECURITY.md H-4).
TECH_ANCHORS = (
    "tech-sqlite",
    "tech-upload-oracle",
    "tech-tables-talk-sandbox",
    "tech-foreign-text",
    "tech-upload-staging",
    "tech-talk-conversations",
    "tech-one-wording",
    "tech-mariadb",
)

#: The section anchors the READMEs and the other languages point at.
SECTION_ANCHORS = (
    "operating-modes",
    "setup-self-service",
    "setup-organisation",
    "check-command",
)

#: FOLD-06: the limits whose finding lives at a stable place under ``docs/`` and not under
#: ``.planning/phases/``, so the link survives when the planning folder of a phase moves.
STABLE_EVIDENCE_ANCHORS = ("tech-folder-oracle",)

#: All 22 ids, the contract of plan 29-08 plus the limit of FOLD-06.
ALL_ANCHORS = LIMIT_ANCHORS + TECH_ANCHORS + STABLE_EVIDENCE_ANCHORS + SECTION_ANCHORS

#: The 17 sections that have to cite a finding.
EVIDENCE_ANCHORS = LIMIT_ANCHORS + TECH_ANCHORS

#: The three limits measured in phase 25; their source is the measuring report.
MEASURED_IN_PHASE_25 = ("limit-share-boundary", "limit-invisible-tag", "limit-app-disabled")
REPORT_NAME = "25-MESSBERICHT.md"

#: Where every cited finding lives, written the way the pages link it.
FINDINGS_PREFIX = "../.planning/phases/"

#: How each language says "exit code"; the paragraph that says it also says 0.
EXIT_CODE_WORDS = {"lang_en": "exit code", "lang_de": "Exit-Code", "lang_fr": "code de sortie"}

#: The strings of the setup that an operator copies, as the raw evidence of 29-01 ran them.
SETUP_STRINGS = (
    f"tag:add {EXCLUDE_TAG} public",
    f"tag:add {EXCLUDE_TAG} restricted",
    "tag:files:add",
    "oc:groups",
    "restrict_creation_to_admin",
)

#: Who the command reads as without ``--admin``: the first account of the user list, and
#: the wording it replaced, which claimed an ordinary account (29-REVIEW IN-03).
READER_WORDS = {
    "lang_en": ("first account of the user list", "like an ordinary account"),
    "lang_de": ("erste Konto der Nutzerliste", "gewöhnliches Konto"),
    "lang_fr": ("premier compte de la liste des utilisateurs", "compte ordinaire"),
}

#: The three READMEs: the file, the link target of its language, the share keyword.
READMES: dict[str, tuple[Path, str, str]] = {
    "readme_en": (ROOT / "README.md", "docs/exclusion.md", "share"),
    "readme_de": (ROOT / "README.de.md", "docs/exclusion.de.md", "Freigabe"),
    "readme_fr": (ROOT / "README.fr.md", "docs/exclusion.fr.md", "partage"),
}

#: U+2013 and U+2014, built from their code points so this file carries neither.
DASHES = (chr(0x2013), chr(0x2014))

#: ASCII stand-ins for umlauts that German prose of this project must not carry (P6). The
#: short words are matched as whole words, the stems at a word start.
ASCII_WORDS = re.compile(r"\b(fuer|ueber|koennen|muessen)\b", re.IGNORECASE)
ASCII_STEMS = re.compile(r"\b(pruef|aender|waehl|schluessel|groesse|loesch)", re.IGNORECASE)

ANCHOR = re.compile(r'<a id="([^"]+)"></a>')
LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HEADING = re.compile(r"^#{1,6} ", re.MULTILINE)


def read(path: Path) -> str:
    """A page, read the way every gate of this repository reads it."""
    return path.read_text(encoding="utf-8")


def anchors_in(text: str) -> list[str]:
    """Every ``<a id>`` of a page, in order."""
    return ANCHOR.findall(text)


def section_at(text: str, anchor: str) -> str:
    """From the anchor to the next anchor (or the end of the page)."""
    start = text.index(f'<a id="{anchor}"></a>')
    following = ANCHOR.search(text, start + 1)
    return text[start : following.start() if following else len(text)]


def links_in(text: str) -> list[str]:
    """Every Markdown link target, code blocks excluded."""
    return LINK.findall(FENCE.sub("", text))


def prose(text: str) -> str:
    """The text without fenced blocks and inline code: what is written, not what is typed."""
    return INLINE_CODE.sub("", FENCE.sub("", text))


def paragraphs(text: str) -> list[str]:
    """Blocks separated by an empty line."""
    return [block for block in re.split(r"\n\s*\n", text) if block.strip()]


def ascii_stand_ins(text: str) -> list[str]:
    """The ASCII spellings of umlauts in the prose of a German text."""
    body = prose(text)
    return ASCII_WORDS.findall(body) + ASCII_STEMS.findall(body)


def sections_of(text: str) -> list[tuple[str, str]]:
    """Every heading with the text up to the next heading."""
    starts = [match.start() for match in HEADING.finditer(text)] + [len(text)]
    result: list[tuple[str, str]] = []
    for begin, end in pairwise(starts):
        block = text[begin:end]
        heading, _, body = block.partition("\n")
        result.append((heading, body))
    return result


page_params = pytest.mark.parametrize("lang", list(PAGES), ids=list(PAGES))
landing_params = pytest.mark.parametrize("key", list(READMES), ids=list(READMES))


# --- the pages ---------------------------------------------------------------------------


@page_params
def test_the_page_exists(lang: str) -> None:
    """D-29-06: one page per language."""
    assert PAGES[lang].is_file(), f"{PAGES[lang].relative_to(ROOT)} is missing"


@page_params
def test_the_page_carries_all_anchors(lang: str) -> None:
    """The 22 ids are the contract the other languages and the READMEs link to."""
    present = set(anchors_in(read(PAGES[lang])))
    missing = [anchor for anchor in ALL_ANCHORS if anchor not in present]

    assert missing == [], f"{PAGES[lang].name} lacks the anchors {missing}"


@page_params
def test_each_limit_cites_a_finding_that_exists(lang: str) -> None:
    """D-29-05 and D-29-11: one sentence of effect plus the finding it rests on (P5)."""
    text = read(PAGES[lang])
    for anchor in EVIDENCE_ANCHORS:
        cited = [link for link in links_in(section_at(text, anchor)) if FINDINGS_PREFIX in link]
        assert cited, f"{PAGES[lang].name}#{anchor} cites no finding under {FINDINGS_PREFIX}"
        for link in cited:
            target = (DOCS / link.split("#", 1)[0]).resolve()
            assert target.is_file(), f"{PAGES[lang].name}#{anchor} links a missing {link}"


def _stable_finding_problems(section_text: str) -> list[str]:
    """What keeps a section from citing a finding at a stable place, empty when it does.

    A stable finding is a link without ``../`` whose file exists below ``docs/`` and does
    not resolve into ``.planning/``. Web links and links into the page itself are no
    findings. A link that leaves ``docs/`` is a problem even next to a good one, because
    it is the link that breaks when the planning folder moves (T-31-06-01).
    """
    problems: list[str] = []
    stable: list[str] = []
    planning = (ROOT / ".planning").resolve()
    for link in links_in(section_text):
        if link.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = (DOCS / link.split("#", 1)[0]).resolve()
        if "../" in link or target.is_relative_to(planning):
            problems.append(f"{link} leaves docs/")
        elif not target.is_relative_to(DOCS.resolve()) or not target.is_file():
            problems.append(f"{link} is no file under docs/")
        else:
            stable.append(link)
    if not stable:
        problems.append("no finding under docs/ is linked")
    return problems


@page_params
def test_each_stable_finding_lives_under_docs(lang: str) -> None:
    """FOLD-06: the limit of the folder tool cites a finding that stays where it is."""
    text = read(PAGES[lang])
    for anchor in STABLE_EVIDENCE_ANCHORS:
        problems = _stable_finding_problems(section_at(text, anchor))
        assert problems == [], f"{PAGES[lang].name}#{anchor}: {problems}"


def test_the_stable_finding_check_can_go_red() -> None:
    """The counter check: a planted link into the planning folder, and no link at all."""
    head = '<a id="tech-folder-oracle"></a>\n### Folder next to a tagged folder\n\n'
    planning_link = "../.planning/phases/31-ordner-anlegen/31-RESEARCH.md"
    planted = f"{head}Source: [31-RESEARCH.md]({planning_link}).\n"
    without_link = f"{head}A sentence without a source.\n"
    good = planted.replace(planning_link, "folder-evidence.md#folder-next-to-a-tagged-folder")

    # The planted target exists, so the check is red for where it lies, not for a dead link.
    assert (DOCS / planning_link).resolve().is_file()
    assert any("leaves docs/" in problem for problem in _stable_finding_problems(planted))
    assert _stable_finding_problems(without_link) == ["no finding under docs/ is linked"]
    assert _stable_finding_problems(good) == []


def test_the_stable_limits_are_not_held_to_the_planning_folder() -> None:
    """The 17 sections of phase 29 keep their own check; the stable ones are not among them."""
    assert len(ALL_ANCHORS) == 22
    assert len(EVIDENCE_ANCHORS) == 17
    assert set(STABLE_EVIDENCE_ANCHORS).isdisjoint(EVIDENCE_ANCHORS)


@page_params
def test_the_measured_limits_cite_the_measuring_report(lang: str) -> None:
    """Success criterion 3: share boundary, invisible tag and app disabled point at phase 25."""
    text = read(PAGES[lang])
    for anchor in MEASURED_IN_PHASE_25:
        links = links_in(section_at(text, anchor))
        assert any(REPORT_NAME in link for link in links), (
            f"{PAGES[lang].name}#{anchor} has to link {REPORT_NAME}"
        )


@page_params
def test_every_relative_link_resolves(lang: str) -> None:
    """A dead link in an operator page is a promise nobody can check."""
    text = read(PAGES[lang])
    own_anchors = set(anchors_in(text))
    siblings = {path.name for path in PAGES.values()}
    for link in links_in(text):
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        if link.startswith("#"):
            assert link[1:] in own_anchors, f"{PAGES[lang].name} links a missing anchor {link}"
            continue
        target = link.split("#", 1)[0]
        if target in siblings:
            continue
        assert (DOCS / target).resolve().exists(), f"{PAGES[lang].name} links a missing {link}"


@page_params
def test_the_page_names_what_an_operator_types(lang: str) -> None:
    """Names from the constants that define them, so a renamed option turns this red."""
    text = read(PAGES[lang])
    expected = (
        OCC_EXCLUSION_CHECK_COMMAND_NAME,
        f"--{ADMIN_OPTION}",
        f"--{JSON_OPTION}",
        "passed",
        EXCLUDE_TAG,
        *SETUP_STRINGS,
    )
    missing = [needle for needle in expected if needle not in text]

    assert missing == [], f"{PAGES[lang].name} does not name {missing}"


@page_params
def test_the_page_names_whom_the_command_reads_as_without_admin(lang: str) -> None:
    """IN-03: without ``--admin`` the reader is the first sorted account, often an admin."""
    text = " ".join(read(PAGES[lang]).split())
    right, wrong = READER_WORDS[lang]

    assert right in text, f"{PAGES[lang].name} does not say {right!r}"
    assert wrong not in text, f"{PAGES[lang].name} still says {wrong!r}"


def test_the_manifest_comment_does_not_claim_the_check_always_reads_as_an_admin() -> None:
    """IN-03: the comment on /exclusion-check in info.xml said "impersonating an administrator"."""
    manifest = " ".join((ROOT / "appinfo" / "info.xml").read_text(encoding="utf-8").split())

    assert "while impersonating an administrator" not in manifest
    assert "impersonating an account of the instance" in manifest


@page_params
def test_the_page_quotes_the_steps_and_the_budget_of_the_code(lang: str) -> None:
    """IN-05: step ids, step names, the limit sentence and TAG_BUDGET come from the code."""
    text = read(PAGES[lang])
    expected = (
        *(f"`{step}`" for step in STEPS),
        *STEP_NAMES.values(),
        LIMIT_SENTENCE,
        f"{TAG_BUDGET:g} s",
        "`TAG_BUDGET`",
    )
    missing = [needle for needle in expected if needle not in text]

    assert missing == [], f"{PAGES[lang].name} does not quote {missing}"


#: The account tables the live proof dumps around every call (29-REVIEW WR-04).
ACCOUNT_TABLES = ("preferences", "storages", "mounts", "filecache")
LIVE_PROOF = ROOT / "tests" / "integration" / "test_exclusion_check_live.py"


@page_params
def test_the_change_nothing_claim_names_the_account_tables_the_proof_compares(lang: str) -> None:
    """WR-04: "changes nothing" must rest on more than the tag tables, in page and proof."""
    text = read(PAGES[lang])
    proof = LIVE_PROOF.read_text(encoding="utf-8")

    for table in ACCOUNT_TABLES:
        assert f"`{table}`" in text, f"{PAGES[lang].name} does not name the table {table}"
        assert f"'{table}'" in proof, f"the live proof does not dump {table}"


#: The newest live run of the check against nc35, after the wording changes of f016f8f and
#: the review fixes (29-REVIEW WR-05). The quoted output has to stand in it verbatim.
LATEST_LIVE_RAW = (
    ROOT
    / ".planning"
    / "phases"
    / "29-pr-fkommando-und-doku"
    / "raw"
    / "29-REVIEW-FIX-live-beweis.txt"
)


@page_params
def test_the_quoted_output_stands_verbatim_in_the_latest_live_run(lang: str) -> None:
    """WR-05: no quoted line of the command may be older than the code that prints it."""
    text = read(PAGES[lang])
    raw = LATEST_LIVE_RAW.read_text(encoding="utf-8")
    quoted = [
        line
        for block in FENCE.findall(text)
        if "$ php occ mcp_connector:exclusion:check" in block
        for line in block.splitlines()
        if line.startswith("  ")
    ]

    assert quoted, f"{PAGES[lang].name} quotes no output of the check"
    assert LATEST_LIVE_RAW.name in text, f"{PAGES[lang].name} does not link the latest run"
    missing = [line for line in quoted if line not in raw]
    assert missing == [], f"{PAGES[lang].name} quotes lines the latest run did not print"


@page_params
def test_the_page_says_the_exit_code_is_zero(lang: str) -> None:
    """D-29-04: over AppAPI the exit code is always 0; monitoring reads ``passed``."""
    word = EXIT_CODE_WORDS[lang]
    hits = [block for block in paragraphs(read(PAGES[lang])) if word in block and "0" in block]

    assert hits, f"{PAGES[lang].name} has no paragraph naming the {word!r} together with 0"


@page_params
def test_the_page_links_both_other_languages(lang: str) -> None:
    """The language switcher."""
    links = {link.split("#", 1)[0] for link in links_in(read(PAGES[lang]))}
    others = {path.name for key, path in PAGES.items() if key != lang}

    assert others <= links, f"{PAGES[lang].name} does not link {sorted(others - links)}"


@page_params
def test_the_page_carries_no_long_dash(lang: str) -> None:
    """P6: no U+2013, no U+2014."""
    text = read(PAGES[lang])
    found = [
        f"{PAGES[lang].name}:{number}"
        for number, line in enumerate(text.splitlines(), start=1)
        if any(dash in line for dash in DASHES)
    ]

    assert found == [], f"long dashes in {found}"


def test_the_german_page_writes_real_umlauts() -> None:
    """P6: the German page writes ü, ö, ä and ß, never their ASCII stand-ins."""
    found = ascii_stand_ins(read(PAGES["lang_de"]))

    assert found == [], f"exclusion.de.md writes ASCII stand-ins: {found}"


def test_the_umlaut_gate_can_go_red() -> None:
    """The counter check: a gate that never saw a wrong text proves nothing about one."""
    wrong = "Die Pruefung ist fuer alle, ueber den Schluessel. `fuer` im Code zaehlt nicht."

    assert sorted(word.casefold() for word in ascii_stand_ins(wrong)) == [
        "fuer",
        "pruef",
        "schluessel",
        "ueber",
    ]


# --- the three README sections -----------------------------------------------------------


def landing_section(key: str) -> tuple[str, str]:
    """The one section of a README that links the page of its language."""
    path, target, _ = READMES[key]
    link = f"]({target})"
    matching = [(head, body) for head, body in sections_of(read(path)) if link in body]
    assert len(matching) == 1, (
        f"{path.name} needs exactly one section linking {target}, found {len(matching)}"
    )
    return matching[0]


@landing_params
def test_one_section_links_the_page_of_its_language(key: str) -> None:
    """D-29-07: a short section, three or four lines of text under the heading."""
    _, body = landing_section(key)
    lines = [line for line in body.splitlines() if line.strip()]

    assert 3 <= len(lines) <= 4, (
        f"{READMES[key][0].name}: the section has {len(lines)} lines of text, 3 or 4 expected"
    )


@landing_params
def test_the_section_names_the_tag_and_the_share_boundary(key: str) -> None:
    """What the tag does and the most important limit in one sentence (D-29-07)."""
    _, body = landing_section(key)
    keyword = READMES[key][2]

    assert EXCLUDE_TAG in body, f"{READMES[key][0].name}: the section does not name the tag"
    assert keyword.casefold() in body.casefold(), (
        f"{READMES[key][0].name}: the section does not name the share boundary ({keyword!r})"
    )


@landing_params
def test_the_landing_page_carries_no_long_dash(key: str) -> None:
    """P6 for the whole README, not only the new section."""
    path = READMES[key][0]
    found = [
        f"{path.name}:{number}"
        for number, line in enumerate(read(path).splitlines(), start=1)
        if any(dash in line for dash in DASHES)
    ]

    assert found == [], f"long dashes in {found}"


def test_the_german_landing_section_writes_real_umlauts() -> None:
    """P6 for the section of README.de.md."""
    heading, body = landing_section("readme_de")
    found = ascii_stand_ins(f"{heading}\n{body}")

    assert found == [], f"README.de.md writes ASCII stand-ins in the section: {found}"
