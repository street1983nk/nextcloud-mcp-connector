"""The checkable sentences of `docs/token-exchange.md` held against the code they describe.

The pattern is the one of `tests/unit/test_docs_audit_truth.py`: a number in a document is a
claim about the code, so every number that came out of a constant is asserted against that
constant instead of being typed a second time. This module is the same gate for the setup
document of the token exchange path, and it holds one thing the audit gate does not: the list
of environment variables, **in both directions**. A variable in the page that the code does
not have sends an operator to a setting that does nothing; a variable in the code that the
page keeps quiet about is a setting an operator never learns exists. Both are red here.

**What this module deliberately does not hold, and why.** The page names four kinds of
measured numbers that come from no constant of this repository:

*   the request header limit of the route (about 14.9 kB through Caddy, about 15.1 kB
    directly on HaRP), measured 2026-09-23 against a running NC 35 HaRP topology,
*   Apache's ``LimitRequestFieldSize`` of 8190 bytes per header line and the 8050 to 8200
    byte window the switch was located in, same measurement,
*   the synthetic token sizes (920, 1477, 4132 bytes) and the threshold of about 68 realm
    roles and 68 groups,
*   the 342 characters of an RS256 signature at 2048 bits.

Every one of them is a property of somebody else's software or of a synthetic claim set. They
are true because a measurement with a date says so, not because this code says so, and
inventing a constant here to anchor them would turn a measurement into a fiction that a later
reader would trust more than the measurement. They stay held by their date in the page.

What this module is also not: a vocabulary or claim gate. That lives in
`tests/unit/test_exapp_env_setup.py` and covers the wording. This module checks whether the
page is true.
"""

import re
from pathlib import Path

from mcp_connector import config
from mcp_connector.audit import store
from mcp_connector.errors import REASON_EXCHANGE_ISSUER
from mcp_connector.exapp import audit_read, occ
from mcp_connector.exapp.exchange_check import MAX_BODY_BYTES
from mcp_connector.oauth import mapping
from mcp_connector.oauth.chain import DEFAULT_JWKS_PATH
from mcp_connector.oauth.exchange import (
    EXCHANGE_LEEWAY_SECONDS,
    MAX_TOKEN_BYTES,
    MAX_TOKEN_LIFETIME_SECONDS,
)
from mcp_connector.oauth.exchange_accounts import EXCHANGE_CLIENT_ID

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "token-exchange.md"

#: The measurement beside the setup page. Until WR-01 of the phase 24 review no gate read it
#: at all, which is how eight quoted lines of a document that calls itself raw output came to
#: carry a column layout the code cannot produce.
EVIDENCE = ROOT / "docs" / "exchange-evidence.md"

#: Every mention of a variable of the namespace. The trailing character class demands at least
#: one letter after the prefix, so the two places that name the namespace itself
#: (``the NC_MCP_EXCHANGE_ namespace``) are not read as a variable called nothing.
VARIABLE = re.compile(r"NC_MCP_EXCHANGE_[A-Z][A-Z_]*")

#: The two sections success criterion 5 asks for by name. They are the first thing a later
#: shortening of the page would drop, which is exactly why their presence is a test.
HONESTY_SECTIONS = (
    "## 9. What this path does not do",
    "## 10. What hangs on F13's four open answers",
)


def page() -> str:
    """The page, read the way every gate of this repository reads it."""
    return PAGE.read_text(encoding="utf-8")


def findings(needle: str, text: str | None = None) -> list[str]:
    """One entry per line carrying ``needle``, file and line number first."""
    source = page() if text is None else text
    return [
        f"docs/token-exchange.md:{number}: {line.strip()}"
        for number, line in enumerate(source.splitlines(), start=1)
        if needle in line
    ]


def variables_in(text: str) -> set[str]:
    """Every ``NC_MCP_EXCHANGE_`` variable the given text names."""
    return set(VARIABLE.findall(text))


def unknown_variables(text: str) -> set[str]:
    """Variables the text names that :data:`config.EXCHANGE_VARIABLES` does not have."""
    return variables_in(text) - set(config.EXCHANGE_VARIABLES)


def undocumented_variables(text: str) -> set[str]:
    """Variables the code has that the text keeps quiet about."""
    return set(config.EXCHANGE_VARIABLES) - variables_in(text)


# --- the variable list, in both directions ------------------------------------------------


