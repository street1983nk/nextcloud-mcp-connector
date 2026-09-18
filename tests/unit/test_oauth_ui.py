"""The browser facing building blocks of phase 3, checked against 03-UI-SPEC.md.

Every page of this phase runs through ``layout.page``. That is the whole reason the module
exists, so the checks here are mostly checks on that one function: the five required
response headers, the per response nonce, the escaping of attacker controlled values and
the accessibility contract of the rendered document.

Two rules drive the harsher checks:

* The client name and the redirect URI arrive from a dynamic client registration, which is
  open by default (D-35). They are attacker input (T-03-20), so the escaping test parses
  the document and counts elements instead of comparing substrings: a substring check
  passes happily while the page grew a second form.
* A consent page that can be framed is a clickjacked consent page (T-03-21), and a cached
  one shows the next user a foreign client name (T-03-25). Both are header checks, and
  they run against every page family, not against one example.
"""

import inspect
import re
from html.parser import HTMLParser

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp.ui import connections, errors, icons, layout, strings
from mcp_connector.exapp.ui import consent as ui_consent

ENV = {config.ENV_PUBLIC_URL: "https://cloud.example.com/exapps/mcp_connector"}
HOST = "cloud.example.com"

#: The path the configured public URL carries, which is the prefix HaRP strips before this
#: application sees a request and therefore the prefix every link of a page has to spell.
PREFIX = "/exapps/mcp_connector"

#: A client name as a registration could send it: markup, quotes, a line break and a
#: control character. Nothing of it may reach the document as anything but text.
HOSTILE_NAME = '<script>alert("x")</script>\r\n\x07Bad Client'
BENIGN_NAME = "Friendly Client"

REDIRECT_URI = (
    "https://claude.ai/api/mcp/auth_callback?state=0123456789abcdef0123456789abcdef"
    "&flow=connector-authorization-with-a-very-long-query-string"
)


