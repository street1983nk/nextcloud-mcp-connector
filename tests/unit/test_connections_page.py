"""The connections page of EXAPP-02: the four screens, E8 and the routes behind them.

Two rules drive the harsher checks of this file, both inherited from phase 3:

* the app name of a row comes from a dynamic client registration, so it is attacker input
  (T-03-20, T-04-34). The escaping check therefore parses the document and compares the
  element sequence instead of looking for a substring: a substring check passes happily
  while the page grew a second form;
* the connection handle is the value a stranger would guess (T-04-31), so it may travel in
  a hidden field and nowhere else, and the three cases "unknown", "not yours" and "already
  revoked" have to answer the same page.

Nothing here talks to Nextcloud: the store is a SQLite file in ``tmp_path``, the data key
is a constant of this file, and the identity of a request is the AppAPI header HaRP would
sign. The host in every sentence comes from the configured public URL and never from a
request (T-03-02).
"""

import asyncio
import base64
import calendar
import re
import sqlite3
import time
from collections.abc import Coroutine, Iterator, Mapping
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from mcp.shared.auth import OAuthClientInformationFull
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp.browser_identity import AppApiBrowserIdentitySource
from mcp_connector.exapp.target import exapp_target
from mcp_connector.exapp.ui import connections as ui
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.exapp.ui import errors, icons, layout, strings
from mcp_connector.oauth import connections as routes
from mcp_connector.oauth import consent, crypto, loginflow, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import store as store_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth import verifier as verifier_module
from mcp_connector.oauth.metadata import TOOL_SCOPE
from mcp_connector.oauth.store import OAuthStore

PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
HOST = "cloud.example.com"
PREFIX = "/exapps/mcp_connector"

ENV = {config.ENV_PUBLIC_URL: PUBLIC_URL}

#: An installation whose administrator has not entered a public address yet. A store install
#: in NC 34 passes no variable into the container at all, so an empty environment is what a
#: fresh one click installation actually looks like (05-RESEARCH, pitfall 2).
NO_PUBLIC_URL: dict[str, str] = {}

#: What the identity line and the bar of such an installation show: the netloc of the
#: documented default, because the page never takes a host out of a request (T-03-02).
DEFAULT_HOST = urlsplit(config.DEFAULT_PUBLIC_URL).netloc

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"

#: The deploy environment of a running ExApp, which the routes need for two things: the
#: prefix of every form action, and the AppAPI handshake that names the account.
SERVED_ENV = {
    **ENV,
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: "http://nc.test",
}

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

NC_USER = "alice"
OTHER_USER = "bob"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
RESOURCE = f"{PUBLIC_URL}/mcp"

CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
SECOND_CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000002"
CLIENT_NAME = "Claude"
SECOND_CLIENT_NAME = "Another assistant"
AUTH_ID = "authorization-of-alice-0001"
SECOND_AUTH_ID = "authorization-of-alice-0002"
FOREIGN_AUTH_ID = "authorization-of-bob-0001"
TOKEN = "an-anti-forgery-value-of-this-row"
SWITCH_TOKEN = "an-anti-forgery-value-of-the-switch"

#: 12 August 2026, 21:30 UTC. Late enough in the day that a local zone east of UTC would
#: render the next day, which is how the UTC rule of 04-UI-SPEC.md S5 is asserted.
CREATED_AT = calendar.timegm((2026, 8, 12, 21, 30, 0, 0, 0, 0))
CONNECTED_ON = "12 August 2026"

#: The section heading as it stands in the document. Compared as markup on purpose: the
#: words "Connected apps" also stand inside the sentence of the switch, so a bare substring
#: would find the wrong one and an order check would silently assert nothing.
SECTION_HEADING = f"<h2>{strings.CONNECTIONS_SECTION}</h2>"

#: A client name as a registration could send it: markup, quotes, a line break and a
#: control character. Nothing of it may reach the document as anything but text.
HOSTILE_NAME = '<script>alert("x")</script>\r\n\x07Bad Client'


class Document(HTMLParser):
    """A minimal reader for the questions these checks ask about a rendered page."""

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


def body(response: Response) -> str:
    return bytes(response.body).decode("utf-8")


def parse(response: Response) -> Document:
    document = Document()
    document.feed(body(response))
    return document


def connection(
    *,
    auth_id: str = AUTH_ID,
    client_name: str = CLIENT_NAME,
    client_id: str = CLIENT_ID,
    created_at: int = CREATED_AT,
    token: str = TOKEN,
) -> ui.Connection:
    return ui.Connection(
        auth_id=auth_id,
        client_name=client_name,
        client_id=client_id,
        created_at=created_at,
        token=token,
    )


def listing(
    *,
    rows: list[ui.Connection] | None = None,
    paused: bool = False,
    result: str = "",
    result_client: str = "",
    env: Mapping[str, str] | None = None,
) -> Response:
    return ui.connections_page(
        [connection()] if rows is None else rows,
        user=NC_USER,
        paused=paused,
        switch_token=SWITCH_TOKEN,
        result=result,
        result_client=result_client,
        env=ENV if env is None else env,
    )


def order_of(text: str, *needles: str) -> list[int]:
    """Where each of these sentences stands in the document, so an order can be asserted."""
    places = []
    for needle in needles:
        place = text.find(needle)
        assert place >= 0, f"{needle!r} is not in the page at all"
        places.append(place)
    return places


# --- S5, the list ------------------------------------------------------------------


def test_the_list_shows_every_fact_of_a_connection_once() -> None:
    """S5: who is asking, who is signed in, and the three facts of a row."""
    document = parse(listing())

    assert strings.WORDMARK in document.text
    assert HOST in document.text
    assert strings.CONNECTIONS_TITLE in document.text
    assert strings.CONSENT_IDENTITY.format(user=NC_USER, host=HOST) in document.text
    assert strings.CONNECTIONS_SECTION in document.text
    assert CLIENT_NAME in document.text
    assert CLIENT_ID in document.text, "the client id is shown in full and never shortened"
    assert strings.CONNECTIONS_ROW_CONNECTED.format(date=CONNECTED_ON) in document.text
    assert strings.CONNECTIONS_FOOTNOTE in document.text
    assert strings.CONNECT_TITLE in document.text, "the way to the onboarding page"
    assert strings.FOOTER_PASSWORD_PROMPT in document.text


def test_the_list_is_a_real_list_with_one_item_per_connection() -> None:
    """A screen reader has to hear how many connections there are (04-UI-SPEC.md, A11y)."""
    document = parse(listing(rows=[connection(), connection(auth_id=SECOND_AUTH_ID)]))

    assert document.tags.count("li") == 2
    assert "table" not in document.tags
    assert document.values_of("class").count("row") == 2


