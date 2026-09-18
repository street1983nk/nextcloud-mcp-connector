"""The four screens of the connections page (04-UI-SPEC.md, S5 to S8).

The routes that drive them live in :mod:`mcp_connector.oauth.connections`; this module only
renders, and it renders through :func:`mcp_connector.exapp.ui.layout.page` like every other
page of this project, so the security headers, the style nonce and the escaping have
exactly one source. ``no-store`` is not decoration here: this page carries the client names
and connection dates of one named account, and the AppAPI PHP proxy caches for 3600 seconds
unless told otherwise (T-04-32).

The screens, in the order a user meets them:

1. :func:`connections_page` for ``GET /connections``: the list of connected apps, the
   switch that pauses the whole access of this account, and the warning callout while it is
   paused. The same function renders the empty state (S6) and the result of a disconnect
   (S8), because all three are the same page in a different state and a second function
   would be a second place to forget the switch in.
2. :func:`confirm_page` for ``action=confirm``: the interstitial that names the app, its
   client id and its connection date before anything is ended.

Three properties are worth naming here, because the rest of the file is their mechanics:

* **The app name is attacker input.** It comes from a dynamic client registration, so every
  one of them passes :func:`~mcp_connector.exapp.ui.layout.client_name` before ``layout``
  escapes it (T-04-34), on the row, in the heading of the confirmation and in the result
  callout.
* **The connection handle never appears as visible text.** It is the handle of a
  credential, so it travels in a hidden field and nowhere else; the client id is public by
  design and is shown in full, because it is the only thing that tells two rows called
  "Claude" apart (T-04-31).
* **The order of the blocks is fixed** (04-UI-SPEC.md, "Callout stacking"): the setup notice
  of an unconfigured installation, identity, the result of what the user just did, the
  switch, the standing pause warning, and only then the list. The result answers the action,
  the warning describes a condition, and the switch stands directly above the warning so the
  way back is one line above the sentence that says access is off. The setup notice comes
  before all of it because it is the reason nothing on the page can work yet (plan 05-04).

The path and the field names are declared here, next to the forms that write them into the
document, and :mod:`mcp_connector.oauth.connections` imports them for its route
declaration. One value for the form and the route it posts to means the two cannot drift
apart, and the dependency runs in one direction only.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from starlette.responses import Response

from ... import config
from . import layout, strings

__all__ = [
    "ACTION_CONFIRM",
    "ACTION_DISCONNECT",
    "ACTION_FIELD",
    "ACTION_KEEP",
    "ACTION_PAUSE",
    "ACTION_RESUME",
    "AUTH_PARAM",
    "CONFIRM_PARAM",
    "CONNECTIONS_PATH",
    "RESULT_DONE",
    "RESULT_GONE",
    "Connection",
    "confirm_page",
    "connections_page",
]

#: Where the page lives. Declared in ``appinfo/info.xml`` fully anchored, like every other
#: route of this app: a pattern one shade too wide publishes a neighbour (D-38, T-04-36).
CONNECTIONS_PATH = "/connections"

#: One route with a named action instead of four routes: every declared route is a line of
#: external attack surface, and the list, the confirmation, the disconnect and the switch
#: are one resource. The same shape ``/connect`` uses for its start and its cancel.
ACTION_FIELD = "action"
ACTION_CONFIRM = "confirm"
ACTION_DISCONNECT = "disconnect"
ACTION_KEEP = "keep"
ACTION_PAUSE = "pause"
ACTION_RESUME = "resume"

#: The connection this form is about, as a hidden field. Never a visible value, and never
#: the only thing that authorises the action: the route compares the account of the row
#: with the account HaRP resolved for the request (T-04-31).
AUTH_PARAM = "connection"

#: The hidden anti forgery value: an HMAC under the data key of this installation, derived
#: from the handle the form is about (T-04-30). A page of another origin cannot produce it,
#: and the value of one row does not fit another row or the switch.
CONFIRM_PARAM = "confirm"

#: Which callout the list carries above everything else, if any. Two named states rather
#: than a rendered fragment handed in from a route: the markup of this surface is built
#: here and nowhere else.
RESULT_DONE = "done"
RESULT_GONE = "gone"


@dataclass(frozen=True, slots=True)
class Connection:
    """One row of the list: the three facts it shows and the two values it hides.

    ``token`` is the anti forgery value of exactly this row, and ``auth_id`` is the handle
    the form posts back. Both are hidden fields; everything else is rendered as text.
    """

    auth_id: str
    client_name: str
    client_id: str
    created_at: int
    token: str


def connections_page(
    rows: Sequence[Connection],
    *,
    user: str,
    paused: bool,
    switch_token: str,
    result: str = "",
    result_client: str = "",
    status_code: int = 200,
    env: Mapping[str, str] | None = None,
) -> Response:
    """S5, S6 and S8: the connected apps of one account, in whichever state they are in.

    The empty state is a state of this page and not an error, so it answers 200 as well
    (04-UI-SPEC.md, S6). The result of a disconnect is this page too, and deliberately not
    a redirect: the answer of a form submission may not be a redirect a browser checks
    against ``form-action 'self'`` (CR-03). The price of that is a reload that submits the
    form again, which is exactly why "Already disconnected" is a calm sentence and not an
    error page.
    """
    blocks = [
        *_setup(env),
        layout.paragraph(
            strings.CONSENT_IDENTITY.format(user=layout.account_name(user), host=_host(env))
        ),
        *_result(result, result_client),
        *_switch(paused, switch_token, env),
    ]
    if paused:
        blocks.append(
            layout.callout(
                "warning", strings.CONNECTIONS_PAUSED_TITLE, strings.CONNECTIONS_PAUSED_BODY
            )
        )

    if rows:
        title = strings.CONNECTIONS_TITLE
        blocks.append(layout.section_heading(strings.CONNECTIONS_SECTION))
        blocks.append(layout.row_list([_row(connection, env) for connection in rows]))
    else:
        title = strings.CONNECTIONS_EMPTY_TITLE
        blocks.append(layout.paragraph(strings.CONNECTIONS_EMPTY_BODY))

    blocks.append(layout.paragraph(strings.CONNECTIONS_FOOTNOTE, muted=True))
    blocks.append(layout.action(strings.CONNECT_TITLE, _CONNECT_PATH, env=env))
    return layout.page(title, blocks, env=env, status_code=status_code)


def confirm_page(connection: Connection, *, env: Mapping[str, str] | None = None) -> Response:
    """S7: the one page between a press of "Disconnect" and the end of a connection.

    The interstitial *is* the friction of this action: no checkbox, no typed name, no
    countdown, because reconnecting is one action in the app itself and friction that
    outweighs the risk teaches people to click through it.

    Two properties are the reason it exists at all. The initial focus is the heading and
    never the acting button (``focus_heading``), so a stray Enter key is not the action;
    and "Keep this connection" is rendered before "Disconnect", so the safe action is the
    one the keyboard reaches first, exactly as deny comes before approve on the consent
    screen.
    """
    name = layout.client_name(connection.client_name)
    return layout.page(
        strings.DISCONNECT_TITLE.format(client=name),
        [
            layout.paragraph(strings.DISCONNECT_BODY.format(client=name)),
            layout.paragraph(strings.DISCONNECT_AGAIN),
            layout.detail_list(
                [
                    (strings.CONSENT_DETAIL_APP_NAME, name),
                    (strings.CONSENT_DETAIL_CLIENT_ID, connection.client_id),
                    (strings.CONNECTIONS_DETAIL_CONNECTED, _connected_on(connection.created_at)),
                ]
            ),
            layout.form(
                CONNECTIONS_PATH,
                [
                    layout.button_secondary(
                        strings.DISCONNECT_KEEP, name=ACTION_FIELD, value=ACTION_KEEP
                    ),
                    layout.button_primary(
                        strings.DISCONNECT_ACTION, name=ACTION_FIELD, value=ACTION_DISCONNECT
                    ),
                ],
                hidden={AUTH_PARAM: connection.auth_id, CONFIRM_PARAM: connection.token},
                env=env,
            ),
        ],
        env=env,
        focus_heading=True,
    )


def _row(
    connection: Connection, env: Mapping[str, str] | None
) -> tuple[str, list[tuple[str, str]], str]:
    """One connection as the three parts :func:`layout.row_list` renders.

    Each row is its own form. One form around the whole list with five submit buttons would
    make the submitted value depend on which button was pressed last, which is exactly the
    ambiguity a destructive action must not have.
    """
    name = layout.client_name(connection.client_name)
    action = layout.form(
        CONNECTIONS_PATH,
        [
            layout.button_secondary(
                strings.DISCONNECT_ACTION,
                name=ACTION_FIELD,
                value=ACTION_CONFIRM,
                aria_label=f"{strings.DISCONNECT_ACTION} {name}",
            )
        ],
        hidden={AUTH_PARAM: connection.auth_id, CONFIRM_PARAM: connection.token},
        env=env,
    )
    lines = [
        (layout.ROW_MONO, connection.client_id),
        (
            layout.ROW_MUTED,
            strings.CONNECTIONS_ROW_CONNECTED.format(date=_connected_on(connection.created_at)),
        ),
    ]
    return name, lines, action


def _setup(env: Mapping[str, str] | None) -> list[str]:
    """What an installation that has never been configured says, above everything else.

    A store installation in Nextcloud 34 passes no variable into the container: with a single
    Docker daemon ``exApps.enableApp`` enables the app without deploy options, and AppAPI drops
    every declared variable whose final value is empty (05-RESEARCH, pitfall 2). So
    :func:`mcp_connector.config.public_url` answers the documented loopback default, every
    discovery document names it, and the first symptom used to be an assistant app failing at
    discovery, which reads like a client problem and is not one.

    The comparison lives here and only here, so the list, the empty list and the paused state
    share one condition: the cause is none of those three states, which is why the notice is
    the first block of all of them rather than a fourth state of this page.

    The copy names the place of the setting and the reactivation step, never the value and
    never a host (T-05-21): nobody can act on ``127.0.0.1:8765``, and the address the
    administrator has to type is the only useful sentence here. The step exists because the
    values are resolved once at the start of the process (plan 05-04, D-20).
    """
    if config.public_url(env) != config.DEFAULT_PUBLIC_URL:
        return []
    return [
        layout.callout("warning", strings.SETUP_PUBLIC_URL_TITLE, strings.SETUP_PUBLIC_URL_BODY),
        layout.paragraph(strings.SETUP_PUBLIC_URL_HINT, muted=True),
    ]


def _switch(paused: bool, token: str, env: Mapping[str, str] | None) -> list[str]:
    """The state of the account in one sentence, and the one button that changes it.

    Turning access off is the secondary style: it is the emergency brake, present but not
    advertised, and nothing is destroyed by it. Turning it back on is the one moment this
    page carries the accent colour, because the state is degraded and the primary action is
    the way back (04-UI-SPEC.md, "The Nextcloud Settings Entry").

    The action is a named state and never a toggle, so a resubmitted or replayed form
    re-states a state instead of flipping it: the same idempotence that makes "Already
    disconnected" an answer rather than an error.
    """
    if paused:
        button = layout.button_primary(
            strings.SWITCH_TURN_ON, name=ACTION_FIELD, value=ACTION_RESUME
        )
        state = strings.SWITCH_OFF_STATE
    else:
        button = layout.button_secondary(
            strings.SWITCH_TURN_OFF, name=ACTION_FIELD, value=ACTION_PAUSE
        )
        state = strings.SWITCH_ON_STATE
    return [
        layout.paragraph(state),
        layout.form(CONNECTIONS_PATH, [button], hidden={CONFIRM_PARAM: token}, env=env),
    ]


def _result(result: str, client: str) -> list[str]:
    """The callout of S8, above everything else the card carries.

    A finished disconnect is a success callout with the check icon, and a disconnect of
    something that is not there any more is a warning callout with the word "Already
    disconnected". The second one is not an error: a disconnect that already happened,
    requested again, is a page that says so calmly, and it is also the answer to a handle
    that never existed and to a handle of another account (T-04-31).
    """
    if result == RESULT_DONE:
        return [
            layout.callout(
                "success",
                strings.DISCONNECT_DONE_TITLE,
                strings.DISCONNECT_DONE_BODY.format(client=layout.client_name(client)),
            )
        ]
    if result == RESULT_GONE:
        return [
            layout.callout("warning", strings.DISCONNECT_GONE_TITLE, strings.DISCONNECT_GONE_BODY)
        ]
    if result:
        raise ValueError(f"unknown result {result!r}")
    return []


def _connected_on(created_at: int) -> str:
    """The day a connection was made, as "12 August 2026" and computed in UTC.

    Day, full month name, year: not ``12/08/2026``, which two continents read differently,
    not a relative time, which needs a clock this page cannot promise, and no time of day,
    which is noise in a list whose unit is a connection. A connection made late in the
    evening can therefore show the next day, and that is the accepted cost of not asking
    the browser for a timezone (04-UI-SPEC.md, S5).
    """
    moment = datetime.fromtimestamp(int(created_at), tz=UTC)
    return f"{moment.day} {moment.strftime('%B')} {moment.year}"


def _host(env: Mapping[str, str] | None) -> str:
    """Where the user signs in, from configuration, never the Host header (T-03-02)."""
    return config.sign_in_host(env)


#: Where the footer link of this page leads: the browser onboarding, for an app that cannot
#: sign in by itself. Spelled here rather than imported from :mod:`.connect`, so the two
#: page modules stay independent of each other, and named once rather than twice.
#:
#: No icon constant of its own anywhere in this module: the three shapes of ``icons.py``
#: reach these pages through :func:`layout.callout`, and this phase adds no fourth one
#: (04-UI-SPEC.md, Design System).
_CONNECT_PATH = "/connect"