def test_the_page_invents_no_variable() -> None:
    """A setting that does not exist is worse than a missing one: it looks configured."""
    stray = unknown_variables(page())

    assert stray == set(), (
        f"docs/token-exchange.md names variables the code does not have: {sorted(stray)}. "
        f"config.EXCHANGE_VARIABLES is the list that exists"
    )


def test_the_page_keeps_quiet_about_no_variable() -> None:
    """The other direction, and the one a later variable would trip: a setting nobody
    documents is a setting nobody finds."""
    missing = undocumented_variables(page())

    assert missing == set(), (
        f"docs/token-exchange.md has to name every variable of config.EXCHANGE_VARIABLES, "
        f"missing: {sorted(missing)}"
    )


def test_the_counter_check_of_the_variable_gate() -> None:
    """The proof that the two tests above can go red at all.

    A gate that only ever ran against a correct page proves nothing about a wrong one, so the
    two rules are run here against a text that is deliberately wrong in both directions.
    """
    invented = "NC_MCP_EXCHANGE_TELEPORT"
    assert invented not in config.EXCHANGE_VARIABLES, "the counter check needs a fake name"

    wrong = f"A page that names {invented} and {config.ENV_EXCHANGE_ISSUER} and nothing else."

    assert unknown_variables(wrong) == {invented}, (
        "an invented variable in the page has to be found"
    )
    assert config.ENV_EXCHANGE_AZP in undocumented_variables(wrong), (
        "a variable the page leaves out has to be found too"
    )


# --- the numbers that came out of a constant ----------------------------------------------


def test_the_page_names_the_hard_token_bound_of_the_code() -> None:
    """The one bound of this application on the route, and it is not typed twice."""
    assert f"{MAX_TOKEN_BYTES} bytes" in page(), (
        f"docs/token-exchange.md has to name the token bound as '{MAX_TOKEN_BYTES} bytes', "
        f"because exchange.MAX_TOKEN_BYTES says so"
    )


def test_the_page_names_the_measured_point_above_the_token_bound() -> None:
    """The measurement of assumption A5 (2026-09-24) proved that nothing in front of the rule
    cuts anything, and it did so with the first value above the bound. The page therefore
    names that value, and it is the bound plus one rather than a literal of its own."""
    assert f"{MAX_TOKEN_BYTES + 1} bytes" in page(), (
        f"docs/token-exchange.md has to name the measured point as "
        f"'{MAX_TOKEN_BYTES + 1} bytes', which is exchange.MAX_TOKEN_BYTES plus one"
    )


def test_the_page_names_the_dry_run_body_bound_as_the_multiple_it_is() -> None:
    """``exchange_check.MAX_BODY_BYTES`` is written in the code as the multiple of the token
    bound that it is, and the page says the same thing the same way. The literal is asserted
    **absent**: a number here would be the double maintenance this whole module exists
    against, and it would go stale the day the multiple changes."""
    assert MAX_BODY_BYTES == 2 * MAX_TOKEN_BYTES, (
        "this test describes the body bound as twice the token bound; the code changed"
    )

    text = page()
    assert "twice `MAX_TOKEN_BYTES`" in text, (
        "docs/token-exchange.md has to name the dry run body bound as twice the token bound"
    )
    assert findings(str(MAX_BODY_BYTES)) == [], (
        f"the body bound stands in docs/token-exchange.md as the literal {MAX_BODY_BYTES}: "
        f"{findings(str(MAX_BODY_BYTES))}"
    )


def test_the_page_names_the_lifetime_bound_of_the_code() -> None:
    """The only bound on how long a leaked or revoked token keeps working here, so the page
    says it and says it right."""
    assert f"{MAX_TOKEN_LIFETIME_SECONDS} seconds" in page(), (
        f"docs/token-exchange.md has to name the lifetime bound as "
        f"'{MAX_TOKEN_LIFETIME_SECONDS} seconds', because "
        f"exchange.MAX_TOKEN_LIFETIME_SECONDS says so"
    )


def test_the_page_names_the_clock_tolerance_of_the_code() -> None:
    """The same constant covers age and lifetime, and this is the tolerance around both."""
    assert f"{EXCHANGE_LEEWAY_SECONDS} seconds" in page(), (
        f"docs/token-exchange.md has to name the tolerance as "
        f"'{EXCHANGE_LEEWAY_SECONDS} seconds', because exchange.EXCHANGE_LEEWAY_SECONDS "
        f"says so"
    )