def test_every_row_carries_its_own_form_and_its_own_accessible_name() -> None:
    """One form per row, and a button whose name is not five times the same word."""
    document = parse(listing(rows=[connection(), connection(auth_id=SECOND_AUTH_ID)]))
    text = body(listing())

    assert document.tags.count("form") == 3, "two rows plus the switch"
    assert f'aria-label="Disconnect {CLIENT_NAME}"' in text
    assert f'action="{PREFIX}{ui.CONNECTIONS_PATH}"' in text


def test_the_date_of_a_row_is_day_month_year_in_utc() -> None:
    """12 August 2026, not 12/08/2026 and not the next day of a local zone."""
    text = body(listing())

    assert CONNECTED_ON in text
    assert "13 August 2026" not in text, "the date is computed in UTC, not in a local zone"
    assert not re.search(r"\d{2}/\d{2}/\d{4}", text)
    assert "21:30" not in text, "no time of day in a list whose unit is a connection"


def test_the_handle_of_a_row_is_never_visible_text() -> None:
    """T-04-31: the handle of a credential travels in a hidden field and nowhere else."""
    response = listing()

    assert AUTH_ID not in parse(response).text
    assert f'value="{AUTH_ID}"' in body(response)


def test_the_switch_block_is_the_on_state_plus_a_secondary_button() -> None:
    """Access on: no accent on this page, and the brake is present but not advertised."""
    text = body(listing())

    assert strings.SWITCH_ON_STATE in text
    assert strings.SWITCH_TURN_OFF in text
    assert f'class="btn-secondary" type="submit" name="{ui.ACTION_FIELD}"' in text
    assert f'value="{ui.ACTION_PAUSE}"' in text
    assert strings.CONNECTIONS_PAUSED_TITLE not in text
    assert '<button class="btn-primary"' not in text, "access on: this page has no accent button"


def test_a_paused_account_gets_the_primary_button_and_the_warning() -> None:
    """The named accent exception: the page state is degraded, so the way back is primary."""
    response = listing(paused=True)
    text = body(response)

    assert strings.SWITCH_OFF_STATE in text
    assert strings.SWITCH_TURN_ON in text
    assert f'value="{ui.ACTION_RESUME}"' in text
    assert "btn-primary" in text
    assert strings.CONNECTIONS_PAUSED_TITLE in parse(response).text
    assert strings.CONNECTIONS_PAUSED_BODY in parse(response).text
    assert icons.WARNING in text


def test_the_switch_block_stands_directly_above_the_pause_warning() -> None:
    """The callout stops being a pointer to Nextcloud: the way back is one line above it."""
    state, warning, section = order_of(
        body(listing(paused=True)),
        strings.SWITCH_OFF_STATE,
        strings.CONNECTIONS_PAUSED_TITLE,
        SECTION_HEADING,
    )

    assert state < warning < section


def test_the_paused_body_no_longer_points_at_the_nextcloud_settings() -> None:
    """Amended 2026-08-17: the switch sits on this page, so the pointer sentence is gone."""
    assert strings.SETTINGS_PLACE not in strings.CONNECTIONS_PAUSED_BODY
    assert strings.SETTINGS_PLACE in strings.ACCESS_DISABLED_DESCRIPTION


# --- the setup state of an installation without a public address (05-04) ------------


def setup_copy() -> str:
    """The three sentences of the setup notice, as one text to ask questions about."""
    return " ".join(
        (
            strings.SETUP_PUBLIC_URL_TITLE,
            strings.SETUP_PUBLIC_URL_BODY,
            strings.SETUP_PUBLIC_URL_HINT,
        )
    )


def test_the_setup_notice_stands_above_everything_else_of_the_list() -> None:
    """05-RESEARCH pitfall 2, stage 3: the page a user opens first says what is missing.

    A store installation in NC 34 sets no variable, so ``config.public_url`` answers the
    documented loopback default and no client can ever connect. Without this notice the first
    symptom is an assistant app that fails at discovery, which looks like a client problem.
    """
    response = listing(env=NO_PUBLIC_URL)
    document = parse(response)
    notice, identity, section = order_of(
        body(response),
        strings.SETUP_PUBLIC_URL_TITLE,
        strings.CONSENT_IDENTITY.format(user=NC_USER, host=DEFAULT_HOST),
        SECTION_HEADING,
    )

    assert strings.SETUP_PUBLIC_URL_TITLE in document.text
    assert strings.SETUP_PUBLIC_URL_BODY in document.text
    assert strings.SETUP_PUBLIC_URL_HINT in document.text
    assert icons.WARNING in body(response)
    assert notice < identity < section, "the cause of the state stands above the state"


def test_the_setup_notice_is_there_in_the_empty_state_as_well() -> None:
    """The cause is not the list, so it is not a state of the list (S6)."""
    document = parse(listing(rows=[], env=NO_PUBLIC_URL))

    assert strings.SETUP_PUBLIC_URL_TITLE in document.text
    assert strings.CONNECTIONS_EMPTY_TITLE in document.text


def test_the_setup_notice_is_there_while_the_account_is_paused() -> None:
    """Both callouts at once, and the setup one first: it is why nothing works at all."""
    response = listing(paused=True, env=NO_PUBLIC_URL)
    setup, paused = order_of(
        body(response), strings.SETUP_PUBLIC_URL_TITLE, strings.CONNECTIONS_PAUSED_TITLE
    )

    assert setup < paused
    assert strings.CONNECTIONS_PAUSED_TITLE in parse(response).text


def test_a_configured_address_renders_no_setup_notice() -> None:
    """A configured installation is character for character the page it was before."""
    response = listing()
    text = body(response)

    for sentence in (
        strings.SETUP_PUBLIC_URL_TITLE,
        strings.SETUP_PUBLIC_URL_BODY,
        strings.SETUP_PUBLIC_URL_HINT,
    ):
        assert sentence not in text
    assert icons.WARNING not in text, "an access-on page without a pause has no callout at all"
    assert text.count('class="callout') == 0
    assert body(listing(env=NO_PUBLIC_URL)).count('class="callout callout-warning"') == 1, (
        "the notice is exactly one callout and adds no second surface"
    )


def test_the_setup_state_keeps_the_status_code_and_the_headers_of_the_page() -> None:
    """A page that explains itself is not an error, and it stays uncacheable (T-04-32)."""
    for response in (
        listing(env=NO_PUBLIC_URL),
        listing(rows=[], env=NO_PUBLIC_URL),
        listing(paused=True, env=NO_PUBLIC_URL),
    ):
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


def test_the_setup_copy_names_the_place_and_the_step_and_never_a_value() -> None:
    """T-05-21: the notice names where the value goes, never a value and never a host.

    The loopback default is the value this state is caused by, and repeating it would put an
    internal address in front of every user of the instance for no gain: nobody can act on
    ``127.0.0.1:8765``, and the only useful sentence is where the real address is entered.
    """
    text = setup_copy()

    assert strings.ADMIN_SETTINGS_PLACE in text
    assert "disable and enable" in text
    assert config.DEFAULT_PUBLIC_URL not in text
    assert "127.0.0.1" not in text
    assert strings.ADMIN_PUBLIC_URL_EXAMPLE in text, "the shape of the address, as an example"