class Document(HTMLParser):
    """A minimal reader for the three questions the checks ask about a rendered page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attributes: list[tuple[str, str, str | None]] = []
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        for name, value in attrs:
            self.attributes.append((tag, name, value))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)

    @property
    def text(self) -> str:
        return "".join(self.chunks)

    def values_of(self, attribute: str) -> list[str]:
        return [value or "" for _, name, value in self.attributes if name == attribute]


def parse(response: Response) -> Document:
    document = Document()
    document.feed(body(response))
    return document


def body(response: Response) -> str:
    return bytes(response.body).decode("utf-8")


def sample_page(
    name: str = BENIGN_NAME,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    footer: str | None = None,
) -> Response:
    """One page that uses every component, so a single render covers the whole surface."""
    blocks = [
        layout.paragraph(strings.SIGNIN_BODY.format(client=layout.client_name(name), host=HOST)),
        layout.callout(
            "warning",
            strings.CONSENT_WARNING_TITLE,
            strings.CONSENT_WARNING_BODY,
        ),
        layout.detail_list(
            [
                (strings.CONSENT_DETAIL_APP_NAME, layout.client_name(name)),
                (strings.CONSENT_DETAIL_REDIRECT, REDIRECT_URI),
            ]
        ),
        layout.form(
            "/authorize",
            [
                layout.button_secondary(strings.CONSENT_DENY, name="decision", value="deny"),
                layout.button_primary(strings.CONSENT_APPROVE, name="decision", value="approve"),
            ],
            hidden={"state": "abc"},
        ),
        layout.action(strings.ACTION_START_OVER, "/authorize"),
    ]
    return layout.page(
        strings.CONSENT_TITLE.format(client=layout.client_name(name)),
        blocks,
        env=ENV,
        status_code=status_code,
        headers=headers,
        footer=footer,
    )


# --- headers ---------------------------------------------------------------------------


def test_page_answers_html_with_every_required_header() -> None:
    """The five headers of the UI-SPEC, on one function, for every page of the phase."""
    response = sample_page()
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    policy = response.headers["content-security-policy"]
    for directive in (
        "default-src 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
    ):
        assert directive in policy


def test_the_status_code_and_extra_headers_are_passed_through() -> None:
    response = sample_page(status_code=429, headers={"Retry-After": "30"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert response.headers["cache-control"] == "no-store"


def test_the_page_also_carries_its_headers_through_a_real_route() -> None:
    """The headers survive the ASGI stack, not just the Response object."""

    async def handler(request: object) -> Response:
        return sample_page()

    with TestClient(Starlette(routes=[Route("/consent", handler)])) as http:
        response = http.get("/consent")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


# --- the nonce -------------------------------------------------------------------------


def nonce_of(response: Response) -> str:
    match = re.search(
        r"style-src 'nonce-([A-Za-z0-9_-]+)'", response.headers["content-security-policy"]
    )
    assert match is not None, "the policy must name a nonce for the one style block"
    return match.group(1)


def test_the_csp_nonce_is_the_nonce_of_the_style_tag() -> None:
    response = sample_page()
    nonce = nonce_of(response)
    document = parse(response)
    assert document.tags.count("style") == 1
    assert document.values_of("nonce") == [nonce]


def test_two_pages_carry_two_different_nonces() -> None:
    """A reused nonce is a nonce, and a nonce that is not one allows injected styles."""
    first, second = sample_page(), sample_page()
    assert nonce_of(first) != nonce_of(second)
    assert nonce_of(first) in body(first)
    assert nonce_of(second) in body(second)


# --- no script, no external asset ------------------------------------------------------


def test_the_page_has_no_script_no_event_handler_and_no_style_attribute() -> None:
    document = parse(sample_page(HOSTILE_NAME))
    assert "script" not in document.tags
    offenders = [
        (tag, name)
        for tag, name, _ in document.attributes
        if name.startswith("on") or name == "style"
    ]
    assert offenders == []


def test_no_href_and_no_src_points_at_another_origin() -> None:
    """CSP default-src 'none' already forbids it; the document must not even try."""
    document = parse(sample_page())
    targets = document.values_of("href") + document.values_of("src")
    assert targets, "the sample page has at least one link"
    for target in targets:
        assert "://" not in target
        assert not target.startswith("//")


def test_the_stylesheet_ships_no_external_reference() -> None:
    assert "://" not in layout.STYLESHEET
    assert "@import" not in layout.STYLESHEET
    assert "url(" not in layout.STYLESHEET


# --- escaping --------------------------------------------------------------------------


def test_a_hostile_client_name_does_not_add_a_single_element() -> None:
    """T-03-20: a registration must not be able to write page copy or a second form."""
    benign = parse(sample_page(BENIGN_NAME))
    hostile = parse(sample_page(HOSTILE_NAME))
    assert hostile.tags == benign.tags
    assert "script" not in hostile.tags
    assert "<script" not in body(sample_page(HOSTILE_NAME))


def test_a_hostile_client_name_is_readable_as_text() -> None:
    """Escaped, not swallowed: the user has to see what the app calls itself."""
    document = parse(sample_page(HOSTILE_NAME))
    assert "Bad Client" in document.text
    assert "\x07" not in document.text
    assert "\r" not in document.text


def test_a_long_client_name_is_truncated() -> None:
    long_name = "A" * 200
    rendered = layout.client_name(long_name)
    assert len(rendered) <= layout.CLIENT_NAME_LIMIT
    assert rendered.startswith("AAAA")
    assert long_name not in body(sample_page(long_name))


def test_an_empty_client_name_falls_back_to_a_readable_placeholder() -> None:
    assert layout.client_name("   ") == strings.CLIENT_NAME_FALLBACK
    assert layout.client_name("\x00\x01") == strings.CLIENT_NAME_FALLBACK


def test_an_account_name_gets_the_same_treatment_a_client_name_gets() -> None:
    """A display name is written on the Nextcloud side, so the page does not take it as is."""
    assert layout.account_name("  Alice   Adams \n") == "Alice Adams"
    assert layout.account_name("Alice\u0000Adams") == "AliceAdams"
    long_name = "A" * 200
    rendered = layout.account_name(long_name)
    assert len(rendered) <= layout.ACCOUNT_NAME_LIMIT
    assert rendered.startswith("AAAA")


def test_an_unusable_account_name_falls_back_to_the_name_that_is_true() -> None:
    """Unlike a client, an account always has a second name, so there is no placeholder."""
    assert layout.account_name("   ", fallback="alice") == "alice"
    assert layout.account_name("\x00\x01", fallback="alice") == "alice"
    assert layout.account_name("", fallback="alice") == "alice"


def test_an_account_name_without_a_fallback_is_allowed_to_be_empty() -> None:
    """The caller that has nothing to fall back on gets nothing, not an invented word."""
    assert layout.account_name("   ") == ""


def test_a_redirect_uri_is_shown_in_full_and_wraps() -> None:
    """Truncating the return address would hide exactly the part an attacker changed."""
    document = parse(sample_page())
    assert REDIRECT_URI in document.text
    assert ("dd", "class", "mono") in document.attributes
    assert "overflow-wrap: anywhere" in layout.STYLESHEET


# --- structure and accessibility -------------------------------------------------------


def test_the_document_has_one_h1_and_the_three_landmarks() -> None:
    document = parse(sample_page())
    assert document.tags.count("h1") == 1
    for landmark in ("header", "main", "footer"):
        assert document.tags.count(landmark) == 1
    assert ("html", "lang", "en") in document.attributes
    assert body(sample_page()).startswith("<!doctype html>")


def test_buttons_are_buttons_links_are_links_and_no_div_carries_a_role() -> None:
    document = parse(sample_page())
    assert document.tags.count("form") == 1
    assert document.tags.count("button") == 2
    assert document.tags.count("a") == 1
    roles = [tag for tag, name, _ in document.attributes if name == "role"]
    assert "div" not in roles


def test_the_form_is_a_post_with_a_local_action_and_its_hidden_field() -> None:
    document = parse(sample_page())
    assert ("form", "method", "post") in document.attributes
    assert ("form", "action", "/authorize") in document.attributes
    assert ("input", "type", "hidden") in document.attributes
    assert ("input", "name", "state") in document.attributes


def test_a_link_to_another_origin_is_refused() -> None:
    """A link target is never attacker input by accident: it has to be local here."""
    with pytest.raises(ValueError, match="local"):
        layout.link("Start over", "https://evil.example.com/")
    with pytest.raises(ValueError, match="local"):
        layout.link("Start over", "//evil.example.com/")
    with pytest.raises(ValueError, match="local"):
        layout.form("https://evil.example.com/", [])


def test_a_return_target_becomes_a_refresh_the_caller_did_not_write() -> None:
    """CR-03: the head takes a value and never a fragment, so a caller cannot write markup
    into it, and the address is the one the page also shows as a link."""
    response = layout.page(
        "Connected",
        [layout.return_action("Continue", "https://claude.ai/callback?code=abc&state=xyz")],
        refresh_to="https://claude.ai/callback?code=abc&state=xyz",
    )
    rendered = body(response)

    assert '<meta http-equiv="refresh" content="0; url=https://claude.ai/callback?' in rendered
    assert "&amp;state=xyz" in rendered, "the address is escaped where it is written"
    assert rendered.count("claude.ai") == 2, "once in the refresh, once as a readable link"
    assert 'target="_blank"' not in rendered, "the return stays in the window of the flow"


@pytest.mark.parametrize(
    "target",
    ["javascript:alert(1)", "data:text/html,x", "//evil.example.com/", "/local/path"],
)
def test_a_return_target_that_is_not_an_http_address_is_refused(target: str) -> None:
    with pytest.raises(ValueError, match="continue to"):
        layout.page("Connected", [], refresh_to=target)
    with pytest.raises(ValueError, match="return to"):
        layout.return_action("Continue", target)


def test_a_page_carries_either_its_own_refresh_or_a_target_and_never_both() -> None:
    """One head, one refresh: two of them and the browser picks, which is not a decision
    this project leaves to a browser."""
    with pytest.raises(ValueError, match="never both"):
        layout.page(
            "Waiting",
            [],
            head_extra='<meta http-equiv="refresh" content="3">',
            refresh_to="https://claude.ai/callback",
        )


def test_the_stylesheet_carries_the_focus_ring_and_never_removes_one() -> None:
    assert ":focus-visible" in layout.STYLESHEET
    assert "outline: 3px solid #1F3A5F" in layout.STYLESHEET
    assert "outline-offset: 2px" in layout.STYLESHEET
    assert "outline: none" not in layout.STYLESHEET
    assert "outline:none" not in layout.STYLESHEET


def test_the_stylesheet_keeps_the_touch_target_and_the_light_palette() -> None:
    assert "min-height: 44px" in layout.STYLESHEET
    assert "max-width: 560px" in layout.STYLESHEET
    assert "color-scheme: light" in layout.STYLESHEET
    assert "prefers-color-scheme" not in layout.STYLESHEET
    assert "animation" not in layout.STYLESHEET
    assert "transition" not in layout.STYLESHEET


def test_the_stylesheet_never_borrows_the_nextcloud_palette() -> None:
    """T-03-23: a page that looks like Nextcloud teaches the wrong lesson."""
    assert "0082C9" not in layout.STYLESHEET.upper()


# --- callout ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "icon"),
    [("warning", icons.WARNING), ("error", icons.CROSS), ("success", icons.CHECK)],
)
def test_every_callout_kind_carries_its_icon_its_title_and_its_body(kind: str, icon: str) -> None:
    rendered = layout.callout(kind, "Unverified client", "Only approve it if you started this.")
    assert icon in rendered
    assert "Unverified client" in rendered
    assert "Only approve it if you started this." in rendered
    assert f"callout-{kind}" in rendered


def test_an_unknown_callout_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="kind"):
        layout.callout("info", "Title", "Body")


def test_a_callout_escapes_its_own_input() -> None:
    rendered = layout.callout("warning", "<b>t</b>", '"x" & <i>y</i>')
    assert "<b>" not in rendered
    assert "<i>" not in rendered
    assert "&lt;b&gt;t&lt;/b&gt;" in rendered


# --- S3, the two display duties of a document identity (AUTH-08, plan 06-06) -----------
#
# The MCP specification asks for both in normative words: the hostname of the identifier
# "MUST" be displayed, and a client whose return addresses are all loopback "SHOULD" carry
# an additional warning. Both are rendered here and decided by the caller, which is the
# mechanism ``unverified`` already used, so these checks ask the page and nothing else.

#: The candidate client of AUTH-08, measured on 2026-08-20 (06-RESEARCH.md, pattern 4). Its
#: identifier is a URL, which is what gives the page a host to name at all.
CIMD_CLIENT_ID = "https://claude.ai/oauth/claude-code-client-metadata"
CIMD_HOST = "claude.ai"

#: A random identifier, as a client that registered itself carries one: there is no host in
#: it, so there is nothing to show and the page has to stay what it was.
DCR_CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"

#: A host as a hostile document could publish it. It reaches the page through the same
#: single escaping point every other value does, and the check below is the element count of
#: the escaping tests above and not a substring.
HOSTILE_HOST = '<script>alert("h")</script>evil.example'

#: The marker of one rendered warning box, which is how these checks count them: two of them
#: on one page is the point of the loopback warning, and a substring of the copy would pass
#: happily while the second box never appeared.
CALLOUT_MARK = "callout callout-warning"


def consent(
    *,
    name: str = BENIGN_NAME,
    client_id: str = CIMD_CLIENT_ID,
    unverified: bool = True,
    client_host: str | None = None,
    loopback_only: bool = False,
) -> Response:
    """The decision screen with the values a caller of ``oauth/consent.py`` would compute."""
    return ui_consent.consent_page(
        name,
        client_id,
        REDIRECT_URI,
        "alice",
        "flow-id-of-this-request",
        "confirm-token-of-this-flow",
        unverified=unverified,
        client_host=client_host,
        loopback_only=loopback_only,
        env=ENV,
    )


def test_the_client_id_host_is_a_fourth_entry_of_the_same_list() -> None:
    """The MUST of the specification, and it stands next to the identifier it comes from."""
    without = parse(consent())
    with_host = parse(consent(client_host=CIMD_HOST))

    assert without.tags.count("dt") == 3
    assert with_host.tags.count("dt") == 4
    assert with_host.tags.count("dd") == 4
    assert strings.CONSENT_DETAIL_CLIENT_HOST in with_host.text
    assert CIMD_HOST in with_host.text
    assert CIMD_CLIENT_ID in with_host.text, "the host is shown next to the identifier, not for it"


def test_a_registered_client_renders_the_page_it_rendered_before() -> None:
    """No host and no loopback: a client that registered sees the three entries of phase 3
    and the one warning of phase 3, so this change costs that client nothing."""
    document = parse(consent(client_id=DCR_CLIENT_ID))
    rendered = body(consent(client_id=DCR_CLIENT_ID))

    assert document.tags.count("dt") == 3
    assert strings.CONSENT_DETAIL_CLIENT_HOST not in rendered
    assert rendered.count(CALLOUT_MARK) == 1
    assert strings.CONSENT_LOOPBACK_TITLE not in rendered


def test_a_loopback_only_client_carries_a_second_warning() -> None:
    """The SHOULD of the specification: the existing warning plus this one, two boxes."""
    one = body(consent())
    two = body(consent(loopback_only=True))

    assert one.count(CALLOUT_MARK) == 1
    assert two.count(CALLOUT_MARK) == 2
    assert strings.CONSENT_WARNING_TITLE in two
    assert strings.CONSENT_LOOPBACK_TITLE in two
    assert strings.CONSENT_LOOPBACK_BODY in two


def test_the_loopback_warning_stands_on_its_own_for_a_listed_client() -> None:
    """An administrator's listing answers "who is this app", not "who holds that port"."""
    rendered = body(consent(unverified=False, loopback_only=True))

    assert rendered.count(CALLOUT_MARK) == 1
    assert strings.CONSENT_WARNING_TITLE not in rendered
    assert strings.CONSENT_LOOPBACK_TITLE in rendered