def test_the_page_says_both_age_and_lifetime_fall_under_that_one_bound() -> None:
    """One constant, two questions. A page that named only one of them would leave the other
    looking unbounded, which is the opposite of what the code does."""
    section = page().split("## 9. What this path does not do", maxsplit=1)
    assert len(section) == 2, "docs/token-exchange.md has the section of criterion 5"

    assert f"older or longer-lived than {MAX_TOKEN_LIFETIME_SECONDS} seconds" in section[1], (
        "the section has to say that both the age and the lifetime fall under the one bound"
    )


# --- the names the page would send an administrator to type -------------------------------


def test_the_page_names_the_dry_run_command_of_the_code() -> None:
    """A command name in a document is typed by somebody. AppAPI keys a registration on the
    app id and the name, so a page naming a stale one sends an operator to a 404."""
    assert occ.OCC_EXCHANGE_CHECK_COMMAND_NAME in page(), (
        f"docs/token-exchange.md has to name the dry run as "
        f"{occ.OCC_EXCHANGE_CHECK_COMMAND_NAME!r}, because occ.py registers that name"
    )


def test_the_page_names_the_two_audit_commands_of_the_code() -> None:
    """The first tool call is found again with these two, so they are typed here as well."""
    text = page()

    for command in (occ.OCC_AUDIT_READ_COMMAND_NAME, occ.OCC_AUDIT_COMMAND_NAME):
        assert command in text, f"docs/token-exchange.md has to name {command!r}"


def test_the_page_names_the_reserved_client_id_of_the_code() -> None:
    """How a reader tells an exchange call from a call of a registered client. A wrong value
    here is a grep that finds nothing in a log that has the rows."""
    assert EXCHANGE_CLIENT_ID in page(), (
        f"docs/token-exchange.md has to name the reserved client id as "
        f"{EXCHANGE_CLIENT_ID!r}, because exchange_accounts.EXCHANGE_CLIENT_ID says so"
    )


def test_the_page_names_the_two_mapping_profiles_of_the_code() -> None:
    """Both values of ``NC_MCP_EXCHANGE_MAPPING``, and no third one."""
    text = page()

    for profile in mapping.MAPPING_STRATEGIES:
        assert profile in text, (
            f"docs/token-exchange.md has to name the mapping profile {profile!r}, "
            f"because mapping.MAPPING_STRATEGIES has it"
        )

    assert len(mapping.MAPPING_STRATEGIES) == 2, (
        "the page describes exactly two profiles; a third one needs a paragraph there"
    )


def test_the_page_names_the_default_key_set_path_of_the_code() -> None:
    """The one default value the page does spell out, because the Keycloak side is configured
    against it. Spelled out means held here."""
    assert DEFAULT_JWKS_PATH in page(), (
        f"docs/token-exchange.md has to name the key set path as {DEFAULT_JWKS_PATH!r}, "
        f"because chain.DEFAULT_JWKS_PATH says so"
    )


# --- the two sections that may not quietly disappear --------------------------------------


def test_the_page_carries_both_honesty_sections() -> None:
    """Success criterion 5 asks for both of them as sections of their own rather than as a
    footnote, and a later shortening would reach for them first (T-24-11)."""
    text = page()

    for heading in HONESTY_SECTIONS:
        assert heading in text, f"docs/token-exchange.md has to carry the section {heading!r}"


def test_the_audience_convention_stays_a_recommendation() -> None:
    """The trap of this page: a convention presented as settled while F13 decision 1 is open
    builds installations that have to be rebuilt. The word is the mitigation, so it is a
    test."""
    text = page()

    assert "Recommendation, not a rule." in text, (
        "the audience convention has to stand as a recommendation, because F13 decision 1 is open"
    )


def test_the_playbook_marks_the_role_of_the_client_as_open() -> None:
    """The owner's decision of 2026-09-24: the verified command goes in, its role is marked
    as one of F13's open answers rather than given an invented reason."""
    text = page()

    assert 'occ oauth2:add-client "<name>" "<redirect-uri>"' in text, (
        "the playbook has to carry the verified command"
    )
    assert "an open F13 answer, deferred on 2026-09-24" in text, (
        "the role of the client has to be marked as open, with the date it was deferred on"
    )


def test_the_open_answers_section_says_which_of_the_two_lists_it_is() -> None:
    """There are two lists of four in this project's research, the decisions and the
    knowledge gaps. A page quoting both without saying which is which is worse than one that
    quotes neither."""
    section = page().split("## 10. What hangs on F13's four open answers", maxsplit=1)
    assert len(section) == 2, "docs/token-exchange.md has the section of the open answers"

    assert "Two lists, and which is which." in section[1], (
        "the section has to say which of the two lists of four it is naming"
    )