def test_the_condition_of_the_notice_is_the_documented_default() -> None:
    """One comparison, in one helper, so all three states of the page share it."""
    assert config.public_url(NO_PUBLIC_URL) == config.DEFAULT_PUBLIC_URL
    assert config.public_url(ENV) != config.DEFAULT_PUBLIC_URL


# --- S6, the empty state -----------------------------------------------------------


def test_the_empty_state_is_the_same_shell_and_answers_200() -> None:
    """S6: a state of the same page and not an error."""
    response = listing(rows=[])
    document = parse(response)

    assert response.status_code == 200
    assert strings.CONNECTIONS_EMPTY_TITLE in document.text
    assert strings.CONNECTIONS_EMPTY_BODY in document.text
    assert strings.CONSENT_IDENTITY.format(user=NC_USER, host=HOST) in document.text
    assert strings.CONNECTIONS_FOOTNOTE in document.text
    assert strings.CONNECT_TITLE in document.text
    assert "ul" not in document.tags, "no empty list, and no section heading above one"
    assert SECTION_HEADING not in body(response)


def test_the_empty_state_keeps_the_switch_and_its_warning() -> None:
    """The switch belongs to the account, not to the list, so it survives an empty one."""
    document = parse(listing(rows=[], paused=True))

    assert strings.SWITCH_OFF_STATE in document.text
    assert strings.CONNECTIONS_PAUSED_TITLE in document.text


# --- S7, the confirmation ----------------------------------------------------------


def test_the_confirm_page_names_the_app_and_the_limit_of_the_consequence() -> None:
    document = parse(ui.confirm_page(connection(), env=ENV))

    assert strings.DISCONNECT_TITLE.format(client=CLIENT_NAME) in document.text
    assert strings.DISCONNECT_BODY.format(client=CLIENT_NAME) in document.text
    assert strings.DISCONNECT_AGAIN in document.text
    assert strings.CONSENT_DETAIL_APP_NAME in document.text
    assert strings.CONSENT_DETAIL_CLIENT_ID in document.text
    assert strings.CONNECTIONS_DETAIL_CONNECTED in document.text
    assert CONNECTED_ON in document.text


def test_the_confirm_page_offers_keep_before_disconnect_in_one_form() -> None:
    """The safe action is reachable first, exactly as deny comes before approve (S3)."""
    response = ui.confirm_page(connection(), env=ENV)
    text = body(response)
    keep, disconnect = order_of(
        text, f">{strings.DISCONNECT_KEEP}<", f">{strings.DISCONNECT_ACTION}<"
    )

    assert keep < disconnect
    assert parse(response).tags.count("form") == 1
    assert text.count("<button") == 2
    assert f'class="btn-primary" type="submit" name="{ui.ACTION_FIELD}"' in text
    assert f'value="{ui.ACTION_DISCONNECT}"' in text


def test_the_confirm_page_opens_with_the_focus_on_its_heading() -> None:
    """A page that opens with the acting button focused turns a stray Enter into the act."""
    text = body(ui.confirm_page(connection(), env=ENV))

    assert '<h1 class="heading" tabindex="-1" autofocus>' in text


def test_the_confirm_page_carries_the_handle_and_the_hmac_as_hidden_fields_only() -> None:
    response = ui.confirm_page(connection(), env=ENV)
    document = parse(response)
    text = body(response)

    assert AUTH_ID not in document.text
    assert TOKEN not in document.text
    assert f'<input type="hidden" name="{ui.AUTH_PARAM}" value="{AUTH_ID}">' in text
    assert f'<input type="hidden" name="{ui.CONFIRM_PARAM}" value="{TOKEN}">' in text


# --- S8, the result of a disconnect ------------------------------------------------


def test_a_finished_disconnect_answers_the_list_with_the_success_callout() -> None:
    response = listing(rows=[], result=ui.RESULT_DONE, result_client=CLIENT_NAME)
    document = parse(response)

    assert response.status_code == 200
    assert strings.DISCONNECT_DONE_TITLE in document.text
    assert strings.DISCONNECT_DONE_BODY.format(client=CLIENT_NAME) in document.text
    assert icons.CHECK in body(response)


def test_a_disconnect_of_something_that_is_gone_says_so_calmly() -> None:
    response = listing(result=ui.RESULT_GONE)
    document = parse(response)

    assert response.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in document.text
    assert strings.DISCONNECT_GONE_BODY in document.text
    assert icons.WARNING in body(response)


def test_the_result_callout_stands_before_the_pause_warning() -> None:
    """Both can appear at once, and the order is fixed: result first, condition second."""
    result, warning, section = order_of(
        body(listing(paused=True, result=ui.RESULT_DONE, result_client=CLIENT_NAME)),
        strings.DISCONNECT_DONE_TITLE,
        strings.CONNECTIONS_PAUSED_TITLE,
        SECTION_HEADING,
    )

    assert result < warning < section


# --- the attacker input of this surface --------------------------------------------


def test_a_hostile_client_name_does_not_add_a_single_element() -> None:
    """T-04-34: a registration must not be able to write page copy or a second form."""
    benign = parse(listing())
    hostile = parse(listing(rows=[connection(client_name=HOSTILE_NAME)]))

    assert hostile.tags == benign.tags
    assert "script" not in hostile.tags
    assert "<script" not in body(listing(rows=[connection(client_name=HOSTILE_NAME)]))


def test_a_hostile_client_name_is_readable_as_text() -> None:
    """Escaped, not swallowed: the user has to see what the app calls itself."""
    document = parse(listing(rows=[connection(client_name=HOSTILE_NAME)]))

    assert "Bad Client" in document.text
    assert "\x07" not in document.text
    assert "\r" not in document.text


def test_a_hostile_client_name_stays_text_on_every_screen_of_this_family() -> None:
    """The confirmation page and the result callout carry the same name (T-04-34)."""
    confirm = parse(ui.confirm_page(connection(client_name=HOSTILE_NAME), env=ENV))
    result = parse(listing(result=ui.RESULT_DONE, result_client=HOSTILE_NAME))

    assert "script" not in confirm.tags
    assert "script" not in result.tags
    assert "Bad Client" in confirm.text
    assert "Bad Client" in result.text


def test_a_nameless_registration_is_shown_as_the_fallback_wording() -> None:
    document = parse(listing(rows=[connection(client_name="")]))

    assert strings.CLIENT_NAME_FALLBACK in document.text


# --- E8, not signed in -------------------------------------------------------------


