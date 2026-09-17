"""The screens of the OAuth authorization: hand over, wait, decide (03-UI-SPEC.md S1 to S4).

The routes that drive them live in :mod:`mcp_connector.oauth.consent`; this module only
renders, and it renders through :func:`mcp_connector.exapp.ui.layout.page` like every other
page of this phase, so the security headers, the style nonce and the escaping have exactly
one source.

Every value on these pages comes from a dynamic client registration and is therefore
attacker input: the name, the return address, the client id. They are shown anyway, and
that is the point of the screen. What makes it safe is that ``layout`` cleans and escapes
each of them at the single place it writes them, and that the page says plainly which of
them nobody verified (03-UI-SPEC.md, S3, T-03-42).

No JavaScript, deliberately and completely. The waiting screen refreshes itself with one
``meta http-equiv="refresh"`` and every load asks Nextcloud exactly once, which is also the
whole throttling of this route (T-03-34).

The four screens, in the order a user meets them:

1. :func:`empty_page` for a bare ``/authorize``: nothing is being asked, so nothing is
   granted. It is also where "Start over" of the timeout page leads.
2. :func:`handoff_page` right after the authorization request: who is asking, and the link
   into the Nextcloud sign in, in a window of its own. It carries no refresh, because a
   link that disappears three seconds after it appeared is worse than one a user can reach
   again (the lesson of plan 03-04).
3. :func:`waiting_page` while the sign in runs: the refreshing screen, one poll per load.
4. :func:`consent_page` once Nextcloud knows who the user is: the decision screen, with
   the two buttons and the hidden value that binds them to this one request.
5. :func:`connected_page` and :func:`denied_page` for the rare client that cannot be
   redirected back at all. The normal end of a decision is a 302 to the registered address
   and no page at all (03-UI-SPEC.md, S4).

The paths and parameter names of the route are declared here, next to the links and forms
that write them into the document, and :mod:`mcp_connector.oauth.consent` imports them for
its route declarations, so a link and its route cannot drift apart.
"""

from collections.abc import Mapping
from urllib.parse import urlencode

from starlette.responses import Response

from ... import config
from . import icons, layout, strings

__all__ = [
    "CONFIRM_PARAM",
    "CONSENT_PATH",
    "DECIDE_PATH",
    "DECISION_APPROVE",
    "DECISION_DENY",
    "DECISION_PARAM",
    "FLOW_PARAM",
    "LOGIN_PARAM",
    "REFRESH_SECONDS",
    "STEP_PARAM",
    "STEP_WAIT",
    "connected_page",
    "consent_page",
    "consent_url",
    "denied_page",
    "empty_page",
    "handoff_page",
    "meta_refresh",
    "wait_path",
    "waiting_page",
]

#: Where the consent surface lives. Declared in ``appinfo/info.xml`` fully anchored, like
#: every other route of this app (D-38, pitfall 14). ``/authorize`` itself is the endpoint
#: of the specification and is declared separately.
CONSENT_PATH = "/authorize/consent"

#: Where the decision of that surface is posted, and the reason it is a path of its own
#: (CR-01). The screen shows what is being asked and grants nothing, so a browser that is
#: not signed in yet may see it; the request that turns a sign in into a grant compares the
#: Nextcloud account HaRP resolved with the one the sign in produced, so a flow id alone no
#: longer decides anything. Both are PUBLIC in ``appinfo/info.xml``: HaRP resolves that
#: account on a PUBLIC route too, and a ``USER`` declaration would feed its blacklist with
#: every refusal this route exists to produce (see ``oauth/consent.py``).
DECIDE_PATH = "/authorize/decide"

#: The flow id travels as a query parameter. It is what connects this page to one running
#: authorization request, which is why every page here carries ``Referrer-Policy:
#: no-referrer``: the sign in link opens another origin (T-03-32).
FLOW_PARAM = "flow"

#: The address of the Nextcloud sign in, carried in the same query. Nextcloud hands it to
#: us once, during the authorization request, and this is how it reaches the page that
#: shows it. The route checks that it belongs to the configured Nextcloud before it is ever
#: rendered, because a link on a page that asks for trust is the phishing step this whole
#: surface exists against (T-03-42).
LOGIN_PARAM = "login"