def test_a_hostile_host_and_a_hostile_name_add_no_element_to_the_page() -> None:
    """T-06-36: every value of a foreign document goes through the one escaping point."""
    benign = parse(consent(client_host=CIMD_HOST, loopback_only=True))
    hostile = parse(consent(name=HOSTILE_NAME, client_host=HOSTILE_HOST, loopback_only=True))
    rendered = body(consent(name=HOSTILE_NAME, client_host=HOSTILE_HOST, loopback_only=True))

    assert hostile.tags == benign.tags
    assert "script" not in hostile.tags
    assert "<script" not in rendered
    assert "evil.example" in hostile.text, "escaped and readable, never swallowed"
    assert "Bad Client" in hostile.text


def test_the_decision_screen_shows_no_image_at_all() -> None:
    """T-06-37: a ``logo_uri`` of a foreign domain would be a tracking channel of the
    reader's browser, and this screen has never shown a logo."""
    document = parse(consent(client_host=CIMD_HOST, loopback_only=True))
    source = inspect.getsource(ui_consent)

    assert "img" not in document.tags
    assert document.values_of("src") == []
    assert "logo_uri" not in source
    assert "<img" not in source


# --- icons -----------------------------------------------------------------------------


def test_there_are_exactly_three_icons() -> None:
    assert sorted(icons.__all__) == ["CHECK", "CROSS", "WARNING"]