def test_e8_is_a_403_that_names_the_host_and_offers_no_link() -> None:
    """403 and not 401: this surface never puts a password prompt in front of a user."""
    response, reference = errors.error_page("E8", env=ENV)
    document = parse(response)

    assert response.status_code == 403
    assert reference == "", "E8 is not the generic page and needs no reference"
    assert strings.ERROR_SIGN_IN_TITLE in document.text
    assert strings.ERROR_SIGN_IN_BODY.format(host=HOST) in document.text
    assert "a" not in document.tags, "no invented link to a sign in page"
    assert "{host}" not in document.text


def test_e8_is_a_row_of_the_existing_table_and_not_a_new_mechanism() -> None:
    """Compared against the generic page and no longer against a position (05-02).

    The check used to read ``len(CODES) - 2``, which said "second to last" while it meant
    "before the generic page". E9 joined the table between the two in plan 05-02 and the
    check failed without anything being wrong, which is what a positional assertion buys.
    """
    assert "E8" in errors.CODES
    assert errors.CODES.index("E8") < errors.CODES.index(errors.GENERIC)
    assert errors.CODES[-1] == errors.GENERIC, "the generic page stays the fallback row"


# --- the stylesheet and the icons --------------------------------------------------


def test_the_row_list_is_the_one_new_primitive_of_the_stylesheet() -> None:
    """Three rules, exactly the ones of the component inventory, and no new value."""
    assert "ul.rows" in layout.STYLESHEET
    assert "li.row" in layout.STYLESHEET
    assert ".row-title" in layout.STYLESHEET
    assert "border-top: 1px solid #D5D8DD" in layout.STYLESHEET
    assert layout.STYLESHEET.count("#") == len(re.findall(r"#[0-9A-F]{6}", layout.STYLESHEET))


def test_this_phase_adds_no_fourth_icon() -> None:
    """An icon that appears once is an icon nobody learns (04-UI-SPEC.md)."""
    shapes = [name for name in vars(icons) if name.isupper() and not name.startswith("_")]

    assert sorted(shapes) == ["CHECK", "CROSS", "WARNING"]


def test_every_page_of_this_family_carries_the_five_required_headers() -> None:
    """The PHP proxy caches for 3600 seconds unless told otherwise (T-04-32)."""
    for response in (listing(), listing(rows=[]), ui.confirm_page(connection(), env=ENV)):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "form-action 'self'" in response.headers["content-security-policy"]
        assert response.headers["content-type"] == "text/html; charset=utf-8"


# --- the routes behind those screens ------------------------------------------------


class Deployment:
    """The connections route with the store and the provider of one deployment.

    Assembled the way ``entry_exapp`` assembles it, so the disconnect of a row runs through
    the very same ``end_connection`` the token endpoint uses, and the verifier that decides
    whether a token still works shares the store and the revocation hook with it (T-04-35).
    """

    def __init__(self, tmp_path: Path, *, throttle: throttle_module.Throttle | None = None) -> None:
        self.store = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
        self.provider = provider_module.NextcloudOAuthProvider(
            nextcloud=exapp_target(SERVED_ENV),
            env=SERVED_ENV,
            policy=registry.client_policy(SERVED_ENV),
            store_provider=self._open,
        )
        self.verifier = verifier_module.StoreTokenVerifier(
            store_provider=self._open, get_client=self.provider.get_client, env=SERVED_ENV
        )
        self.provider.on_revocation(self.verifier.invalidate)
        # High on purpose: the throttle has its own checks, and a page that throttles itself
        # stops testing the refusals it is here for. A check about the throttle hands in one
        # with the real limits, and it gets the consent surface next to the page, because the
        # question of HI-01 is whether one surface can close the other.
        counters = (
            throttle
            if throttle is not None
            else throttle_module.Throttle(limit=10_000, ceiling=100_000, window=60)
        )
        self.client = TestClient(
            Starlette(
                routes=[
                    *routes.connections_routes(
                        SERVED_ENV,
                        store_provider=self._open,
                        end_connection=self.provider.end_connection,
                        throttle=counters,
                    ),
                    *consent.consent_routes(
                        SERVED_ENV,
                        provider=self.provider,
                        browser_identity=AppApiBrowserIdentitySource(SERVED_ENV),
                        nextcloud=exapp_target(SERVED_ENV),
                        throttle=counters,
                    ),
                ]
            )
        )

    async def _open(self) -> OAuthStore:
        return self.store

    def get(self, user: str = NC_USER) -> Any:
        return self.client.get(ui.CONNECTIONS_PATH, headers=appapi_headers(user))

    def post(self, data: dict[str, str], user: str = NC_USER) -> Any:
        return self.client.post(ui.CONNECTIONS_PATH, data=data, headers=appapi_headers(user))

    def token_of(self, auth_id: str) -> str:
        return self.store.form_token(auth_id, purpose=crypto.PURPOSE_DISCONNECT)

    def switch_token_of(self, user: str = NC_USER) -> str:
        return self.store.form_token(f"{routes.SWITCH_HANDLE}{user}", purpose=crypto.PURPOSE_SWITCH)

    def rows_of(self, user: str = NC_USER) -> list[str]:
        return [row.auth_id for row in run(self.store.authorizations_of_user(user))]


def run[T](work: Coroutine[Any, Any, T]) -> T:
    """One asynchronous call from a synchronous test, the shape the other files use."""
    return asyncio.run(work)


