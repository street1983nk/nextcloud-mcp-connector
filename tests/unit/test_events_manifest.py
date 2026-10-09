"""The opt-in deployment declares every setting without altering the default manifest."""

import runpy
from pathlib import Path
from xml.etree import ElementTree as ET


def test_generated_manifest_declares_event_route_and_settings():
    root = Path(__file__).resolve().parents[2]
    path = root / "appinfo/info.xml"
    before = path.read_bytes()
    generate = runpy.run_path(str(root / "scripts/events_manifest.py"))["manifest"]
    manifest = ET.fromstring(generate())  # noqa: S314 - local generated test data
    assert path.read_bytes() == before
    routes = [
        r for r in manifest.findall(".//routes/route") if r.findtext("url") == "^/events/talk$"
    ]
    assert len(routes) == 1
    assert routes[0].findtext("verb") == "POST"
    assert routes[0].findtext("access_level") == "PUBLIC"
    names = [v.findtext("name") for v in manifest.findall(".//environment-variables/variable")]
    for name in (
        "NC_MCP_TALK_EVENTS_ENABLED",
        "NC_MCP_TALK_EVENTS_ROOMS",
        "NC_MCP_TALK_EVENTS_SECRET",
        "NC_MCP_TALK_EVENTS_MAX_TTL_MS",
    ):
        assert names.count(name) == 1
    assert b"^/events/talk$" not in before