@pytest.mark.parametrize("icon", [icons.WARNING, icons.CHECK, icons.CROSS])
def test_every_icon_is_inline_decorative_and_sized(icon: str) -> None:
    assert icon.startswith("<svg")
    assert 'aria-hidden="true"' in icon
    assert 'width="20"' in icon
    assert 'height="20"' in icon
    assert "currentColor" in icon
    assert "<title" not in icon
    assert "://" not in icon


# --- identity of the sender ------------------------------------------------------------


def test_the_wordmark_and_the_host_come_from_the_configuration() -> None:
    document = parse(sample_page())
    assert strings.WORDMARK in document.text
    assert HOST in document.text


def test_the_page_function_never_sees_the_request() -> None:
    """T-03-02 for HTML: a forged Host header must not be able to rename the sender."""
    parameters = inspect.signature(layout.page).parameters
    assert "request" not in parameters
    assert "env" in parameters


def test_the_footer_names_who_may_ask_for_a_password() -> None:
    document = parse(sample_page())
    assert strings.FOOTER_PASSWORD_PROMPT in document.text


def test_a_page_can_carry_its_own_footer() -> None:
    document = parse(sample_page(footer=strings.CONSENT_FOOTER.format(host=HOST)))
    assert "never sees the password you typed" in document.text


