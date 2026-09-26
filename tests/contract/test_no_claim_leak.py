"""No value of an unchecked token may reach a row about a refused exchange attempt.

That is success criterion 2 of phase 24 read strictly: a row of the refusal chain carries the
rejection group of ``errors.REASONS`` and nothing else. The reason it needs a gate rather than
discipline is that the tempting mistake is a helpful one. ``oauth.exchange_accounts.
acting_party`` lies ready, it is two words long, and a row that named the acting party would
answer the first question an operator asks of such a row. But the token behind a refusal did
not pass its signature check, so its ``azp`` is text a stranger chose: writing it would hand
whoever drives the pre-authentication path a free field in the hash chained trail of the
instance (T-24-04, pitfall 4 of 24-RESEARCH.md).

Two things make this test trustworthy rather than decorative, and both are taken from
``tests/contract/test_no_destructive_calls.py`` rather than written a second time:

*   **Comments and docstrings are removed before counting.** ``audit/refusals.py`` explains in
    its own comment that a row never carries an ``azp``, an issuer, an audience or a ``sub``.
    A naive grep would fail on that sentence, and the usual repair is to delete the sentence,
    which trades documentation for a green check. String literals stay in scope on purpose:
    ``claims["azp"]`` is the real thing this gate is looking for.
*   **Every finding names file and line**, so a violation is a one line fix and never a hunt
    through the tree.

The call gate below is asked of the syntax tree instead of of the text, because a call is a
shape and not a word: ``acting_party=`` as a keyword argument is not a call and must not be a
finding, while ``exchange_accounts.acting_party(claims)`` is one however it is spelled.

Every counter proof runs through the very function the gate runs through. A counter proof
that reimplements the check proves something about the counter proof.

The file also holds the import direction of ``audit/refusals.py``: nothing out of ``..oauth``.
"""

import ast
import io
import re
import tokenize
from collections.abc import Iterable
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"

#: The module this gate guards: the one writer of the refusal chain (plan 24-03).
REFUSALS = "audit/refusals.py"

#: The function that reads the acting party out of a claim set.
ACTING_PARTY = "acting_party"

#: Where it may be called, and why exactly there. Both places stand behind the full checker
#: of phase 21, so the claim set they read has a signature that held, an issuer that was
#: configured, an audience that named this instance and an ``azp`` of the allowlist. That is
#: the difference the whole gate is about: the same function on a checked claim set writes an
#: identity, on an unchecked one it would write whatever a stranger sent.
ACTING_PARTY_CALLERS: dict[str, str] = {
    # The AppAPI account source builds the identity of a mapped account out of a claim set
    # ``ChainedVerifier.verify_token`` has already checked (MAP-02).
    "oauth/exchange_appapi.py": "the identity of a checked exchange token in the ExApp mode",
    # The same step for the standalone mode, over the binding a browser session set up.
    "oauth/exchange_binding.py": "the identity of a checked exchange token in the bound mode",
}

#: The six fields a row of the refusal chain may carry, and no seventh. ``actor`` is
#: deliberately not among them, although the column exists and although this is exactly the
#: column an acting party would go into on any other path (AUDIT-07).
ALLOWED_ENTRY_FIELDS = frozenset({"chain", "kind", "at", "outcome", "reason", "removed"})

#: The class whose construction the field gate above is asked about.
ENTRY = "Entry"

#: Names that point at a piece of a token or at the claim set of one. A name of this list in
#: the writer of the refusal chain means a value of an unchecked token got as far as the
#: module that writes rows, which is one line away from a row that carries it.
FORBIDDEN_NAMES: dict[str, str] = {
    "azp": "the acting party of an unchecked token",
    "iss": "the issuer an unchecked token named",
    "aud": "the audience an unchecked token named",
    "sub": "the subject of an unchecked token",
    "kid": "the key id an unchecked token named",
    "claims": "the claim set of an unchecked token",
    "token": "the credential itself",
}

