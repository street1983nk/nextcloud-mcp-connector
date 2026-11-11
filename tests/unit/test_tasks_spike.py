"""Unit tests for the pure helpers of ``scripts/tasks_spike.py`` (phase 30).

The script is not a package module, so it is loaded from its file path. Nothing here talks
to a network or to Docker: the measuring blocks run against the live nc35 topology from the
script itself. Pinned down here are only the helpers whose mistakes would silently falsify
a measurement: a refusal counted although the folder exists, an abort criterion that lets a
403 pass, a RAM gate that starts next to a foreign Nextcloud, a secret written into a
protocol, a quoted raw value that stands in no raw file.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tasks_spike.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tasks_spike", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tasks_spike"] = module
    spec.loader.exec_module(module)
    return module


spike = _load()


# --- the status matrix --------------------------------------------------------------------


def test_mkcol_expectations_name_the_fourteen_rows_in_order_with_the_researched_status() -> None:
    assert spike.mkcol_expectations() == {
        "frei": 201,
        "ordner-vorhanden": 405,
        "datei-vorhanden": 405,
        "eltern-fehlt": 409,
        "eltern-ist-datei": 409,
        "name-htaccess": 400,
        "name-backslash": 400,
        "name-ueberlang": 400,
        "share-ro": 403,
        "share-rw": 201,
        "root-vorhanden": 201,
        "root-fehlt": 409,
        "root-selbst": 405,
        "quota": 201,
    }
    assert list(spike.mkcol_expectations()) == [
        "frei",
        "ordner-vorhanden",
        "datei-vorhanden",
        "eltern-fehlt",
        "eltern-ist-datei",
        "name-htaccess",
        "name-backslash",
        "name-ueberlang",
        "share-ro",
        "share-rw",
        "root-vorhanden",
        "root-fehlt",
        "root-selbst",
        "quota",
    ]


def test_mkcol_keys_are_exactly_the_keys_of_the_expectations_in_their_order() -> None:
    assert tuple(spike.mkcol_expectations()) == spike.MKCOL_KEYS
    assert len(spike.MKCOL_KEYS) == 14


def test_gf_keys_are_the_five_group_folder_rows_in_order() -> None:
    assert spike.GF_KEYS == (
        "acl-rw",
        "acl-ro",
        "acl-ro-kontrolle-b",
        "acl-ro-nach-regelentzug",
        "gruppe-nur-lesen",
    )


def test_only_a_201_keeps_the_abort_criterion_of_mess_01_silent() -> None:
    assert spike.abort_mess01(201) is False
    assert spike.abort_mess01(403) is True
    assert spike.abort_mess01(405) is True
    assert spike.abort_mess01(0) is True


def test_refused_needs_a_status_outside_2xx_and_nothing_created() -> None:
    assert spike.refused(403, created=False) is True
    assert spike.refused(201, created=True) is False


def test_a_refusal_with_a_created_folder_is_a_contradiction_and_never_counted() -> None:
    with pytest.raises(ValueError, match="contradiction"):
        spike.refused(403, created=True)


def test_same_status_names_every_row_that_differs() -> None:
    left = {"frei": 201, "share-ro": 403}
    assert spike.same_status(left, {"frei": 201, "share-ro": 403}) == (True, [])
    assert spike.same_status(left, {"frei": 201, "share-ro": 404}) == (False, ["share-ro"])
    assert spike.same_status(left, {"frei": 201}) == (False, ["share-ro"])


# --- describe_error -----------------------------------------------------------------------

_ERROR_BODY = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b'<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">\n'
    b"  <s:exception>Sabre\\DAV\\Exception\\MethodNotAllowed</s:exception>\n"
    b"  <s:message>The resource you tried to create already exists</s:message>\n"
    b"</d:error>\n"
)


def test_describe_error_reads_exception_and_message_of_a_sabre_error_body() -> None:
    assert spike.describe_error(_ERROR_BODY) == (
        "Sabre\\DAV\\Exception\\MethodNotAllowed The resource you tried to create already exists"
    )


@pytest.mark.parametrize("body", [b"", b"   \n"])
def test_describe_error_of_an_empty_body_is_an_empty_string(body: bytes) -> None:
    assert spike.describe_error(body) == ""


def test_describe_error_of_something_that_is_no_xml_says_so() -> None:
    assert spike.describe_error(b"<html><body>login") == "(not XML)"


# --- the RAM gate -------------------------------------------------------------------------


def test_free_host_memory_is_read_from_kib() -> None:
    assert spike.free_host_memory_gb("5300000\n") == pytest.approx(5.05)
    assert spike.free_host_memory_gb("MemTotal: 1 kB\nMemAvailable:    5300000 kB\n") == (
        pytest.approx(5.05)
    )


def test_free_host_memory_of_an_unreadable_probe_is_zero_so_the_gate_stays_shut() -> None:
    assert spike.free_host_memory_gb("") == 0.0
    assert spike.free_host_memory_gb("access denied") == 0.0


def test_ram_gate_needs_four_gb_and_no_foreign_run() -> None:
    assert spike.ram_gate_ok(5.05, foreign=[]) is True
    assert spike.ram_gate_ok(3.9, foreign=[]) is False
    assert spike.ram_gate_ok(5.05, foreign=["nc-spike-tags"]) is False


def test_foreign_runs_reports_a_foreign_nextcloud_and_skips_own_containers() -> None:
    lines = ["nc35-nc", "gameworld-dev-app-1 nextcloud:34.0.3-apache 0.5%"]
    assert spike.foreign_runs(lines, own={"nc35-nc"}) == [
        "gameworld-dev-app-1 nextcloud:34.0.3-apache 0.5%"
    ]


def test_foreign_runs_only_lists_a_quiet_helper_container() -> None:
    lines = [
        "nc35-nc nextcloud:35.0.0-apache-local 55.0%",
        "gameworld-dev-gameworld-docker-proxy-1 tecnativa/docker-socket-proxy:v0.5.0 0.02%",
    ]
    assert spike.foreign_runs(lines, own={"nc35-nc"}) == []


@pytest.mark.parametrize(
    "line",
    [
        "some-db postgres:17 0.1%",
        "other mariadb:11 0.0%",
        "nc_app_mcp_connector_park34 127.0.0.1:5000/mcp_connector:0.1.11 0.0%",
        "builder alpine:3 42.5%",
    ],
)
def test_foreign_runs_reports_databases_the_connector_image_and_busy_containers(line: str) -> None:
    assert spike.foreign_runs([line], own={"nc35-nc"}) == [line]


# --- secrets ------------------------------------------------------------------------------


def test_scan_for_secrets_names_every_hit_by_name_and_line_never_by_value() -> None:
    texts = {"protocol": "clean line\nvalue s3cr3t-value here\nAUTHORIZATION-APP-API: abc\n"}
    hits = spike.scan_for_secrets(texts, {"APP_SECRET": "s3cr3t-value", "EMPTY": ""})
    assert hits == ["protocol:2: APP_SECRET", "protocol:3: AUTHORIZATION-APP-API"]
    assert all("s3cr3t-value" not in hit for hit in hits)


def test_scan_for_secrets_ignores_empty_values() -> None:
    assert spike.scan_for_secrets({"p": "a line\n\n"}, {"A": "", "B": "   "}) == []


def test_raw_answer_never_carries_an_authorization_or_cookie_header() -> None:
    headers = [
        ("Content-Type", "application/xml"),
        ("Authorization", "Basic abc"),
        ("AUTHORIZATION-APP-API", "abc"),
        ("Set-Cookie", "oc_sessionPassphrase=abc"),
    ]
    lines = spike.raw_answer(405, "Method Not Allowed", headers, b"<d:error/>")
    text = "\n".join(lines)
    assert "HTTP 405 Method Not Allowed" in text
    assert "Content-Type: application/xml" in text
    assert "abc" not in text
    assert "<d:error/>" in text


# --- quotes of the report -----------------------------------------------------------------

_REPORT = """# Titel

## 1. MKCOL

`nicht im Abschnitt Rohausgaben`

## 12. Rohausgaben

### 12.1 raw/nc35-mkcol.txt

Die Zeile `MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201` steht dort.

```
HTTP 201 Created
  Content-Length: 0
```

## 13. Danach

`auch nicht`
"""


def test_quoted_lines_reads_the_backtick_quotes_and_fenced_lines_of_the_raw_section() -> None:
    assert spike.quoted_lines(_REPORT) == [
        "MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201",
        "HTTP 201 Created",
        "Content-Length: 0",
    ]


def test_missing_quotes_names_what_stands_in_no_raw_file() -> None:
    raw = {
        "raw/nc35-mkcol.txt": (
            "2026 | MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201 | \n"
            "    HTTP 201 Created\n"
        )
    }
    assert spike.missing_quotes(_REPORT, raw) == ["Content-Length: 0"]
    raw["raw/zwei.txt"] = "      Content-Length: 0\n"
    assert spike.missing_quotes(_REPORT, raw) == []
