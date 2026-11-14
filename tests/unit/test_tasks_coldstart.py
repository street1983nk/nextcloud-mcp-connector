"""Unit tests for the pure helpers of ``scripts/tasks_coldstart.py`` (plan 33-11)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tasks_coldstart.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks_coldstart", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cold = _load()
HOME = "/remote.php/dav/calendars/alice/"


def test_roles_name_the_home_the_test_list_and_every_other_list() -> None:
    assert cold.role_of(HOME, "alice") == "home"
    assert cold.role_of(HOME.rstrip("/"), "alice") == "andere"
    assert cold.role_of(f"{HOME}p3311-ro_shared_by_bob/", "alice") == "ro"
    assert cold.role_of(f"{HOME}personal/", "alice") == "eigen"
    assert cold.role_of("/remote.php/dav/calendars/bob/p3311-ro/", "alice") == "andere"


def test_cycles_rotate_through_the_three_kinds() -> None:
    assert [cold.kind_of(n) for n in range(4)] == ["wahr", "produkt", "parallel7", "wahr"]


def test_timings_are_summed_up_per_role_and_server_errors_counted() -> None:
    timings = [
        cold.Timing("PROPFIND", "home", "207", 0.25),
        cold.Timing("REPORT", "ro", "207", 1.5),
        cold.Timing("REPORT", "ro", "abgebrochen", 2.0),
        cold.Timing("REPORT", "eigen", "503", 0.1),
    ]
    line = cold.timings_line(timings)
    assert line == (
        "eigen:n=1,status=503,max_ms=100 home:n=1,status=207,max_ms=250 "
        "ro:n=2,status=207/abgebrochen,max_ms=2000"
    )
    assert cold.server_errors(timings) == 1
    assert cold.timings_line([]) == "keine"