#: Whole words and never substrings: ``audit_store`` carries ``aud``, ``substr`` carries
#: ``sub`` and a gate that matched those would be red on the day it was written and would be
#: repaired by renaming a variable. Case insensitive, so a name spelled ``Claims`` in a type
#: is caught as well.
_NAME_PATTERNS = {
    name: re.compile(rf"\b{name}\b", re.IGNORECASE) for name in sorted(FORBIDDEN_NAMES)
}


def _source_files() -> list[Path]:
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no production sources found under {SRC}"
    return files


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Return the source lines with comments and docstrings blanked out.

    Only these two are removed. A string literal that is not a docstring stays, because a
    claim is read as a string: ``claims["azp"]``.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    blanked = list(lines)

    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        first = node.body[0]
        end = first.end_lineno or first.lineno
        for lineno in range(first.lineno, end + 1):
            blanked[lineno - 1] = ""

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        lineno, col = token.start
        blanked[lineno - 1] = blanked[lineno - 1][:col]

    return [(number, text) for number, text in enumerate(blanked, start=1) if text.strip()]


def _violations(relative: str, lines: Iterable[tuple[int, str]]) -> list[str]:
    """Every finding in already filtered lines, in the form the failure message prints.

    Shared by the gate and by its counter proofs on purpose: a counter proof that
    reimplements the check proves something about the counter proof.
    """
    findings: list[str] = []
    for number, text in lines:
        for name, pattern in _NAME_PATTERNS.items():
            if pattern.search(text):
                findings.append(
                    f"{relative}:{number}: {name!r} ({FORBIDDEN_NAMES[name]}): {text.strip()}"
                )
    return findings