def appapi_headers(user: str) -> dict[str, str]:
    """What HaRP signs onto every request it forwards: an account, or the empty string."""
    token = base64.b64encode(f"{user}:{APP_SECRET}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def registration(client_id: str, client_name: str) -> str:
    """A registration as the DCR endpoint stores it, so ``get_client`` accepts it again."""
    return OAuthClientInformationFull.model_validate(
        {
            "client_id": client_id,
            "client_name": client_name,
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": TOOL_SCOPE,
        }
    ).model_dump_json(exclude={"client_secret"})


def seed(
    deployment: Deployment,
    *,
    auth_id: str = AUTH_ID,
    client_id: str = CLIENT_ID,
    client_name: str = CLIENT_NAME,
    nc_user: str = NC_USER,
    created_at: int = CREATED_AT,
) -> None:
    """One registered client and one live connection of that client to that account."""
    store = deployment.store
    run(
        store.save_client(
            client_id, metadata_json=registration(client_id, client_name), allowed=True
        )
    )
    run(store.touch_client(client_id))
    run(
        store.create_authorization(
            auth_id,
            client_id=client_id,
            nc_user=nc_user,
            app_password=APP_PASSWORD,
            scopes=TOOL_SCOPE,
            resource=RESOURCE,
            now=created_at,
        )
    )


def issue(deployment: Deployment, token: str, *, auth_id: str = AUTH_ID) -> None:
    """An access token and a refresh family of one connection, as the token endpoint does."""
    family = f"family-of-{auth_id}"
    run(
        deployment.store.create_access_token(
            token, auth_id=auth_id, family_id=family, scopes=TOOL_SCOPE, resource=RESOURCE
        )
    )
    run(
        deployment.store.create_refresh_token(f"refresh-{token}", auth_id=auth_id, family_id=family)
    )


def comparable(response: Any) -> str:
    """The answer without the two values that differ per response: the nonce, twice.

    Everything else has to be identical for the three cases of S8, or the page is an
    existence oracle for whoever guesses a handle (T-04-31).
    """
    return re.sub(r'nonce[-=]"?[A-Za-z0-9_-]+', "nonce", response.text)


class Nextcloud:
    """The one Nextcloud call this page can cause, recorded instead of sent.

    A disconnect hands the app password of the connection back (BL-01), which is a
    ``DELETE`` against Nextcloud. Nothing in this file opens a socket, so the call is
    recorded here and the answer is what a test wants it to be.
    """

    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.answer = True

    async def revoke(self, login_name: str, app_password: str, *, target: object) -> bool:
        # Required like the real signature, so a caller without a target fails here too.
        del target
        self.deleted.append((login_name, app_password))
        return self.answer


@pytest.fixture(autouse=True)
def nextcloud(monkeypatch: pytest.MonkeyPatch) -> Nextcloud:
    """Autouse: no test of this file may reach a network, not even by accident."""
    recorder = Nextcloud()
    monkeypatch.setattr(loginflow, "revoke_app_password", recorder.revoke)
    return recorder


@pytest.fixture
def live(tmp_path: Path) -> Deployment:
    deployment = Deployment(tmp_path)
    seed(deployment)
    return deployment


def test_the_page_lists_the_connections_of_the_account_behind_the_browser(
    live: Deployment,
) -> None:
    """S5 over the wire: this account's rows, newest first, and nobody else's."""
    seed(
        live,
        auth_id=SECOND_AUTH_ID,
        client_id=SECOND_CLIENT_ID,
        client_name=SECOND_CLIENT_NAME,
        created_at=CREATED_AT + 86400,
    )
    seed(live, auth_id=FOREIGN_AUTH_ID, nc_user=OTHER_USER)

    response = live.get()
    newest, oldest = order_of(response.text, SECOND_CLIENT_NAME, CLIENT_NAME)

    assert response.status_code == 200
    assert newest < oldest, "newest first"
    assert FOREIGN_AUTH_ID not in response.text, "another account's connections are not listed"
    assert live.token_of(AUTH_ID) in response.text, "every row carries its own hidden value"


def test_an_account_without_connections_gets_the_empty_state(tmp_path: Path) -> None:
    response = Deployment(tmp_path).get()

    assert response.status_code == 200
    assert strings.CONNECTIONS_EMPTY_TITLE in response.text


def test_a_browser_without_a_nextcloud_account_gets_e8_on_both_verbs(live: Deployment) -> None:
    """E8: 403, and nothing about whether that account exists or has connections."""
    listed = live.client.get(ui.CONNECTIONS_PATH, headers=appapi_headers(""))
    acted = live.client.post(
        ui.CONNECTIONS_PATH,
        data={ui.ACTION_FIELD: ui.ACTION_DISCONNECT, ui.AUTH_PARAM: AUTH_ID},
        headers=appapi_headers(""),
    )

    for response in (listed, acted):
        assert response.status_code == 403
        assert strings.ERROR_SIGN_IN_TITLE in response.text
        assert CLIENT_NAME not in response.text
    assert live.rows_of() == [AUTH_ID], "a refused request changes nothing"


def test_a_confirm_of_an_own_connection_is_the_interstitial(live: Deployment) -> None:
    response = live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_CONFIRM,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )

    assert response.status_code == 200
    assert strings.DISCONNECT_TITLE.format(client=CLIENT_NAME) in response.text
    assert live.token_of(AUTH_ID) in response.text
    assert live.rows_of() == [AUTH_ID], "the interstitial changes nothing"


def test_a_confirmation_without_the_anti_forgery_value_hands_no_value_out(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """LO-07: the interstitial changes nothing, and its page carries the next value.

    A foreign origin can post this form. It cannot read the answer and it does not know the
    handle either, so nothing was reachable through it; what remains is one of five actions
    of this page answering a request that carried none of its own values, with the page that
    renders the interstitial of a destructive action. The form of the row carries the value
    already, so the closed enumeration is now closed in the same way five times over.
    """
    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.post({ui.ACTION_FIELD: ui.ACTION_CONFIRM, ui.AUTH_PARAM: AUTH_ID})

    assert response.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in response.text, "the same calm answer as always"
    assert strings.DISCONNECT_TITLE.format(client=CLIENT_NAME) not in response.text
    assert live.rows_of() == [AUTH_ID]
    assert caplog.records


def test_an_unknown_a_foreign_and_a_revoked_handle_answer_the_same_page(
    live: Deployment,
) -> None:
    """T-04-31: a page that told them apart would answer whether a connection exists."""
    seed(live, auth_id=FOREIGN_AUTH_ID, nc_user=OTHER_USER)
    seed(live, auth_id=SECOND_AUTH_ID, client_id=SECOND_CLIENT_ID, client_name=SECOND_CLIENT_NAME)
    run(live.store.revoke_authorization(SECOND_AUTH_ID))

    unknown = live.post({ui.ACTION_FIELD: ui.ACTION_CONFIRM, ui.AUTH_PARAM: "never-existed"})
    foreign = live.post({ui.ACTION_FIELD: ui.ACTION_CONFIRM, ui.AUTH_PARAM: FOREIGN_AUTH_ID})
    revoked = live.post({ui.ACTION_FIELD: ui.ACTION_CONFIRM, ui.AUTH_PARAM: SECOND_AUTH_ID})

    assert comparable(unknown) == comparable(foreign) == comparable(revoked)
    assert strings.DISCONNECT_GONE_TITLE in unknown.text
    assert unknown.status_code == 200


def test_a_disconnect_ends_that_one_connection_and_says_so(live: Deployment) -> None:
    """SC 2: the row is gone, the page says which app lost access, and it stays a page."""
    response = live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )
    row = run(live.store.load_authorization(AUTH_ID))

    assert response.status_code == 200
    assert strings.DISCONNECT_DONE_TITLE in response.text
    assert strings.DISCONNECT_DONE_BODY.format(client=CLIENT_NAME) in response.text
    assert live.rows_of() == []
    assert row is not None
    assert row.revoked_at is not None
    assert row.cleanup_at is None, "the app password went back, so nothing is left to clean up"