# --- E1 to E7, the seven error pages ------------------------------------------------------
#
# The table below is the second copy of the UI-SPEC table on purpose. A test that reads the
# status code out of the implementation proves that the implementation equals itself.

ERROR_PAGES = [
    ("E1", 403, strings.ERROR_ALLOWLIST_TITLE, "Ask your administrator"),
    ("E2", 400, strings.ERROR_REGISTRATION_OFF_TITLE, "Ask your administrator"),
    ("E3", 400, strings.ERROR_EXPIRED_TITLE, "Start the connection again"),
    ("E4", 408, strings.ERROR_TIMEOUT_TITLE, "Start the connection again"),
    ("E5", 400, strings.ERROR_REDIRECT_TITLE, "Start the connection again"),
    ("E6", 429, strings.ERROR_THROTTLED_TITLE, "Wait"),
    # E8 joined the table in phase 4 and stands where the table declares it: before the
    # generic page, which stays the last row because it is also the fallback of an unknown
    # code (04-UI-SPEC.md, E8).
    ("E8", 403, strings.ERROR_SIGN_IN_TITLE, "Sign in at"),
    # E9 joined in phase 5 (BL-10) and stands next to E8 for the same reason: both are a
    # refusal of an account rather than of a request, and both answer 403 without a
    # challenge. It is the page every enforcement point of the switch answers with.
    ("E9", 403, strings.CONNECTIONS_PAUSED_TITLE, strings.ACTION_OPEN_CONNECTIONS),
    ("E7", 500, strings.ERROR_GENERIC_TITLE, "Try again"),
]

