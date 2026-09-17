"""The four screens of the browser onboarding (03-UI-SPEC.md, S1, S2 and the S4 variant).

The routes that drive them live in :mod:`mcp_connector.oauth.connect`; this module only
renders, and it renders through :func:`mcp_connector.exapp.ui.layout.page` like every other
page of this phase, so the security headers, the style nonce and the escaping have exactly
one source.

No JavaScript, deliberately and completely (03-UI-SPEC.md, Platform Constraints). The whole
automation of the waiting screen is one ``meta http-equiv="refresh"`` tag, and its manual
fallback is a GET form with one button. A page where a human makes a trust decision has to
be readable by the administrator who installs it, and a script is the part of a page that
nobody reads.

The four screens, in the order a user meets them:

1. :func:`invitation_page` for ``GET /connect``: what this does, and one button that starts
   it. The button is a POST, because starting a sign in creates state at Nextcloud, and a
   GET that does so is a page a crawler can trigger (T-03-35).
2. :func:`handoff_page` as the answer to that POST: the link into the Nextcloud sign in, in
   a window of its own, plus the two ways onwards. It carries no meta refresh on purpose, a
   refresh would take the link away from a user who is still reading the page.
3. :func:`waiting_page` for ``GET /connect/wait``: the refreshing screen, one poll per load.
4. :func:`result_page`: the credential, once, with what to do with it and how to end it.

The paths and field names of the route are declared here, next to the links and forms that
write them into the document, and :mod:`mcp_connector.oauth.connect` imports them for its
route declarations. One value for the link and the route it leads to means the two cannot
drift apart, and the dependency runs in one direction only.
"""

from collections.abc import Mapping

from starlette.responses import Response

from ... import config
from . import icons, layout, strings

__all__ = [
    "ACTION_CANCEL",
    "ACTION_FIELD",
    "ACTION_START",
    "CONNECT_PATH",
    "FLOW_PARAM",
    "REFRESH_SECONDS",
    "WAIT_PATH",
    "handoff_page",
    "invitation_page",
    "meta_refresh",
    "result_page",
    "waiting_page",
]

#: Where the onboarding lives. Two paths, both declared in ``appinfo/info.xml`` and both
#: fully anchored there, because a route pattern one shade too wide publishes a neighbour
#: (D-38, pitfall 14).
CONNECT_PATH = "/connect"
WAIT_PATH = "/connect/wait"

#: The flow id travels as a query parameter of the waiting page. It is the only thing that
#: authorises fetching a result, which is why every page of this route carries
#: ``Referrer-Policy: no-referrer``: the sign in link opens another origin, and a referrer
#: would hand that origin the running sign in (T-03-32).
FLOW_PARAM = "flow"

#: One POST route with a named action instead of two routes: every route in the manifest is
#: a line of external attack surface, and starting and cancelling are the same resource.
ACTION_FIELD = "action"
ACTION_START = "start"
ACTION_CANCEL = "cancel"

#: The pace of the waiting screen (03-UI-SPEC.md, S2). One poll per load, so this number is
#: also the load this flow puts on Nextcloud: one request every three seconds, for at most
#: the twenty minutes a flow lives (T-03-34).
REFRESH_SECONDS = 3


def meta_refresh(seconds: int = REFRESH_SECONDS) -> str:
    """The whole automation of the waiting screen, as one tag without a target.

    Without a URL the browser reloads the address it is on, which already carries the flow
    id. That is why this page needs no script, and why it cannot be talked into reloading
    somewhere else.
    """
    return f'<meta http-equiv="refresh" content="{int(seconds)}">'


def invitation_page(*, env: Mapping[str, str] | None = None) -> Response:
    """S1 before anything was started: what this is, and the button that begins it."""
    return layout.page(
        strings.CONNECT_TITLE,
        [
            layout.paragraph(strings.CONNECT_BODY.format(host=_host(env))),
            layout.form(
                CONNECT_PATH,
                [layout.button_primary(strings.SIGNIN_CTA, name=ACTION_FIELD, value=ACTION_START)],
                env=env,
            ),
        ],
        env=env,
    )


def handoff_page(login_url: str, flow_id: str, *, env: Mapping[str, str] | None = None) -> Response:
    """S1 with the sign in Nextcloud just opened, in a window of its own.

    This is the only page of the phase that links out of the application, and the only one
    that shows the sign in link at all: the waiting screen behind it refreshes itself, and a
    link that disappears three seconds after it appeared is worse than one a user reaches
    again through "Start over".
    """
    return layout.page(
        strings.CONNECT_HANDOFF_TITLE.format(host=_host(env)),
        [
            layout.paragraph(strings.CONNECT_HANDOFF_BODY),
            layout.external_action(strings.SIGNIN_CTA, login_url),
            _onwards(flow_id, env),
        ],
        env=env,
    )


def waiting_page(flow_id: str, *, env: Mapping[str, str] | None = None) -> Response:
    """S2: the refreshing screen. Every load of it is exactly one poll at Nextcloud."""
    return layout.page(
        strings.CONNECT_WAIT_TITLE,
        [
            layout.status_line(strings.WAIT_STATUS.format(host=_host(env))),
            layout.paragraph(strings.CONNECT_WAIT_BODY),
            _onwards(flow_id, env),
        ],
        env=env,
        head_extra=meta_refresh(),
    )


def result_page(
    login_name: str, credential: str, *, env: Mapping[str, str] | None = None
) -> Response:
    """The S4 variant of this route: the credential, shown once and stored nowhere.

    This is the one page of the whole surface that writes a secret into a document, and that
    is deliberate: the app password belongs to the user, not to this server. What makes it
    safe is worth naming. The answer carries ``no-store`` and ``no-referrer`` like every page
    here, nothing of it reaches a file or a log, and the user can see and end the connection
    in Nextcloud under "Devices and sessions", which is what the last paragraph says
    (T-03-33, D-34).
    """
    return layout.page(
        strings.RESULT_CONNECTED_TITLE,
        [
            layout.paragraph(strings.CONNECT_RESULT_BODY),
            layout.detail_list(
                [
                    (strings.CONNECT_DETAIL_USER, login_name),
                    (strings.CONNECT_DETAIL_CREDENTIAL, credential),
                ]
            ),
            layout.callout(
                "warning", strings.CONNECT_RESULT_ONCE_TITLE, strings.CONNECT_RESULT_ONCE
            ),
            layout.paragraph(strings.CONNECT_RESULT_HOWTO),
            layout.paragraph(strings.CONNECT_RESULT_REVOKE, muted=True),
        ],
        env=env,
        heading_icon=icons.CHECK,
        heading_tone="success",
    )


def _onwards(flow_id: str, env: Mapping[str, str] | None = None) -> str:
    """The two ways on that every screen after the start offers: check now, or start over.

    "Check now" is a GET form and asks the same question the refresh asks, for a browser
    where the refresh is switched off. "Start over" is a plain link back to the first page,
    the honest answer for a user whose sign in window is gone: the running flow ends on its
    own after twenty minutes.
    """
    return layout.form(
        WAIT_PATH,
        [layout.button_secondary(strings.ACTION_CHECK_NOW, name="check", value="now")],
        hidden={FLOW_PARAM: flow_id},
        method="get",
        env=env,
    ) + layout.action(strings.ACTION_START_OVER, CONNECT_PATH, env=env)


def _host(env: Mapping[str, str] | None) -> str:
    """Where the user signs in, from configuration, never the Host header (T-03-02)."""
    return config.sign_in_host(env)