def test_a_disconnect_hands_the_app_password_back_to_nextcloud(
    live: Deployment, nextcloud: Nextcloud
) -> None:
    """BL-01: the value behind a connection is a full Nextcloud credential, not a token.

    The page promised "{client} loses access to your Nextcloud immediately" while the app
    password stayed valid at Nextcloud for good: no sweep can see a revoked row
    (``abandoned_authorizations`` filters ``revoked_at IS NULL``), so the visible way out
    was strictly weaker than the machine path of ``/revoke``, which hands it back (WR-04,
    D-34).
    """
    live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )
    row = run(live.store.load_authorization(AUTH_ID))

    assert nextcloud.deleted == [(NC_USER, APP_PASSWORD)], "one attempt, never a retry"
    assert row is not None
    assert row.cleanup_at is None, "the credential is gone from Nextcloud"


def test_a_failed_deletion_still_ends_the_connection_and_keeps_the_note(
    live: Deployment, nextcloud: Nextcloud
) -> None:
    """Pitfall 13: Nextcloud is the slowest participant and may not hold up a disconnect."""
    nextcloud.answer = False

    response = live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )
    row = run(live.store.load_authorization(AUTH_ID))

    assert response.status_code == 200
    assert strings.DISCONNECT_DONE_TITLE in response.text
    assert live.rows_of() == []
    assert row is not None
    assert row.revoked_at is not None
    assert row.cleanup_at is not None, "the orphaned credential is noted, not forgotten"


def test_the_same_form_submitted_again_is_already_disconnected(live: Deployment) -> None:
    """A reload resubmits the form, which is why this answer exists and is not an error."""
    form = {
        ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
        ui.AUTH_PARAM: AUTH_ID,
        ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
    }
    live.post(form)

    again = live.post(form)

    assert again.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in again.text


def test_a_disconnect_leaves_every_other_connection_alone(live: Deployment) -> None:
    """SC 2 in its second half: without affecting the other apps, or another account."""
    seed(live, auth_id=SECOND_AUTH_ID, client_id=SECOND_CLIENT_ID, client_name=SECOND_CLIENT_NAME)
    seed(live, auth_id=FOREIGN_AUTH_ID, nc_user=OTHER_USER)

    live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )

    assert live.rows_of() == [SECOND_AUTH_ID]
    assert live.rows_of(OTHER_USER) == [FOREIGN_AUTH_ID]


@pytest.mark.parametrize("presented", ["", "a-value-of-another-page", "  "])
def test_a_disconnect_without_the_anti_forgery_value_changes_nothing(
    live: Deployment, presented: str, caplog: pytest.LogCaptureFixture
) -> None:
    """T-04-30: a foreign origin can post this form, and it cannot produce this value."""
    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.post(
            {
                ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
                ui.AUTH_PARAM: AUTH_ID,
                ui.CONFIRM_PARAM: presented,
            }
        )

    assert response.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in response.text, "no oracle, the same calm answer"
    assert live.rows_of() == [AUTH_ID]
    assert caplog.records, "a forged form is worth exactly one log line"


