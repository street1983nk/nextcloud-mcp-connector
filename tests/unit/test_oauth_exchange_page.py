"""The pages of the exchange enrollment (CRED-02, plan 23-06).

The module under test only renders, through ``layout.page`` like every other page of this
project, so the checks here are the ones every page family gets: the security headers, the
forms with their named action field and hidden values, the escaping of the one foreign
value this surface prints (the acting party), and the rule that the flow id travels in the
address and never in the readable text.
"""

from datetime import UTC, datetime
from html.parser import HTMLParser

import pytest
from starlette.responses import Response

from mcp_connector import config
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.exapp.ui import exchange, strings
from mcp_connector.oauth import exchange_enroll

ENV = {config.ENV_PUBLIC_URL: "https://mcp.example.com"}

#: An acting party as a foreign realm could send it: markup, quotes and a control
#: character. Nothing of it may reach the document as anything but text (T-04-34 shape).
HOSTILE_PARTY = '<script>alert("x")</script>\r\n\x07Bad Party'

FLOW_ID = "flow-abc-123"
LOGIN_URL = "https://nc.test/login/v2/flow/abc"
CREATED_AT = 1_766_000_000


class Document(HTMLParser):
    """A minimal reader for the questions the checks ask about a rendered page."""

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

    def hidden_fields(self) -> dict[str, str]:
        """Every hidden input of the document, name to value."""
        fields: dict[str, str] = {}
        pending: dict[int, dict[str, str]] = {}
        index = -1
        for tag, name, value in self.attributes:
            if tag != "input":
                continue
            if name == "type":
                index += 1
            record = pending.setdefault(index, {})
            record[name] = value or ""
        for record in pending.values():
            if record.get("type") == "hidden" and "name" in record:
                fields[record["name"]] = record.get("value", "")
        return fields

    def values_of(self, attribute: str) -> list[str]:
        return [value or "" for _, name, value in self.attributes if name == attribute]


def parse(response: Response) -> Document:
    document = Document()
    document.feed(body(response))
    return document


def body(response: Response) -> str:
    return bytes(response.body).decode("utf-8")


def binding(acting_party: str = "f13-orchestrator") -> exchange.Binding:
    return exchange.Binding(
        auth_id="binding-handle-1",
        created_at=CREATED_AT,
        acting_party=acting_party,
        token="anti-forgery-value-1",
    )


def every_page() -> list[Response]:
    return [
        exchange.invitation_page(env=ENV),
        exchange.invitation_page(result=exchange.RESULT_REVOKED, env=ENV),
        exchange.handoff_page(LOGIN_URL, FLOW_ID, env=ENV),
        exchange.waiting_page(FLOW_ID, env=ENV),
        exchange.identity_page("/oidc/start", {"flow": FLOW_ID, "confirm": "tok"}, env=ENV),
        exchange.bound_page(binding(), user="Alice Example", env=ENV),
    ]


# --- one truth about the path and the parameter names --------------------------------------


def test_the_enroll_path_is_one_truth_shared_with_the_mechanics() -> None:
    """The page and the mechanics may not hold two truths about one address."""
    assert exchange.ENROLL_PATH == "/exchange"
    assert exchange.ENROLL_PATH == exchange_enroll.ENROLL_PATH


def test_the_flow_parameter_is_the_one_the_oidc_callback_writes() -> None:
    """The callback of ``oidc_routes`` sends a finished browser to ``?flow=<id>``, spelled
    with the consent parameter; a second spelling here would break that return silently."""
    assert exchange.FLOW_PARAM == ui_consent.FLOW_PARAM


# --- headers, on every page -----------------------------------------------------------------


def test_every_page_answers_with_the_headers_of_this_surface() -> None:
    for response in every_page():
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        policy = response.headers["content-security-policy"]
        for directive in (
            "default-src 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
        ):
            assert directive in policy


def test_no_page_names_a_credential_a_claim_or_a_token_string() -> None:
    """The wording talks about a service acting for the user, never about the mechanics."""
    for response in every_page():
        text = parse(response).text.lower()
        assert "app password" not in text
        assert "claim" not in text
        assert "token" not in text


# --- the invitation --------------------------------------------------------------------------


def test_the_invitation_carries_exactly_one_form_with_the_start_action() -> None:
    document = parse(exchange.invitation_page(env=ENV))

    assert document.tags.count("form") == 1
    assert document.values_of("action") == [exchange.ENROLL_PATH]
    buttons = [
        (name, value)
        for tag, name, value in document.attributes
        if tag == "button" and name in ("name", "value")
    ]
    assert ("name", exchange.ACTION_FIELD) in buttons
    assert ("value", exchange.ACTION_START) in buttons
    assert document.hidden_fields() == {}