#: Which of the two states of the same page is meant. Without it the page is the handoff,
#: with it the waiting screen, which is also the one state that polls. One route instead of
#: two, because every declared route is a line of external attack surface (D-38).
STEP_PARAM = "step"
STEP_WAIT = "wait"

#: The pace of the waiting screen (03-UI-SPEC.md, S2). One poll per load, so this number is
#: also the load a running sign in puts on Nextcloud: one request every three seconds, for
#: at most the twenty minutes a flow lives.
REFRESH_SECONDS = 3

#: Which of the two buttons was pressed. Both are submit buttons of one form, so the name
#: of the field is the same and only the value differs (03-UI-SPEC.md, S3).
DECISION_PARAM = "decision"
DECISION_APPROVE = "approve"
DECISION_DENY = "deny"

#: The hidden field that binds the form to one authorization request. The value is derived
#: from the flow id and the data key of this installation, so a page of another site cannot
#: produce it and a value of another flow does not fit this one (T-03-50).
CONFIRM_PARAM = "confirm"


def consent_url(public_base: str, flow_id: str, login_url: str) -> str:
    """The absolute address the authorization endpoint redirects a browser to.

    Absolute and built from the configured public URL, not from the path this application
    sees: HaRP strips the prefix, so a redirect to ``/authorize/consent`` would send the
    browser to the root of the Nextcloud domain, where this app is not.
    """
    query = urlencode({FLOW_PARAM: flow_id, LOGIN_PARAM: login_url})
    return f"{public_base}{CONSENT_PATH}?{query}"


def meta_refresh(seconds: int = REFRESH_SECONDS) -> str:
    """The whole automation of the waiting screen, as one tag without a target.

    Without a URL the browser reloads the address it is on, which already carries the flow
    id and the step. That is why this page needs no script, and why it cannot be talked
    into reloading somewhere else.
    """
    return f'<meta http-equiv="refresh" content="{int(seconds)}">'


def empty_page(*, env: Mapping[str, str] | None = None) -> Response:
    """Nothing is being asked. The honest landing point of a link and of a stale tab."""
    return layout.page(
        strings.EMPTY_TITLE,
        [layout.paragraph(strings.EMPTY_BODY)],
        env=env,
        status_code=400,
    )


def handoff_page(
    client_name: str,
    login_url: str,
    flow_id: str,
    *,
    env: Mapping[str, str] | None = None,
) -> Response:
    """S1: who is asking, and the one link that leaves this application."""
    name = layout.client_name(client_name)
    return layout.page(
        strings.SIGNIN_TITLE,
        [
            layout.paragraph(strings.SIGNIN_BODY.format(client=name, host=_host(env))),
            layout.external_action(strings.SIGNIN_CTA, login_url),
            _onwards(flow_id, env),
        ],
        env=env,
    )


def waiting_page(flow_id: str, *, env: Mapping[str, str] | None = None) -> Response:
    """S2: the refreshing screen. Every load of it is exactly one poll at Nextcloud."""
    return layout.page(
        strings.WAIT_TITLE,
        [
            layout.status_line(strings.WAIT_STATUS.format(host=_host(env))),
            layout.paragraph(strings.WAIT_BODY),
            _onwards(flow_id, env),
        ],
        env=env,
        head_extra=meta_refresh(),
    )