def test_a_form_from_the_previous_window_still_disconnects(
    live: Deployment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BL-08: the second accepted window is what a page open across an hour boundary needs.

    The clock is monkeypatched and never slept on: the value is rendered as it would have
    been an hour ago and submitted now.
    """
    with monkeypatch.context() as older:
        older.setattr(crypto, "_unix_time", lambda: _seconds_ago(crypto.FORM_TOKEN_WINDOW))
        presented = live.token_of(AUTH_ID)

    response = live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: presented,
        }
    )

    assert response.status_code == 200
    assert strings.DISCONNECT_DONE_TITLE in response.text
    assert live.rows_of() == []


def test_a_form_older_than_two_windows_is_refused_like_any_other_wrong_value(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """BL-08: the chosen behaviour for an expired value is the quiet refusal that exists.

    No new screen and no error page: the page shows itself again, which is what a user who
    left a tab open overnight sees, and the row is untouched.
    """
    presented = live.store.form_token(
        AUTH_ID,
        purpose=crypto.PURPOSE_DISCONNECT,
        now=_seconds_ago(2 * crypto.FORM_TOKEN_WINDOW + 1),
    )

    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.post(
            {
                ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
                ui.AUTH_PARAM: AUTH_ID,
                ui.CONFIRM_PARAM: presented,
            }
        )

    assert response.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in response.text, "the same calm answer, no oracle"
    assert live.rows_of() == [AUTH_ID], "nothing was disconnected"
    assert caplog.records


def _seconds_ago(seconds: float) -> float:
    """A moment in the past of the real clock, so the windows around it are the real ones."""
    return time.time() - seconds


def test_the_row_value_of_one_connection_does_not_disconnect_another(live: Deployment) -> None:
    """The value is derived from the handle, so it fits one row and one row only."""
    seed(live, auth_id=SECOND_AUTH_ID, client_id=SECOND_CLIENT_ID, client_name=SECOND_CLIENT_NAME)

    response = live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: SECOND_AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )

    assert strings.DISCONNECT_GONE_TITLE in response.text
    assert sorted(live.rows_of()) == sorted([AUTH_ID, SECOND_AUTH_ID])


def test_the_value_of_a_consent_form_does_not_disconnect_that_connection(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """ME-01: the two forms are about the same id, so they must not carry the same value.

    ``consent.py`` writes the authorization under the id of its own flow, which makes
    ``auth_id`` and ``flow_id`` one string. A value derived from that string alone therefore
    authorised two different privileged actions at once, and there is no way to rotate one
    of them without breaking every stored app password. The purpose belongs in the
    derivation, not only in the name of the field.
    """
    presented = live.store.form_token(AUTH_ID, purpose=crypto.PURPOSE_CONSENT)

    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.post(
            {
                ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
                ui.AUTH_PARAM: AUTH_ID,
                ui.CONFIRM_PARAM: presented,
            }
        )

    assert response.status_code == 200
    assert strings.DISCONNECT_GONE_TITLE in response.text, "the same calm answer, no oracle"
    assert live.rows_of() == [AUTH_ID], "nothing was disconnected"
    assert caplog.records


def test_the_switch_pauses_and_resumes_the_account_of_the_browser(live: Deployment) -> None:
    """The proof of effect is the page itself: the callout appears and disappears."""
    paused = live.post({ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.switch_token_of()})

    assert paused.status_code == 200
    assert strings.CONNECTIONS_PAUSED_TITLE in paused.text
    assert run(live.store.access_disabled(NC_USER)) is True
    assert live.rows_of() == [AUTH_ID], "pausing disconnects nothing (D-46)"

    resumed = live.post(
        {ui.ACTION_FIELD: ui.ACTION_RESUME, ui.CONFIRM_PARAM: live.switch_token_of()}
    )

    assert strings.CONNECTIONS_PAUSED_TITLE not in resumed.text
    assert run(live.store.access_disabled(NC_USER)) is False


def test_the_switch_is_a_named_state_and_survives_a_resubmitted_form(live: Deployment) -> None:
    """pause and resume, never toggle: a replayed form re-states a state (04-UI-SPEC.md)."""
    form = {ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.switch_token_of()}
    live.post(form)
    live.post(form)

    assert run(live.store.access_disabled(NC_USER)) is True


def test_the_switch_of_one_account_is_never_the_switch_of_another(live: Deployment) -> None:
    live.post({ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.switch_token_of()})

    assert run(live.store.access_disabled(OTHER_USER)) is False


def test_a_row_value_cannot_pause_the_account(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """The switch value is bound to the account, so a value of a row does not fit it."""
    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.post(
            {ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.token_of(AUTH_ID)}
        )

    assert response.status_code == 200
    assert run(live.store.access_disabled(NC_USER)) is False
    assert strings.CONNECTIONS_PAUSED_TITLE not in response.text
    assert caplog.records


def test_the_switch_value_of_one_account_does_not_pause_another(live: Deployment) -> None:
    response = live.post(
        {ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.switch_token_of(OTHER_USER)}
    )

    assert run(live.store.access_disabled(NC_USER)) is False
    assert strings.CONNECTIONS_PAUSED_TITLE not in response.text


def test_the_keep_button_answers_the_plain_list(live: Deployment) -> None:
    response = live.post({ui.ACTION_FIELD: ui.ACTION_KEEP})

    assert response.status_code == 200
    assert SECTION_HEADING in response.text
    assert strings.DISCONNECT_GONE_TITLE not in response.text
    assert live.rows_of() == [AUTH_ID]


def test_an_action_this_route_does_not_know_is_the_list_and_a_400(live: Deployment) -> None:
    """Not an error a user can act on differently, and not a page of its own."""
    response = live.post({ui.ACTION_FIELD: "delete-everything"})

    assert response.status_code == 400
    assert SECTION_HEADING in response.text
    assert live.rows_of() == [AUTH_ID]


def test_a_get_never_changes_anything(live: Deployment) -> None:
    """T-03-35: the rule that makes a link safe on a page that can end a connection."""
    before = Path(live.store.path).read_bytes()

    live.get()
    live.client.get(
        f"{ui.CONNECTIONS_PATH}?{ui.ACTION_FIELD}={ui.ACTION_DISCONNECT}",
        headers=appapi_headers(NC_USER),
    )

    assert Path(live.store.path).read_bytes() == before


def test_a_disconnect_stops_the_token_of_that_connection_at_once(live: Deployment) -> None:
    """T-03-62: the verifier answers from a five second cache, and this empties it."""
    issue(live, "an-access-token-of-this-connection")
    assert run(live.verifier.verify_token("an-access-token-of-this-connection")) is not None

    live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )

    assert run(live.verifier.verify_token("an-access-token-of-this-connection")) is None


def test_a_disconnect_revokes_the_refresh_family_of_that_connection(live: Deployment) -> None:
    """The whole connection ends, not only the access token that happened to be cached."""
    issue(live, "an-access-token-of-this-connection")

    live.post(
        {
            ui.ACTION_FIELD: ui.ACTION_DISCONNECT,
            ui.AUTH_PARAM: AUTH_ID,
            ui.CONFIRM_PARAM: live.token_of(AUTH_ID),
        }
    )
    refresh = run(live.store.load_refresh_token("refresh-an-access-token-of-this-connection"))

    assert refresh is not None
    assert refresh.state == store_module.STATE_REVOKED


def test_the_address_with_a_trailing_slash_is_served_and_never_redirected(
    live: Deployment,
) -> None:
    """ME-05: the manifest allows ``^/connections/?$`` and Starlette served one of the two.

    The other one got a 307 that Starlette builds out of the request URL, so the ``Location``
    came from the Host header and carried no application prefix: in a browser that lands on
    ``https://cloud.example.com/connections``, outside ``/exapps/mcp_connector/``, where
    Nextcloud answers 404. A bookmark or an autocompleted address then hid the switch and the
    disconnect exactly when somebody went looking for them. It also broke T-03-02, the rule
    that every address of this app comes from the configured public URL and never from a
    request, and the redirect carried no ``no-store``.
    """
    listed = live.client.get(
        f"{ui.CONNECTIONS_PATH}/", headers=appapi_headers(NC_USER), follow_redirects=False
    )
    paused = live.client.post(
        f"{ui.CONNECTIONS_PATH}/",
        data={ui.ACTION_FIELD: ui.ACTION_PAUSE, ui.CONFIRM_PARAM: live.switch_token_of()},
        headers=appapi_headers(NC_USER),
        follow_redirects=False,
    )

    assert listed.status_code == 200
    assert CLIENT_NAME in listed.text
    assert paused.status_code == 200
    assert strings.CONNECTIONS_PAUSED_TITLE in paused.text
    assert run(live.store.access_disabled(NC_USER)) is True
    for response in (listed, paused):
        assert "location" not in response.headers
        assert response.headers["cache-control"] == "no-store"


def test_a_body_far_larger_than_this_page_has_fields_for_is_refused_unread(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """LO-08: four short text fields, and no bound on what a caller could send.

    ``request.form()`` reads an urlencoded body into memory whole and spools multipart parts
    above a threshold into temporary files. The page needs an action, a handle and a value
    of sixty four characters, so a few kilobytes is generous and anything above it is not a
    browser filling in this form.
    """
    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.client.post(
            ui.CONNECTIONS_PATH,
            data={
                ui.ACTION_FIELD: ui.ACTION_PAUSE,
                ui.CONFIRM_PARAM: live.switch_token_of(),
                "padding": "p" * (routes.MAX_FORM_BYTES + 1),
            },
            headers=appapi_headers(NC_USER),
        )

    assert response.status_code == 400
    assert SECTION_HEADING in response.text, "the list, exactly as an unknown action gets it"
    assert run(live.store.access_disabled(NC_USER)) is False, "the body was never acted on"
    assert caplog.records


def test_a_chunked_body_far_larger_than_this_page_has_fields_for_is_refused_too(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """The same limit, for a request that announces no length at all (IN-01, second place).

    ``_oversized`` reads the announced ``Content-Length``, and a request with
    ``Transfer-Encoding: chunked`` announces none, so the check passed it through and
    ``request.form()`` read whatever arrived into memory. The action inside that body was
    then carried out, which is what this test would have measured before: a switch flipped
    by a request the page said it refuses unread. The limit counts what arrives now.
    """

    def in_chunks() -> Iterator[bytes]:
        yield (
            f"{ui.ACTION_FIELD}={ui.ACTION_PAUSE}"
            f"&{ui.CONFIRM_PARAM}={live.switch_token_of()}&padding="
        ).encode()
        for _ in range(64):
            yield b"p" * 1024

    with caplog.at_level("WARNING", logger="mcp_connector.oauth.connections"):
        response = live.client.post(
            ui.CONNECTIONS_PATH,
            content=in_chunks(),
            headers=appapi_headers(NC_USER) | {"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 400
    assert SECTION_HEADING in response.text, "the list, exactly as the announced case gets it"
    assert run(live.store.access_disabled(NC_USER)) is False, "the body was never acted on"
    assert caplog.records
    assert "pppp" not in "\n".join(record.getMessage() for record in caplog.records)


def test_a_chunked_body_inside_the_limit_is_acted_on_as_before(live: Deployment) -> None:
    """The counter check: the limit bounds the read, it does not refuse chunked bodies.

    Nothing says a browser has to announce a length, and a form of four short fields is far
    inside the limit however it arrives.
    """

    def in_chunks() -> Iterator[bytes]:
        yield f"{ui.ACTION_FIELD}={ui.ACTION_PAUSE}".encode()
        yield f"&{ui.CONFIRM_PARAM}={live.switch_token_of()}".encode()

    response = live.client.post(
        ui.CONNECTIONS_PATH,
        content=in_chunks(),
        headers=appapi_headers(NC_USER) | {"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert run(live.store.access_disabled(NC_USER)) is True


def test_a_form_body_that_cannot_be_parsed_is_a_page_and_never_an_unhandled_500(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """HI-02: the module promises that no refusal escapes as a 500, and this one did.

    Starlette catches its own ``MultiPartException`` inside ``Request.form()`` and turns it
    into a 400; the ``MultipartParseError`` of ``python_multipart`` is not covered by that
    and ran through untouched. The answer was a bare ``text/plain`` 500 without
    ``no-store``, without a reference a user could report, and with a full traceback in the
    log for every request: a cheap log flooder that any signed in account could fire.
    """
    with caplog.at_level("ERROR", logger="mcp_connector"):
        response = live.client.post(
            ui.CONNECTIONS_PATH,
            headers=appapi_headers(NC_USER)
            | {"Content-Type": "multipart/form-data; boundary=the-boundary"},
            content=b"this is not a multipart body",
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert "Traceback" not in response.text
    assert caplog.records, "one log line with the reference of the page, and no traceback"
    assert live.rows_of() == [AUTH_ID], "a body nobody could read changes nothing"


def test_a_store_that_cannot_be_read_answers_a_page_and_never_a_traceback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Fail closed (D-37): the reader can do nothing about it, the log carries the detail."""
    deployment = Deployment(tmp_path)
    seed(deployment)
    Path(deployment.store.path).write_bytes(b"this is not a SQLite file")

    with caplog.at_level("ERROR", logger="mcp_connector.oauth.connections"):
        response = deployment.get()

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert "Traceback" not in response.text
    assert caplog.records


def test_the_page_never_ends_a_connection_on_a_path_of_its_own() -> None:
    """T-04-35, the source guard of pitfall 3: one revocation path, and it is the provider's.

    A direct ``revoke_authorization`` in either module would end a connection without
    emptying the verifier cache, so a revoked token would keep working for up to five
    seconds. Counter checked by hand: a store call written into ``oauth/connections.py``
    turns this test red.
    """
    for path in (
        Path("src/mcp_connector/oauth/connections.py"),
        Path("src/mcp_connector/exapp/ui/connections.py"),
    ):
        code = "\n".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "revoke_authorization" not in code, f"{path.name} revokes on its own"
        assert "revoke_family" not in code, f"{path.name} revokes on its own"


def test_the_page_is_throttled_in_a_class_of_its_own() -> None:
    """HI-01: the emergency brake may not hang in the class of the consent surface.

    ``CLASS_AUTHORIZE`` counted the refusals of ``/authorize/consent``,
    ``/authorize/decide`` and this page in one counter with one ceiling for the whole class,
    so a flood on either of them closed the other two for everybody (T-04-37, and the
    reason ``throttle.py`` splits classes at all).
    """
    built = routes.connections_routes(
        SERVED_ENV,
        store_provider=_no_store,
        end_connection=_never_ends,
        throttle=throttle_module.Throttle(),
    )

    for route in built:
        guard = route.app
        assert isinstance(guard, throttle_module.Throttled)
        assert guard._path_class == throttle_module.CLASS_CONNECTIONS
        assert guard._path_class != throttle_module.CLASS_AUTHORIZE


def test_an_anonymous_flood_closes_neither_the_brake_nor_the_consent_surface(
    tmp_path: Path,
) -> None:
    """HI-01, reproduced: 201 anonymous requests used to lock the page for five minutes.

    Every answer is E8 with 403, so every one of them was counted, and the counter of a
    whole path class is checked for every caller whatever its source. The account owner then
    could neither disconnect anything nor pull the brake, which is the one function EXAPP-02
    exists for, and every running authorization decision of the instance went with it.
    """
    deployment = Deployment(tmp_path, throttle=throttle_module.Throttle())
    seed(deployment)
    before = deployment.get()

    for index in range(throttle_module.PATH_CEILING + 1):
        flood = deployment.client.get(
            ui.CONNECTIONS_PATH,
            headers=appapi_headers("") | {"X-Forwarded-For": f"203.0.113.{index % 250}"},
        )
        assert flood.status_code == 403, "the flood is refused, and refusals are what count"

    owner = deployment.get()
    consent_surface = deployment.client.get(
        f"{ui_consent.CONSENT_PATH}?{ui_consent.FLOW_PARAM}=a-flow-that-does-not-exist",
        headers=appapi_headers(NC_USER),
    )

    assert before.status_code == 200
    assert owner.status_code == 200, "the owner of the account still reaches their own brake"
    assert CLIENT_NAME in owner.text
    assert consent_surface.status_code != 429, "and no consent decision was locked out either"


def test_the_refusals_of_one_account_do_not_lock_out_another(tmp_path: Path) -> None:
    """The counter is keyed by the signed account and not by a forgeable header (HI-01).

    A stale tab produces refusals as normal operation, and ``FAILURE_LIMIT`` of them are
    enough to be sent away for five minutes. That may hit the account that produced them
    and nobody else.
    """
    deployment = Deployment(tmp_path, throttle=throttle_module.Throttle())
    seed(deployment)
    seed(deployment, auth_id=FOREIGN_AUTH_ID, nc_user=OTHER_USER)

    for _ in range(throttle_module.FAILURE_LIMIT + 1):
        deployment.post({ui.ACTION_FIELD: "not-an-action-of-this-page"})

    assert deployment.get().status_code == 429, "the account that flooded waits"
    assert deployment.get(OTHER_USER).status_code == 200, "the other account does not"


async def _no_store() -> OAuthStore:  # pragma: no cover - the route is never called here
    raise sqlite3.Error("no store in this check")


async def _never_ends(nc_user: str, auth_id: str) -> bool:  # pragma: no cover - never called
    del nc_user, auth_id
    return False