# --- the measuring document: its quoted lines against the function that prints them --------


def evidence() -> str:
    """The measurement document, read the way this module reads the setup page."""
    return EVIDENCE.read_text(encoding="utf-8")


def row(
    seq: int,
    chain: str,
    kind: str,
    at: int,
    **columns: object,
) -> tuple[object, ...]:
    """One row in the column order ``audit/store._entry_of_row`` reads.

    Written out as a tuple rather than built from an ``Entry``, because what is under test is
    the printed form of a row of the file and not the round trip of a dataclass.
    """
    named = {
        "actor": None,
        "nc_user": None,
        "tool": None,
        "client_id": None,
        "auth_id": None,
        "client_name": None,
        "outcome": None,
        "reason": None,
        "duration_ms": None,
        "params": "[]",
        "removed": None,
        "gap_chain": None,
        "gap_hash": None,
        **columns,
    }
    return (seq, chain, kind, at, *named.values())


#: The six refusal rows of the measured run, as values: the sequence number, the moment, and
#: the two things such a row carries. Everything else of them is empty, which is the property
#: the document is quoted for, and empty columns are exactly what the quoted lines got wrong.
MEASURED_REFUSALS = (
    (493, 1_790_230_457),
    (474, 1_790_230_385),
    (456, 1_790_230_291),
    (438, 1_790_230_244),
    (423, 1_790_230_188),
    (408, 1_790_230_055),
)

#: The two ``u:alice`` rows of the mixed run, taken from the ``--json`` block that stands in
#: the same document and was never touched. Row 494 is the own token, row 495 the exchanged
#: one, which is why the acting party stands on one of them and the client name on the other.
MEASURED_CALLS = (
    row(
        494,
        "u:alice",
        store.KIND_CALL,
        1_790_230_459,
        nc_user="alice",
        tool="files_read",
        client_id="bc6b83e8-9c90-4382-be3d-e087ca300871",
        auth_id="A4RV9s7-IoKoCfL1HMaVNK1l5rTgNjwtsQZPfqyzMJY",
        client_name="exchange evidence",
        outcome=store.OUTCOME_OK,
        duration_ms=93,
        params='["path"]',
    ),
    row(
        495,
        "u:alice",
        store.KIND_CALL,
        1_790_230_460,
        actor="mcp-evidence-orchestrator",
        nc_user="alice",
        tool="files_read",
        client_id=EXCHANGE_CLIENT_ID,
        auth_id="",
        outcome=store.OUTCOME_OK,
        duration_ms=78,
        params='["path"]',
    ),
)


def test_the_quoted_refusal_lines_are_the_lines_this_code_prints() -> None:
    """WR-01 of the phase 24 review, and the reason this gate exists at all.

    ``docs/exchange-evidence.md`` says its blocks are the raw output of the measuring
    script, and these six lines were not: every run of empty columns had a separator too
    few. A proof that was retyped is no longer a measurement, and this phase lives on
    "measured rather than claimed", so the document needs the same kind of gate the setup
    page has. Nothing here retypes the format; the function that prints it is asked.
    """
    text = evidence()
    for seq, at in MEASURED_REFUSALS:
        line = audit_read._line(
            row(
                seq,
                store.CHAIN_EXCHANGE,
                store.KIND_REFUSAL,
                at,
                outcome=store.OUTCOME_REJECTED,
                reason=REASON_EXCHANGE_ISSUER,
                removed=1,
            )
        )
        assert line in text, f"docs/exchange-evidence.md no longer quotes row {seq} as printed"


def test_the_quoted_call_lines_are_the_lines_this_code_prints() -> None:
    """The same for the two rows of the mixed run, and these are the ones that carry values.

    Their columns are the ones that moved when the acting party took its place in the line
    (AUDIT-07), so a reader counting positions in this document is reading the very change
    that made the quoted lines wrong.
    """
    text = evidence()
    for measured in MEASURED_CALLS:
        line = audit_read._line(measured)
        assert line in text, f"docs/exchange-evidence.md no longer quotes row {measured[0]}"


def test_the_measuring_document_says_which_of_its_lines_were_recomputed() -> None:
    """The honesty half. The eight lines above are the printed form of measured values, not
    bytes copied out of a terminal, and a document claiming raw output has to say so."""
    text = evidence()

    assert "WR-01 of the phase 24 review" in text
    assert "No measured value changed; only the number of separators did." in text