#: What an attacker must not learn from an error page: which check fired, which parameter
#: was wrong, where we run (T-03-24). Checked against the whole document, markup included,
#: because a leak in an attribute is still a leak.
FORBIDDEN_ON_ERROR_PAGES = [
    "invalid_grant",
    "invalid_client",
    "invalid_request",
    "unauthorized_client",
    "access_denied",
    "redirect_uri",
    "code_verifier",
    "code_challenge",
    "client_secret",
    "Traceback",
    "traceback",
]

#: The copy rules of the contract. Checked against the visible text only: the document type
#: declaration carries an exclamation mark that no user ever reads.
FORBIDDEN_IN_ERROR_TEXT = ["click here", "Sorry", "you entered", "!"]


def error_body(code: str, client: str = "", seconds: int = 0) -> str:
    response, _ = errors.error_page(code, env=ENV, client=client, seconds=seconds)
    return body(response)


@pytest.mark.parametrize(("code", "status", "title", "next_step"), ERROR_PAGES)
def test_every_error_page_names_the_problem_and_the_next_step(
    code: str, status: int, title: str, next_step: str
) -> None:
    response, _ = errors.error_page(code, env=ENV, client=BENIGN_NAME, seconds=30)
    document = parse(response)
    assert response.status_code == status
    assert title in document.text
    assert next_step in document.text
    assert document.tags.count("h1") == 1
    assert icons.CROSS in body(response)


@pytest.mark.parametrize(("code", "status", "title", "next_step"), ERROR_PAGES)
def test_every_error_page_carries_the_security_headers_of_the_shell(
    code: str, status: int, title: str, next_step: str
) -> None:
    response, _ = errors.error_page(code, env=ENV, client=BENIGN_NAME, seconds=30)
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize(("code", "status", "title", "next_step"), ERROR_PAGES)
def test_no_error_page_tells_the_attacker_which_check_fired(
    code: str, status: int, title: str, next_step: str
) -> None:
    response, _ = errors.error_page(code, env=ENV, client=HOSTILE_NAME, seconds=30)
    rendered = body(response)
    for needle in FORBIDDEN_ON_ERROR_PAGES:
        assert needle not in rendered, f"{code} leaks {needle!r}"
    readable = parse(response).text
    for needle in FORBIDDEN_IN_ERROR_TEXT:
        assert needle not in readable, f"{code} breaks a copy rule with {needle!r}"


def test_the_table_has_exactly_the_nine_pages_of_the_contract() -> None:
    expected = tuple(code for code, _, _, _ in ERROR_PAGES)
    assert expected == errors.CODES


def test_the_client_name_on_an_error_page_is_cleaned_and_escaped() -> None:
    benign = parse(errors.error_page("E1", env=ENV, client=BENIGN_NAME)[0])
    hostile = parse(errors.error_page("E1", env=ENV, client=HOSTILE_NAME)[0])
    assert hostile.tags == benign.tags
    assert "Bad Client" in hostile.text
    long_name = "N" * 200
    assert long_name not in error_body("E1", client=long_name)


def test_an_error_page_without_a_client_name_still_reads_as_a_sentence() -> None:
    rendered = error_body("E1")
    assert strings.CLIENT_NAME_FALLBACK in rendered


def test_the_timeout_page_offers_the_way_back() -> None:
    document = parse(errors.error_page("E4", env=ENV)[0])
    assert strings.ACTION_START_OVER in document.text
    assert document.tags.count("a") == 1
    for target in document.values_of("href"):
        assert target.startswith("/")
        assert "://" not in target