def _called_name(node: ast.expr) -> str | None:
    """The name a call names, whether it was reached through a module or imported directly."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _calls_of(relative: str, source: str, name: str) -> list[str]:
    """Every call of ``name`` in ``source``, each naming file and line.

    Asked of the syntax tree and not of the text: a keyword argument that happens to be
    called ``acting_party`` is not a call of it, and a gate that could not tell the two apart
    would be repaired by renaming a parameter.
    """
    findings: list[str] = []
    for node in ast.walk(ast.parse(source, filename=relative)):
        if isinstance(node, ast.Call) and _called_name(node.func) == name:
            findings.append(f"{relative}:{node.lineno}: {name}() is called here")
    return findings


def _acting_party_violations(relative: str, source: str) -> list[str]:
    """Every call of :data:`ACTING_PARTY` outside the places that may make one."""
    if relative in ACTING_PARTY_CALLERS:
        return []
    return _calls_of(relative, source, ACTING_PARTY)


def _entry_violations(relative: str, source: str) -> list[str]:
    """Every field an ``Entry`` of this module carries that is not one of the six allowed.

    A positional argument is a finding of its own: it carries a field the keyword check
    could not see, and the constructor of ``audit/store.Entry`` would accept it.
    """
    findings: list[str] = []
    for node in ast.walk(ast.parse(source, filename=relative)):
        if not (isinstance(node, ast.Call) and _called_name(node.func) == ENTRY):
            continue
        for _argument in node.args:
            findings.append(f"{relative}:{node.lineno}: {ENTRY}() is built with a positional field")
        for keyword in node.keywords:
            if keyword.arg is None:
                findings.append(f"{relative}:{node.lineno}: {ENTRY}(**...) hides its fields")
            elif keyword.arg not in ALLOWED_ENTRY_FIELDS:
                findings.append(
                    f"{relative}:{node.lineno}: {ENTRY}({keyword.arg}=...) is not allowed"
                )
    return findings


#: The package the writer of the refusal chain must not import from.
OAUTH = "oauth"


# The rule of the module docstring of ``audit/refusals.py`` ("What this module must not
# import"): the writer runs on the pre-authentication path and names the five minute window a
# second time rather than importing it, so an import out of ``..oauth`` would be the first
# step towards a token value reaching a row (IN-07 of 24-REVIEW.md).
def _oauth_imports(relative: str, source: str) -> list[str]:
    """Every import in ``source`` that reaches into :data:`OAUTH`, each naming file and line.

    Compared by dotted segment and never by substring, so a future module called
    ``oauthless`` is no finding, and asked of the syntax tree, so the word in a comment or a
    docstring is none either. The relative form ``from .. import oauth`` carries the package
    in the imported name rather than in the module, which is why the names are asked as well.
    """
    findings: list[str] = []
    for node in ast.walk(ast.parse(source, filename=relative)):
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")
            names = [segment for alias in node.names for segment in alias.name.split(".")]
            if OAUTH in module or OAUTH in names:
                findings.append(f"{relative}:{node.lineno}: imports out of {OAUTH}")
        elif isinstance(node, ast.Import):
            if any(OAUTH in alias.name.split(".") for alias in node.names):
                findings.append(f"{relative}:{node.lineno}: imports out of {OAUTH}")
    return findings


# --- the acting party, and the two places that may read it ---------------------------------


def test_nothing_outside_the_two_checked_places_reads_the_acting_party() -> None:
    """T-24-04: the value is only ever safe where the claim set behind it was checked."""
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        findings.extend(_acting_party_violations(relative, path.read_text(encoding="utf-8")))

    assert findings == [], (
        "the acting party of a claim set may be read where that claim set was checked and "
        "nowhere else:\n" + "\n".join(findings)
    )


def test_the_gate_would_notice_the_acting_party_in_the_refusal_writer() -> None:
    """Counter proof, over the same function and over source instead of over a real change.

    The tempting line itself: an ``actor`` next to the reason, so that a row says who tried.
    It must be a finding, and it must name file and line.
    """
    tempting = "async def note(self, claims):\n    return Entry(actor=acting_party(claims))\n"

    findings = _acting_party_violations(REFUSALS, tempting)

    assert len(findings) == 1
    assert findings[0].startswith(f"{REFUSALS}:2:"), "a finding names file and line"


def test_the_allowlist_of_callers_is_not_decoration() -> None:
    """Both allowed places have to exist and really call it, or the list guards nothing."""
    for relative in ACTING_PARTY_CALLERS:
        path = SRC / relative
        assert path.is_file(), f"{relative} is allowed to call {ACTING_PARTY} but does not exist"
        assert _calls_of(relative, path.read_text(encoding="utf-8"), ACTING_PARTY) != [], (
            f"{relative} is on the allowlist but calls {ACTING_PARTY} nowhere"
        )


def test_the_exemption_covers_the_call_and_not_the_file() -> None:
    """The narrow half of the same list: an allowed file is allowed this one call.

    Written as "ignore this file", the exemption would cover every future line of it as
    well, and ``oauth/exchange_appapi.py`` is the module that talks to Nextcloud about
    accounts. What it is allowed is one name, which is why the gate asks for that name.
    """
    allowed = next(iter(ACTING_PARTY_CALLERS))
    source = "value = acting_party(claims)\nother = something_else(claims)\n"

    assert _acting_party_violations(allowed, source) == []
    assert len(_acting_party_violations(REFUSALS, source)) == 1


# --- the fields of a row about a refused attempt -------------------------------------------


def test_a_row_of_the_refusal_chain_carries_the_six_allowed_fields_and_no_other() -> None:
    """The row is the place the leak would land, so the row is measured field by field."""
    path = SRC / REFUSALS
    assert path.is_file(), f"{REFUSALS} is the module this gate exists for"

    findings = _entry_violations(REFUSALS, path.read_text(encoding="utf-8"))

    assert findings == [], "a row about a refused attempt carries no seventh field:\n" + "\n".join(
        findings
    )


def test_the_field_gate_would_notice_an_actor_a_positional_field_and_a_spread() -> None:
    """Counter proof for all three shapes the check knows, over the same function."""
    with_an_actor = "Entry(chain=c, kind=k, at=t, outcome=o, reason=r, removed=n, actor=a)\n"
    positional = "Entry(c, kind=k)\n"
    spread = "Entry(**fields)\n"

    assert len(_entry_violations(REFUSALS, with_an_actor)) == 1
    assert "actor" in _entry_violations(REFUSALS, with_an_actor)[0]
    assert len(_entry_violations(REFUSALS, positional)) == 1
    assert len(_entry_violations(REFUSALS, spread)) == 1
    for shape in (with_an_actor, positional, spread):
        assert _entry_violations(REFUSALS, shape)[0].startswith(f"{REFUSALS}:1:")


# --- the names that point at a piece of a token --------------------------------------------


def test_the_refusal_writer_names_no_part_of_a_token() -> None:
    """The step before the row: a value that never arrives cannot be written down."""
    path = SRC / REFUSALS

    findings = _violations(REFUSALS, _code_lines(path))

    assert findings == [], (
        "the writer of the refusal chain sees a rejection identifier and nothing else:\n"
        + "\n".join(findings)
    )


def test_the_filter_removes_prose_and_only_prose() -> None:
    """Counter proof: the module explains what it never writes, and may keep saying so.

    ``audit/refusals.py`` names ``azp``, the issuer, the audience and the ``sub`` in the
    comment above the row it builds. Without this case the gate above could be green because
    the filter eats everything, and the usual repair for the other kind of failure would be
    to delete the sentence.
    """
    path = SRC / REFUSALS
    raw = path.read_text(encoding="utf-8")
    measured = "\n".join(text for _, text in _code_lines(path))

    assert "azp" in raw, "the module says in prose which values a row never carries"
    assert "azp" not in measured, "and that prose must not reach the gate"

    with_a_violation = measured + '\n    identifier = claims["azp"]\n'
    findings = _violations(REFUSALS, list(enumerate(with_a_violation.splitlines(), start=1)))

    assert findings != [], "a real read of a claim is still visible after filtering"
    assert any("'azp'" in finding for finding in findings)
    assert any("'claims'" in finding for finding in findings)


def test_the_forbidden_names_are_not_decoration() -> None:
    """At least one of them has to occur in the measured code of ``oauth/``.

    A list of names that matches nothing anywhere would block nothing, and nobody would
    notice: the gate above would be green because the words are unusual rather than because
    the writer avoids them. The claim set of the exchange path is read all over ``oauth/``,
    and that is exactly the difference this gate draws a line through.
    """
    findings: list[str] = []
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        if not relative.startswith("oauth/"):
            continue
        findings.extend(_violations(relative, _code_lines(path)))

    assert findings != [], "no forbidden name occurs in the measured code of oauth/"
    assert any("'claims'" in finding for finding in findings)
    assert any("'azp'" in finding for finding in findings)


# --- the import direction of the refusal writer ------------------------------------------


def test_the_refusal_writer_imports_nothing_out_of_oauth() -> None:
    """IN-07: the rule the module docstring of ``audit/refusals.py`` states, held as a gate."""
    path = SRC / REFUSALS

    findings = _oauth_imports(REFUSALS, path.read_text(encoding="utf-8"))

    assert findings == [], "the writer of the refusal chain imports nothing out of oauth:\n" + (
        "\n".join(findings)
    )


def test_the_import_gate_would_notice_every_spelling_of_oauth() -> None:
    """Counter proof over the same function: five spellings of the import, one finding each
    with its line, and neither a neighbouring name nor the word in prose is a finding."""
    spellings = [
        "from ..oauth import throttle\n",
        "from ..oauth.throttle import WINDOW\n",
        "from .. import oauth\n",
        "import mcp_connector.oauth.throttle\n",
        "from mcp_connector.oauth import chain\n",
    ]
    for spelling in spellings:
        findings = _oauth_imports(REFUSALS, '"""A module."""\n' + spelling)
        assert len(findings) == 1, spelling
        assert findings[0].startswith(f"{REFUSALS}:2:"), "a finding names file and line"

    harmless = (
        '"""This module imports nothing out of oauth."""\n'
        "from ..errors import known_reason  # and nothing out of oauth\n"
        "import oauthless\n"
    )
    assert _oauth_imports(REFUSALS, harmless) == []
