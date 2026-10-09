"""Generate the opt-in POC manifest without changing the released default manifest.

Writes XML to stdout. Contains no secret values. For an explicitly opted-in instance.
"""

from pathlib import Path
from xml.etree import ElementTree as ET


def manifest() -> str:
    path = Path(__file__).resolve().parents[1] / "appinfo/info.xml"
    root = ET.parse(path).getroot()  # noqa: S314 - trusted manifest in this source checkout
    routes = root.find(".//routes")
    variables = root.find(".//environment-variables")
    if routes is None or variables is None:
        raise ValueError("Source manifest is missing routes or environment variables")
    route = ET.SubElement(routes, "route")
    for key, value in {
        "url": "^/events/talk$",
        "verb": "POST",
        "access_level": "PUBLIC",
        "headers_to_exclude": '["AUTHORIZATION-APP-API","EX-APP-ID","EX-APP-VERSION",'
        '"AA-VERSION","X-ORIGIN-IP"]',
    }.items():
        ET.SubElement(route, key).text = value
    for name, label, description in (
        (
            "NC_MCP_TALK_EVENTS_ENABLED",
            "Experimental Talk events",
            "Off by default. Set true to enable experimental background event delivery.",
        ),
        (
            "NC_MCP_TALK_EVENTS_ROOMS",
            "Enabled conversations",
            "Comma-separated exact conversation tokens, at most ten.",
        ),
        (
            "NC_MCP_TALK_EVENTS_SECRET",
            "Talk webhook secret",
            "Dedicated random shared secret for the Talk bot, at least 32 characters.",
        ),
        (
            "NC_MCP_TALK_EVENTS_MAX_TTL_MS",
            "Maximum event subscription lifetime",
            "60000 to 3600000 milliseconds; default 3600000. Clients must renew before expiry.",
        ),
    ):
        variable = ET.SubElement(variables, "variable")
        for key, value in {"name": name, "display-name": label, "description": description}.items():
            ET.SubElement(variable, key).text = value
    return ET.tostring(root, encoding="unicode")


if __name__ == "__main__":
    print(manifest())