def consent_page(
    client_name: str,
    client_id: str,
    redirect_uri: str,
    user: str,
    flow_id: str,
    confirm: str,
    *,
    unverified: bool,
    client_host: str | None = None,
    loopback_only: bool = False,
    confirm_identity: tuple[str, Mapping[str, str]] | None = None,
    env: Mapping[str, str] | None = None,
) -> Response:
    """S3: everything a person needs to decide, and the two buttons that decide it.

    ``confirm_identity`` is the step a standalone deployment asks for first: the path and
    hidden fields of the form that starts the single sign-on. While it is set, the page shows
    that one button instead of the two decision buttons; the decision route refuses without
    the proof either way.

    The details are a definition list and the return address is never shortened: a redirect
    target cut off in the middle hides exactly the part an attacker would have changed
    (03-UI-SPEC.md, S3).

    Two of them are the display duties the MCP specification puts on a client that
    identifies itself with a metadata document, and both are values this function only
    renders: the caller decides what they are (``oauth/consent.py``, the mechanism of
    ``unverified``).

    * ``client_host`` is the host of the client identifier, which is a URL for such a
      client and a random identifier for one that registered. It becomes a fourth entry of
      the same list rather than a paragraph of its own, next to the identifier it comes out
      of. A client that registered has no host to name, and then the list is the same three
      entries it was before.
    * ``loopback_only`` says that every registered return address of this client is on the
      computer the reader is sitting at. It renders a second warning next to the one about
      an unregistered client, with :func:`layout.callout` and no new primitive, because the
      specification asks for a warning and not for a new kind of surface.

    Nothing of a client's document is fetched to build this page, and no image out of it is
    shown. A logo address from a foreign domain would be a request of the reader's browser
    to whoever wrote that document, and cross domain tracking is not something this screen
    hands out in exchange for a picture. The field carrying such an address is therefore not
    named anywhere in this module, and a test greps for it (T-06-37).

    Four properties of the decision itself are built here and are the reason this page has
    no JavaScript at all:

    * both buttons are submit buttons of one ``POST`` form, so no link and no reload can
      grant anything (a GET must never change state, T-03-50),
    * the deny button is rendered before the approve button, so the safe action is the one
      the keyboard reaches first,
    * the form carries the anti forgery value of exactly this flow as a hidden field,
    * it posts to :data:`DECIDE_PATH` and not to this page: that route grants nothing
      unless the Nextcloud account behind the browser is the one this sign in produced,
      which a browser that is not signed in cannot be (CR-01),
    * the initial focus is the heading and never the granting button, because a page that
      opens with that button focused turns a stray Enter key into a grant.
    """
    name = layout.client_name(client_name)
    blocks = [
        layout.paragraph(strings.CONSENT_IDENTITY.format(user=user, host=_host(env))),
    ]
    if unverified:
        blocks.append(
            layout.callout("warning", strings.CONSENT_WARNING_TITLE, strings.CONSENT_WARNING_BODY)
        )
    if loopback_only:
        blocks.append(
            layout.callout("warning", strings.CONSENT_LOOPBACK_TITLE, strings.CONSENT_LOOPBACK_BODY)
        )
    details = [
        (strings.CONSENT_DETAIL_APP_NAME, name),
        (strings.CONSENT_DETAIL_REDIRECT, redirect_uri),
        (strings.CONSENT_DETAIL_CLIENT_ID, client_id),
    ]
    if client_host:
        details.append((strings.CONSENT_DETAIL_CLIENT_HOST, client_host))
    blocks.extend(
        [
            layout.detail_list(details),
            layout.section_heading(strings.CONSENT_GRANT_TITLE),
            layout.unordered_list(
                [
                    strings.CONSENT_GRANT_READ,
                    strings.CONSENT_GRANT_WRITE,
                    strings.CONSENT_GRANT_NO_REMOVAL,
                    strings.CONSENT_GRANT_REVOKE,
                ]
            ),
        ]
    )
    if confirm_identity is not None:
        action_path, fields = confirm_identity
        blocks.extend(
            [
                layout.paragraph(strings.CONSENT_CONFIRM_BODY),
                layout.form(
                    action_path,
                    [
                        layout.button_primary(
                            strings.CONSENT_CONFIRM_ACTION, name="step", value="confirm"
                        )
                    ],
                    hidden=fields,
                    env=env,
                ),
            ]
        )
        return layout.page(
            strings.CONSENT_TITLE.format(client=name),
            blocks,
            env=env,
            footer=strings.CONSENT_FOOTER.format(host=_host(env)),
            focus_heading=True,
        )
    blocks.extend(
        [
            layout.form(
                DECIDE_PATH,
                [
                    layout.button_secondary(
                        strings.CONSENT_DENY, name=DECISION_PARAM, value=DECISION_DENY
                    ),
                    layout.button_primary(
                        strings.CONSENT_APPROVE, name=DECISION_PARAM, value=DECISION_APPROVE
                    ),
                ],
                hidden={FLOW_PARAM: flow_id, CONFIRM_PARAM: confirm},
                env=env,
            ),
        ]
    )
    return layout.page(
        strings.CONSENT_TITLE.format(client=name),
        blocks,
        env=env,
        footer=strings.CONSENT_FOOTER.format(host=_host(env)),
        focus_heading=True,
    )