def test_the_invitation_says_what_it_allows_and_that_it_can_be_withdrawn() -> None:
    text = parse(exchange.invitation_page(env=ENV)).text
    assert strings.EXCHANGE_REACH in text
    assert strings.EXCHANGE_REVOKE_ANYTIME in text


def test_the_results_of_a_revocation_are_their_own_callouts() -> None:
    revoked = parse(exchange.invitation_page(result=exchange.RESULT_REVOKED, env=ENV)).text
    gone = parse(exchange.invitation_page(result=exchange.RESULT_GONE, env=ENV)).text

    assert strings.EXCHANGE_REVOKED_TITLE in revoked
    assert strings.EXCHANGE_GONE_TITLE in gone
    assert strings.EXCHANGE_REVOKED_TITLE not in gone
    with pytest.raises(ValueError, match="unknown result"):
        exchange.invitation_page(result="surprise", env=ENV)


# --- the handoff and the waiting screen ------------------------------------------------------


def test_the_handoff_page_carries_the_sign_in_link_in_its_own_window() -> None:
    document = parse(exchange.handoff_page(LOGIN_URL, FLOW_ID, env=ENV))

    assert LOGIN_URL in document.values_of("href")
    anchors = [(name, value) for tag, name, value in document.attributes if tag == "a" and value]
    assert ("target", "_blank") in anchors
    assert ("rel", "noopener noreferrer") in anchors


def test_the_waiting_page_refreshes_itself() -> None:
    response = exchange.waiting_page(FLOW_ID, env=ENV)
    assert '<meta http-equiv="refresh" content="3">' in body(response)


def test_the_flow_id_stands_in_the_address_and_never_in_the_text() -> None:
    for response in (
        exchange.waiting_page(FLOW_ID, env=ENV),
        exchange.handoff_page(LOGIN_URL, FLOW_ID, env=ENV),
    ):
        document = parse(response)
        assert FLOW_ID not in document.text
        # The way into the address: the "Check now" GET form carries it as a hidden value.
        assert document.hidden_fields()[exchange.FLOW_PARAM] == FLOW_ID
        assert ("form", "method", "get") in document.attributes


# --- the step to the independent sign in -----------------------------------------------------


def test_the_identity_page_posts_the_fields_of_the_step() -> None:
    fields = {"flow": FLOW_ID, "confirm": "proof-form-value"}
    document = parse(exchange.identity_page("/oidc/start", fields, env=ENV))

    assert document.values_of("action") == ["/oidc/start"]
    assert document.hidden_fields() == fields
    assert strings.CONSENT_CONFIRM_ACTION in document.text


# --- the bound page ---------------------------------------------------------------------------


def test_the_bound_page_shows_account_date_and_acting_party() -> None:
    document = parse(exchange.bound_page(binding(), user="Alice Example", env=ENV))

    moment = datetime.fromtimestamp(CREATED_AT, tz=UTC)
    assert "Alice Example" in document.text
    assert f"{moment.day} {moment.strftime('%B')} {moment.year}" in document.text
    assert "f13-orchestrator" in document.text


def test_the_bound_page_carries_exactly_one_revoke_form_with_hidden_values() -> None:
    document = parse(exchange.bound_page(binding(), user="Alice Example", env=ENV))

    assert document.tags.count("form") == 1
    assert document.values_of("action") == [exchange.ENROLL_PATH]
    assert document.hidden_fields() == {
        exchange.AUTH_PARAM: "binding-handle-1",
        exchange.TOKEN_PARAM: "anti-forgery-value-1",
    }
    buttons = [
        (name, value)
        for tag, name, value in document.attributes
        if tag == "button" and name in ("name", "value")
    ]
    assert ("name", exchange.ACTION_FIELD) in buttons
    assert ("value", exchange.ACTION_REVOKE) in buttons
    # The handle is a hidden value and never readable text.
    assert "binding-handle-1" not in document.text


def test_a_hostile_acting_party_reaches_the_page_quoted() -> None:
    document = parse(
        exchange.bound_page(binding(acting_party=HOSTILE_PARTY), user="Alice", env=ENV)
    )

    assert "script" not in document.tags
    # The markup arrives as text: the parser decodes the escapes back into characters.
    assert '<script>alert("x")</script>' in document.text