def test_the_return_address_page_names_the_way_that_works() -> None:
    """The half BL-14 was open about, decided by the owner on 2026-08-20: a reader who is
    refused over a return address gets the way that works named (the app password path),
    and still learns nothing about which of the four checks in ``oauth/consent.py`` fell.

    The word ``cursor`` is asked of the document without its stylesheet, because the
    stylesheet of every page carries a ``cursor: pointer`` declaration that no user ever
    reads and that says nothing about any client. Everything else of the document counts,
    markup and attributes included, because a leak in an attribute is still a leak.
    """
    response, _ = errors.error_page("E5", env=ENV, client=BENIGN_NAME)
    document = parse(response)
    without_stylesheet = re.sub(r"<style.*?</style>", "", body(response), flags=re.DOTALL)

    assert "app password" in document.text
    assert "Start the connection again" in document.text
    assert "cursor" not in without_stylesheet.lower()
    assert "://" not in without_stylesheet
    assert "cursor" not in strings.ERROR_REDIRECT_BODY.lower()


# --- E9, the page of an account that paused its own access (BL-10) ------------------------
#
# The answer of the three enforcement points of plan 05-02. It is a page and not a wire
# answer, because all three of them are reached by a browser in the middle of a sign in, and
# what the reader needs is the one sentence that says why plus the way to the switch.


def test_the_paused_page_refuses_with_403_and_never_challenges_the_browser() -> None:
    """The same choice as R1 at the transport boundary, and for the same reason: a 401 with
    a challenge sends an OAuth client into the full rediscovery loop, and a 401 on a page a
    browser opened invites the browser's own password prompt."""
    response, _ = errors.error_page("E9", env=ENV)

    assert response.status_code == 403
    assert "www-authenticate" not in response.headers
    assert response.headers["cache-control"] == "no-store"


def test_the_paused_page_names_the_state_and_where_the_switch_is() -> None:
    document = parse(errors.error_page("E9", env=ENV)[0])

    assert strings.CONNECTIONS_PAUSED_TITLE in document.text
    assert strings.SWITCH_OFF_STATE in document.text
    assert strings.SETTINGS_PLACE in document.text


def test_the_paused_page_offers_exactly_one_link_and_it_is_the_connections_page() -> None:
    """The prefix comes from the configured public URL: HaRP strips ``/exapps/<app>`` before
    this application sees a request, so a path without it points at the Nextcloud root."""
    document = parse(errors.error_page("E9", env=ENV)[0])

    assert document.tags.count("a") == 1
    target = document.values_of("href")[0]
    assert target.startswith(PREFIX), target
    assert target.endswith(connections.CONNECTIONS_PATH), target
    assert "://" not in target, "a local path, never an origin of its own"


def test_the_paused_page_names_no_account_and_no_client() -> None:
    """The refusal is about a setting of an account, so it names neither (T-03-24)."""
    rendered = body(errors.error_page("E9", env=ENV, client=HOSTILE_NAME)[0])

    assert "Bad Client" not in rendered
    assert strings.CLIENT_NAME_FALLBACK not in rendered
    assert HOSTILE_NAME not in rendered


def test_the_throttled_page_carries_retry_after_with_the_number_of_its_own_text() -> None:
    response, _ = errors.error_page("E6", env=ENV, seconds=42)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    assert "Wait 42 seconds" in parse(response).text


def test_the_throttled_page_never_promises_an_immediate_retry() -> None:
    response, _ = errors.error_page("E6", env=ENV, seconds=0)
    assert int(response.headers["retry-after"]) >= 1


def test_two_generic_pages_carry_two_different_references() -> None:
    """The reference correlates with one log line and decodes to nothing else."""
    first_response, first = errors.error_page("E7", env=ENV)
    second_response, second = errors.error_page("E7", env=ENV)
    assert first != second
    assert len(first) == errors.REFERENCE_LENGTH
    assert set(first) <= set(errors.REFERENCE_ALPHABET)
    assert first in parse(first_response).text
    assert second in parse(second_response).text


@pytest.mark.parametrize("code", ["E1", "E2", "E3", "E4", "E5", "E6", "E8", "E9"])
def test_only_the_generic_page_carries_a_reference(code: str) -> None:
    _, reference = errors.error_page(code, env=ENV, seconds=30)
    assert reference == ""


def test_an_unknown_code_lands_on_the_generic_page_and_never_on_an_empty_one() -> None:
    """Fail closed (D-37): a caller with a typo still answers something a user can act on."""
    response, reference = errors.error_page("nope", env=ENV)
    assert response.status_code == 500
    document = parse(response)
    assert strings.ERROR_GENERIC_TITLE in document.text
    assert reference in document.text
    assert reference != ""
