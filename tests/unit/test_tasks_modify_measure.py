"""Unit tests for the pure helpers of ``scripts/tasks_modify_measure.py`` (plan 33-01).

The script is not a package module, so it is loaded from its file path, the same way
``tests/unit/test_tasks_measure.py`` loads the measuring script of phase 32. Nothing here
talks to a network or to Docker. Pinned down are the helpers whose mistakes would silently
falsify a measurement: a line comparison that calls a cleared value removed, a chain whose
children point at the wrong parent, a cap off the rule written before the measurement, and
an inventory place that ends up without a plan.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import icalendar
import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tasks_modify_measure.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks_modify_measure", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tasks_modify_measure"] = module
    spec.loader.exec_module(module)
    return module


modify = _load()


def _ics(*todo_lines: str, alarm: tuple[str, ...] = ()) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nextcloud Tasks v0.18.1",
        "BEGIN:VTODO",
        "UID:p3301-test-0001",
        "DTSTAMP:20261113T100000Z",
        *todo_lines,
    ]
    if alarm:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", *alarm, "END:VALARM"]
    lines += ["END:VTODO", "END:VCALENDAR", ""]
    return "\r\n".join(lines)


# --- line_diff ---------------------------------------------------------------------------------


def test_line_diff_names_a_line_that_went_away_as_removed() -> None:
    before = _ics("SUMMARY:a", "DUE:20261120T120000Z")
    after = _ics("SUMMARY:a")
    found = modify.line_diff(before, after)
    assert found["entfernt"] == ["DUE"]
    assert found["hinzu"] == []
    assert found["geaendert"] == []
    assert found["leer"] == []


def test_line_diff_counts_an_empty_value_as_cleared_and_not_as_removed() -> None:
    before = _ics("SUMMARY:a", "DESCRIPTION:text")
    after = _ics("SUMMARY:a", "DESCRIPTION:")
    found = modify.line_diff(before, after)
    assert found["leer"] == ["DESCRIPTION"]
    assert found["entfernt"] == []
    assert found["geaendert"] == []


def test_line_diff_names_a_changed_value_and_an_added_line() -> None:
    before = _ics("SUMMARY:a", "PRIORITY:3")
    after = _ics("SUMMARY:a", "PRIORITY:5", "STATUS:COMPLETED", "PERCENT-COMPLETE:100")
    found = modify.line_diff(before, after)
    assert found["geaendert"] == ["PRIORITY"]
    assert found["hinzu"] == ["PERCENT-COMPLETE", "STATUS"]
    assert found["entfernt"] == []


def test_line_diff_ignores_the_description_of_an_alarm() -> None:
    before = _ics("SUMMARY:a", alarm=("DESCRIPTION:old", "TRIGGER:-PT15M"))
    after = _ics("SUMMARY:a", alarm=("DESCRIPTION:new", "TRIGGER:-PT15M"))
    found = modify.line_diff(before, after)
    assert found == {"hinzu": [], "entfernt": [], "geaendert": [], "leer": []}


def test_line_diff_reads_folded_lines_as_one_logical_line() -> None:
    before = _ics("SUMMARY:a", "DESCRIPTION:one long\r\n  line")
    after = _ics("SUMMARY:a", "DESCRIPTION:one long line")
    assert modify.line_diff(before, after)["geaendert"] == []


def test_line_diff_sees_a_parameter_change_as_a_change() -> None:
    before = _ics("SUMMARY:a", "DUE;VALUE=DATE:20261120")
    after = _ics("SUMMARY:a", "DUE:20261120T120000Z")
    assert modify.line_diff(before, after)["geaendert"] == ["DUE"]


# --- removal_form ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("after_lines", "name", "expected"),
    [
        (("SUMMARY:a",), "DUE", "zeile-weg"),
        (("SUMMARY:a", "DUE:"), "DUE", "leer"),
        (("SUMMARY:a", "DUE:20261120T120000Z", "PRIORITY:0"), "PRIORITY", "wert-0"),
        (("SUMMARY:a", "DUE:20261120T120000Z", "PRIORITY:3"), "DUE", "unveraendert"),
    ],
)
def test_removal_form_names_the_form_of_a_removal(
    after_lines: tuple[str, ...], name: str, expected: str
) -> None:
    before = _ics("SUMMARY:a", "DUE:20261120T120000Z", "PRIORITY:3")
    assert modify.removal_form(before, _ics(*after_lines), name) == expected


def test_removal_form_of_a_line_that_was_never_there_is_unchanged() -> None:
    assert modify.removal_form(_ics("SUMMARY:a"), _ics("SUMMARY:a"), "CATEGORIES") == (
        "unveraendert"
    )


def test_removal_form_of_a_changed_value_is_no_removal() -> None:
    before = _ics("SUMMARY:a", "PRIORITY:3")
    after = _ics("SUMMARY:a", "PRIORITY:5")
    assert modify.removal_form(before, after, "PRIORITY") == "geaendert"


# --- chain_objects -----------------------------------------------------------------------------


def _parents(objects: list) -> dict[str, str]:
    return {obj.uid: obj.parent for obj in objects}


@pytest.mark.parametrize("depth", [1, 3])
def test_chain_objects_parse_and_carry_unique_uids(depth: int) -> None:
    objects = modify.chain_objects("p3301-root", 50, depth, "p3301-k1")
    assert len(objects) == 50
    uids = [obj.uid for obj in objects]
    assert len(set(uids)) == 50
    assert "p3301-root" not in uids
    for obj in objects:
        calendar = icalendar.Calendar.from_ical(obj.text)
        todos = list(calendar.walk("VTODO"))
        assert len(todos) == 1
        assert str(todos[0]["UID"]) == obj.uid
        assert str(todos[0]["RELATED-TO"]) == obj.parent
        assert obj.text.count("\r\n") == obj.text.count("\n"), "CRLF as the server stores it"


def test_chain_objects_of_depth_one_are_all_children_of_the_root() -> None:
    objects = modify.chain_objects("p3301-root", 50, 1, "p3301-k1")
    assert set(_parents(objects).values()) == {"p3301-root"}
    assert {obj.level for obj in objects} == {1}


def test_chain_objects_of_depth_three_spread_evenly_over_three_levels() -> None:
    objects = modify.chain_objects("p3301-root", 50, 3, "p3301-k3")
    by_level: dict[int, list] = {}
    for obj in objects:
        by_level.setdefault(obj.level, []).append(obj)
    assert sorted(by_level) == [1, 2, 3]
    sizes = sorted(len(group) for group in by_level.values())
    assert sizes[-1] - sizes[0] <= 1
    level_of = {obj.uid: obj.level for obj in objects}
    for obj in objects:
        if obj.level == 1:
            assert obj.parent == "p3301-root"
        else:
            assert level_of[obj.parent] == obj.level - 1


def test_chain_objects_list_every_parent_before_its_children() -> None:
    objects = modify.chain_objects("p3301-root", 50, 3, "p3301-k3")
    seen = {"p3301-root"}
    for obj in objects:
        assert obj.parent in seen
        seen.add(obj.uid)


def test_write_order_puts_every_child_before_its_parent_and_the_root_last() -> None:
    objects = modify.chain_objects("p3301-root", 50, 3, "p3301-k3")
    order = modify.write_order("p3301-root", objects)
    assert order[-1] == "p3301-root"
    assert len(order) == 51
    position = {uid: index for index, uid in enumerate(order)}
    for obj in objects:
        assert position[obj.uid] < position[obj.parent]


def test_chain_objects_refuse_a_depth_the_plan_does_not_name() -> None:
    with pytest.raises(ValueError, match="depth"):
        modify.chain_objects("p3301-root", 50, 2, "p3301-k2")


# --- chain_cap ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("max_total", "expected"),
    [
        (0.4, 50),
        (10.0, 50),
        (15.0, 50),
        (15.1, 45),
        (30.0, 25),
        (60.0, 10),
        (100.0, 10),
    ],
)
def test_chain_cap_follows_the_rule_fixed_before_the_measurement(
    max_total: float, expected: int
) -> None:
    assert modify.chain_cap(max_total) == expected


def test_chain_cap_result_keeps_the_budget_within_the_limit_unless_at_the_floor() -> None:
    for tenths in range(1, 1000):
        max_total = tenths / 10
        cap = modify.chain_cap(max_total)
        assert cap % 5 == 0
        assert 10 <= cap <= 50
        if cap > 10:
            assert modify.derive_budget(max_total * cap / 50) <= 30
        if cap < 50:
            assert modify.derive_budget(max_total * (cap + 5) / 50) > 30


# --- inventory assignment ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("file", "klasse", "methods", "target", "expected"),
    [
        (
            "tests/contract/test_no_destructive_calls.py",
            "gate",
            "MOVE,DELETE",
            "Phase 33",
            ("MOVE", "33-03"),
        ),
        (
            "tests/contract/test_tool_surface.py",
            "gate",
            "PUT,MOVE,DELETE",
            "Phase 33",
            ("PUT,MOVE", "33-02"),
        ),
        ("tests/contract/tool_classes.py", "gate", "PUT", "Phase 33", ("PUT", "33-02")),
        ("src/mcp_connector/server/__init__.py", "annotation", "PUT", "Phase 33", ("PUT", "33-02")),
        (
            "src/mcp_connector/audit/allowlist.py",
            "audit",
            "PUT,MOVE",
            "Phase 33",
            ("PUT,MOVE", "33-02"),
        ),
        (
            "tests/integration/test_canary.py",
            "kanarie",
            "PUT,MOVE",
            "Phase 33",
            ("PUT,MOVE", "33-09"),
        ),
        ("README.md", "zusage-doku", "PUT,MOVE,DELETE", "Phase 34", ("PUT,MOVE", "34")),
        (
            "tests/contract/test_no_destructive_calls.py",
            "gate",
            "DELETE",
            "Phase 33",
            ("", "entfaellt"),
        ),
    ],
)
def test_assign_gives_every_place_exactly_one_plan(
    file: str, klasse: str, methods: str, target: str, expected: tuple[str, str]
) -> None:
    touched, plan, reason = modify.assign(file, klasse, methods, target)
    assert (touched, plan) == expected
    assert reason


def test_assign_refuses_a_place_no_rule_knows() -> None:
    touched, plan, _ = modify.assign("docs/other.md", "gate", "PUT", "Phase 33")
    assert plan == ""
    assert touched == "PUT"


def test_previous_places_read_the_phase_33_rows_of_the_report() -> None:
    report = "\n".join(
        [
            "### 7.1 Fundstellen",
            "",
            "| Klasse | Datei:Zeile | Wortlaut | berührt von | abzuarbeiten in | Muster |",
            "|--------|-------------|----------|-------------|-----------------|--------|",
            "| gate | `a.py:4` | never delete | PUT | Phase 33 | 1 |",
            "| zusage-doku | `README.md:9` | No deleting | PUT | Phase 34 | 1 |",
            "| gate | `a.py:7` | uses ''x'' \\| y | MOVE | Phase 33 | 2 |",
            "",
            "### 7.2 Ausgeschlossene Treffer",
            "| gate | `b.py:1` | other | PUT | Phase 33 | 1 |",
        ]
    )
    assert modify.previous_places(report) == [("a.py", "never delete"), ("a.py", "uses `x` | y")]


def test_new_places_match_by_file_and_wording_not_by_line_number() -> None:
    previous = [("a.py", "never delete"), ("a.py", "keep this")]
    current = [("a.py", 40, "never delete, overwrite"), ("a.py", 41, "brand new line")]
    assert modify.new_places(previous, current) == ["a.py:41"]