def connected_page(
    client_name: str,
    user: str,
    *,
    target: str = "",
    env: Mapping[str, str] | None = None,
) -> Response:
    """S4, approved: the end of the flow, with or without somewhere to go back to.

    With a ``target`` this is the return page of CR-03: the decision is a form submission,
    and Chromium and WebKit check ``form-action`` against the target of a redirect that
    follows one, so the ``302`` this used to answer is refused by those browsers under the
    policy every page of this phase carries. A navigation is not a form submission, so the
    page navigates instead: it carries the address as a meta refresh and as a button the
    reader can see and press.

    Without one it is the page for a client that registered no usable return address, and
    it has to say two things: it worked, and there is nothing left to do here.
    """
    name = layout.client_name(client_name)
    blocks = [layout.paragraph(strings.RESULT_CONNECTED_BODY.format(client=name, user=user))]
    if target:
        blocks = [
            layout.paragraph(strings.RESULT_RETURN_BODY.format(client=name)),
            layout.return_action(strings.RESULT_RETURN_ACTION.format(client=name), target),
        ]
    return layout.page(
        strings.RESULT_CONNECTED_TITLE,
        blocks,
        env=env,
        heading_icon=icons.CHECK,
        heading_tone="success",
        refresh_to=target,
    )


def denied_page(
    client_name: str, *, target: str = "", env: Mapping[str, str] | None = None
) -> Response:
    """S4, denied: nothing was shared, and the sentence says exactly that.

    Answered with 200 and not with an error status: the user did what they meant to do,
    and a refusal that reads like a failure teaches people to try again until it works.
    The refusal has to reach the client that asked, so this page returns to it the same way
    the approved one does (CR-03), carrying ``error=access_denied`` in the address.
    """
    name = layout.client_name(client_name)
    blocks = [layout.paragraph(strings.RESULT_DENIED_BODY.format(client=name))]
    if target:
        blocks.append(
            layout.return_action(strings.RESULT_RETURN_ACTION.format(client=name), target)
        )
    return layout.page(
        strings.RESULT_DENIED_TITLE,
        blocks,
        env=env,
        refresh_to=target,
    )


def wait_path(flow_id: str) -> str:
    """The address of the waiting state of one flow, as this application sees it."""
    return f"{CONSENT_PATH}?{urlencode({FLOW_PARAM: flow_id, STEP_PARAM: STEP_WAIT})}"


def _onwards(flow_id: str, env: Mapping[str, str] | None) -> str:
    """The two ways on that every screen of a running sign in offers.

    "Check now" is a GET form and asks the same question the refresh asks, for a browser
    where the refresh is switched off. "Start over" is a link to the bare authorization
    endpoint, which answers the empty state: the honest end for a user whose sign in window
    is gone, because the connection has to be started again in the app that asked for it.
    """
    return layout.form(
        CONSENT_PATH,
        [layout.button_secondary(strings.ACTION_CHECK_NOW, name="check", value="now")],
        hidden={FLOW_PARAM: flow_id, STEP_PARAM: STEP_WAIT},
        method="get",
        env=env,
    ) + layout.action(strings.ACTION_START_OVER, _AUTHORIZATION_PATH, env=env)


def _host(env: Mapping[str, str] | None) -> str:
    """Where the user signs in, from configuration, never the Host header (T-03-02)."""
    return config.sign_in_host(env)


#: Where "Start over" leads, which is the same path ``exapp/ui/errors.py`` uses for the
#: timeout page. Spelled here as a constant rather than imported from the SDK, so this
#: module keeps rendering without an authorization server on the import path.
_AUTHORIZATION_PATH = "/authorize"
