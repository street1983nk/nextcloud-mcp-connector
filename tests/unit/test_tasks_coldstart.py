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


def test_roles_of_shared_lists_never_carry_the_owner() -> None:
    assert cold.role_of(f"{HOME}p3311-gro_shared_by_bob/", "alice") == "gro"
    assert cold.role_of(f"{HOME}p3311-a/x.ics", "alice") == "a"


def test_the_discovery_is_reduced_to_roles_status_and_flags() -> None:
    body = (
        '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
        'xmlns:oc="http://owncloud.org/ns">'
        f"<d:response><d:href>{HOME}</d:href><d:propstat><d:prop/>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        f"<d:response><d:href>{HOME}p3311-ro_shared_by_bob/</d:href><d:propstat><d:prop>"
        '<oc:read-only>1</oc:read-only><c:supported-calendar-component-set><c:comp name="VTODO"/>'
        "</c:supported-calendar-component-set></d:prop><d:status>HTTP/1.1 200 OK</d:status>"
        "</d:propstat><d:propstat><d:prop><d:foo/></d:prop>"
        "<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response>"
        f"<d:response><d:href>{HOME}personal/</d:href><d:propstat><d:prop/>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        "</d:multistatus>"
    ).encode()
    assert cold.discovery_lines(body, "alice") == [
        "eigen:status=200,read_only=fehlt,comp=keine",
        "ro:status=200/404,read_only=1,comp=VTODO",
    ]
    assert cold.discovery_lines(b"<nope", "alice") == ["unlesbar bytes=5"]
    assert "bob" not in " ".join(cold.discovery_lines(body, "alice"))
