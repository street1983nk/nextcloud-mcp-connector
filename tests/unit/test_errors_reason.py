"""The rejection reason of an error, and the frozen set it has to come from (T-18-01).

A tool error of this project carries a sentence written for the model: ``dav.py`` names a
real path, ``caldav.py`` a real calendar name, ``ids.py`` the id that was handed in. Putting
that sentence into a log would put result content into the log and would break AUDIT-01. The
reason identifier is the way out: it says *why* a call was refused without saying *what* was
asked for.

That only holds while the set of identifiers stays small and readable. A free string handed
to ``reason=`` would walk straight past :data:`mcp_connector.errors.REASONS`, so the last
case of this file walks the whole of ``src/mcp_connector`` and refuses any ``reason=`` that
is not one of the twelve constants, naming file and line of every finding (the shape of
``tests/contract/test_no_destructive_calls.py``).
"""

import ast
from pathlib import Path
from typing import Any

import pytest

from mcp_connector import config, ids, paging
from mcp_connector.errors import (
    REASON_EXCHANGE_ACCOUNT,
    REASON_EXCHANGE_CLAIMS,
    REASON_EXCHANGE_FAILED,
    REASON_EXCHANGE_ISSUER,
    REASON_EXCHANGE_KEY,
    REASON_EXCHANGE_MALFORMED,
    REASON_GUARD_TRIPPED,
    REASON_UNSPECIFIED,
    REASONS,
    ToolError,
)
from mcp_connector.tools import talk

SRC = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"

#: The two error classes of this package that do not end in ``Error``. Every other one does
#: (``ToolError``, ``AppMissingError``, ``ConflictError``), so the walk below recognises them
#: by their suffix and these names by hand. ``ExchangeRefused`` joined the set with AUDIT-07:
#: since it carries a ``reason`` of its own, a free string handed to it would otherwise have
#: walked past the frozen set on the one path a stranger reaches without a key.
_ERROR_CLASSES_WITHOUT_THE_SUFFIX = frozenset({"ExchangeRefused", "IssuerRefused"})


def _is_an_error_construction(call: ast.Call) -> bool:
    """Say whether a call builds one of this package's error objects.

    The walk has to name the callee rather than only the keyword, because ``reason`` is also
    the name of a **column** of the audit log: ``audit/store.py`` builds an ``Entry`` with
    ``reason=row[11]``, and that value comes out of a file at runtime and can never be a
    module constant. Only the error side is what the frozen set governs.
    """
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name.endswith("Error") or name in _ERROR_CLASSES_WITHOUT_THE_SUFFIX


def _findings_in(source: str, relative: str) -> list[str]:
    """Every ``reason=`` of an error construction in ``source`` that is not a ``REASON_*``.

    The walk over ``src/`` and the counter-proof below run through this one function on
    purpose. A counter-proof written against a second, hand-made copy of the rule would
    prove something about that copy and nothing about the gate.
    """
    findings: list[str] = []
    tree = ast.parse(source, filename=relative)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_an_error_construction(node):
            continue
        for word in node.keywords:
            if word.arg != "reason":
                continue
            value = word.value
            if isinstance(value, ast.Name) and value.id.startswith("REASON_"):
                continue
            if isinstance(value, ast.Attribute) and value.attr.startswith("REASON_"):
                continue
            findings.append(f"{relative}:{value.lineno}: reason= is not a REASON_* constant")
    return findings


@pytest.mark.anyio
async def test_the_talk_send_switch_says_a_guard_stopped_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The switch is a guard of this server, not a refusal by Nextcloud (D-17)."""
    monkeypatch.setenv(config.ENV_TALK_SEND, "0")
    clients: Any = None
    with pytest.raises(ToolError) as refused:
        await talk.send(clients, "abcd1234", "hello")
    assert refused.value.reason == REASON_GUARD_TRIPPED


def test_a_refused_cursor_says_a_guard_stopped_the_call() -> None:
    """Paging refuses a handle that this server would otherwise misread."""
    with pytest.raises(ToolError) as refused:
        paging.decode_cursor("not a handle")
    assert refused.value.reason == REASON_GUARD_TRIPPED

    with pytest.raises(ToolError) as scoped:
        paging.check_scope({"q": "invoice"}, "q", "budget", "search")
    assert scoped.value.reason == REASON_GUARD_TRIPPED


def test_a_refused_id_says_a_guard_stopped_the_call() -> None:
    """The id codec refuses before a single request leaves this server."""
    with pytest.raises(ToolError) as unknown_kind:
        ids.parse("nonsense:1")
    assert unknown_kind.value.reason == REASON_GUARD_TRIPPED

    with pytest.raises(ToolError) as bad_mail:
        ids.parse("mail:abc")
    assert bad_mail.value.reason == REASON_GUARD_TRIPPED


def test_any_other_raise_site_stays_honestly_unspecified() -> None:
    """The roughly 223 untouched raise sites read as "not determined", not as a guess (D-17)."""
    assert ToolError("m", "h").reason == REASON_UNSPECIFIED
    assert REASON_UNSPECIFIED in REASONS
    assert len(REASONS) == 12


def test_the_six_exchange_reasons_are_frozen_and_name_their_path() -> None:
    """AUDIT-07: a reader of an audit line sees which path refused without looking it up.

    The prefix is the whole point of the six names: ``guard_tripped`` could have come from
    any guard of this server, ``exchange_claims`` could not. Grouped rather than one name
    per fixed phrase, because eighteen names in a chained audit trail would resolve a
    refusal down to the single rule that fell, which is the oracle the checker refuses to
    be (the phrases stay in the DEBUG line).
    """
    exchange_reasons = {
        REASON_EXCHANGE_MALFORMED,
        REASON_EXCHANGE_KEY,
        REASON_EXCHANGE_ISSUER,
        REASON_EXCHANGE_CLAIMS,
        REASON_EXCHANGE_ACCOUNT,
        REASON_EXCHANGE_FAILED,
    }
    assert len(exchange_reasons) == 6
    assert exchange_reasons <= REASONS
    assert all(name.startswith("exchange_") for name in exchange_reasons)


def test_the_gate_reports_a_free_text_handed_to_an_exchange_refusal() -> None:
    """The counter-proof: the walk below would see a made-up reason on the exchange path.

    Without this case the walk over ``src/`` proves only that today's source is clean, which
    it would also do if the class had quietly dropped out of the recognised set.
    """
    invented = 'raise ExchangeRefused(reason="made up on the spot")\n'
    assert _findings_in(invented, "invented.py") == [
        "invented.py:1: reason= is not a REASON_* constant"
    ]

    named = "raise ExchangeRefused(reason=REASON_EXCHANGE_MALFORMED)\n"
    assert _findings_in(named, "invented.py") == []


def test_every_reason_under_src_is_one_of_the_frozen_constants() -> None:
    """A string literal at ``reason=`` would walk past the frozen set without a review."""
    findings: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        findings.extend(_findings_in(path.read_text(encoding="utf-8"), relative))

    assert findings == [], (
        "a literal at reason= bypasses the frozen set of errors.REASONS, and a seventh reason "
        "is a decision that belongs into a review and not into a diff:\n" + "\n".join(findings)
    )
