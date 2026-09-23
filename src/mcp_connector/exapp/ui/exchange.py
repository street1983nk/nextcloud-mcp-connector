"""The screens of the exchange enrollment (CRED-02, plan 23-06, standalone only).

The routes that drive them live in :mod:`mcp_connector.oauth.exchange_enroll`; this module
only renders, and it renders through :func:`mcp_connector.exapp.ui.layout.page` like every
other page of this project, so the security headers, the style nonce and the escaping have
exactly one source.

The screens, in the order a user meets them: :func:`invitation_page` explains what the
permission is and carries the one button that starts a sign in; :func:`handoff_page` shows
the Nextcloud sign in link in a window of its own; :func:`waiting_page` refreshes itself,
one poll per load; :func:`identity_page` is the step to the independent sign-on of CR-01;
and :func:`bound_page` shows the one permission of this account and the form that ends it.

Three properties are worth naming here, the rest of the file is their mechanics:

* **The acting party is foreign text.** It names a service of another realm, so it passes
  :func:`~mcp_connector.exapp.ui.layout.client_name` before ``layout`` escapes it, exactly
  like the name a client gives itself at registration.
* **The handle of the permission never appears as visible text.** It is the handle of a
  credential, so it travels in a hidden field next to the anti forgery value, the shape of
  the disconnect form of ``ui/connections.py``.
* **The flow id travels in the address and never in the readable text.** The waiting screen
  reloads its own address, and the manual way onwards is a GET form whose hidden value
  becomes that address on submit, the shape of ``ui/connect.py``.

The path and the field names are declared here, next to the forms that write them into the
document, and :mod:`mcp_connector.oauth.exchange_enroll` imports them for its route
declaration, so the two cannot drift apart and the dependency runs in one direction only.
:data:`FLOW_PARAM` is deliberately the one of the consent surface: the OIDC callback of
``oauth/oidc_routes`` sends a confirmed enrollment browser back to this page with exactly
that query name, and a second spelling would break that return silently.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from starlette.responses import Response

from ... import config
from . import layout, strings
from .consent import FLOW_PARAM

__all__ = [
    "ACTION_FIELD",
    "ACTION_REVOKE",
    "ACTION_START",
    "AUTH_PARAM",
    "ENROLL_PATH",
    "FLOW_PARAM",
    "REFRESH_SECONDS",
    "RESULT_GONE",
    "RESULT_REVOKED",
    "TOKEN_PARAM",
    "Binding",
    "bound_page",
    "handoff_page",
    "identity_page",
    "invitation_page",
    "waiting_page",
]

#: Where the enrollment lives. One address for the whole procedure, in the shape of
#: ``/connections``: the invitation, the waiting screen, the confirmation and the
#: withdrawal are one resource, and every route is a line of external attack surface. The
#: one truth about this path; ``oauth/exchange_enroll.py`` and through it the OIDC callback
#: import it from here.
ENROLL_PATH = "/exchange"

#: One POST route with a named action instead of two routes, the shape every browser
#: surface of this project has.
ACTION_FIELD = "action"
ACTION_START = "start"
ACTION_REVOKE = "revoke"

#: The permission this form is about, as a hidden field. Never a visible value, and never
#: the only thing that authorises the withdrawal: the anti forgery value rendered next to
#: it was only ever shown to the confirmed account (T-23-29).
AUTH_PARAM = "binding"

#: The hidden anti forgery value of the withdrawal: an HMAC under the data key of this
#: installation, derived from the handle and the disconnect purpose (T-04-30, ME-01).
TOKEN_PARAM = "confirm"  # noqa: S105 - the name of a form field, not a credential

#: Which callout the invitation carries above everything else, if any. Two named states
#: rather than a rendered fragment handed in from a route, the shape of ``ui/connections``.
RESULT_REVOKED = "revoked"
RESULT_GONE = "gone"

#: The pace of the waiting screen: one poll per load, one request every three seconds, the
#: number of every other waiting screen of this project.
REFRESH_SECONDS = 3


@dataclass(frozen=True, slots=True)
class Binding:
    """The one permission of an account: the two facts it shows and the two values it hides.

    ``token`` is the anti forgery value of exactly this permission and ``auth_id`` the
    handle the form posts back; both are hidden fields. ``acting_party`` comes from a
    foreign realm and passes :func:`layout.client_name` before it is rendered.
    """

    auth_id: str
    created_at: int
    acting_party: str
    token: str


def invitation_page(
    *,
    result: str = "",
    status_code: int = 200,
    env: Mapping[str, str] | None = None,
) -> Response:
    """The first screen, and the answer to every withdrawal: what this is, and the start.

    The result of a withdrawal is this page and deliberately not a redirect (CR-03): the
    answer of a form submission may not be a redirect a browser checks against
    ``form-action 'self'``. The price is a reload that submits the form again, which is why
    "Already withdrawn" is a calm sentence and not an error page.
    """
    blocks = [
        *_result(result),
        layout.paragraph(strings.EXCHANGE_BODY.format(host=_host(env))),
        layout.paragraph(strings.EXCHANGE_REACH),
        layout.paragraph(strings.EXCHANGE_REVOKE_ANYTIME, muted=True),
        layout.form(
            ENROLL_PATH,
            [layout.button_primary(strings.SIGNIN_CTA, name=ACTION_FIELD, value=ACTION_START)],
            env=env,
        ),
    ]
    return layout.page(strings.EXCHANGE_TITLE, blocks, env=env, status_code=status_code)


def handoff_page(login_url: str, flow_id: str, *, env: Mapping[str, str] | None = None) -> Response:
    """The sign in Nextcloud just opened, in a window of its own.

    The only page of this surface that links out of the application, and the only one that
    shows the sign in link at all: the waiting screen behind it refreshes itself, and a
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
    """The refreshing screen. Every load of it is exactly one poll at Nextcloud.

    The refresh tag carries no target, so the browser reloads the address it is on, which
    already carries the flow id; the id never stands in the readable text.
    """
    return layout.page(
        strings.CONNECT_WAIT_TITLE,
        [
            layout.status_line(strings.WAIT_STATUS.format(host=_host(env))),
            layout.paragraph(strings.EXCHANGE_WAIT_BODY),
            _onwards(flow_id, env),
        ],
        env=env,
        head_extra=_meta_refresh(),
    )


def identity_page(
    action_path: str, fields: Mapping[str, str], *, env: Mapping[str, str] | None = None
) -> Response:
    """The step to the independent sign-on, rendered from an ``IdentityStep`` (CR-01).

    The same form the consent screen offers instead of its decision buttons: the sign in
    alone does not prove who is reading this page, so the permission is only written after
    the organization's own sign-on named the same account.
    """
    return layout.page(
        strings.EXCHANGE_CONFIRM_TITLE,
        [
            layout.paragraph(strings.EXCHANGE_CONFIRM_BODY),
            layout.form(
                action_path,
                [
                    layout.button_primary(
                        strings.CONSENT_CONFIRM_ACTION, name="step", value="confirm"
                    )
                ],
                hidden=dict(fields),
                env=env,
            ),
        ],
        env=env,
    )


def bound_page(binding: Binding, *, user: str, env: Mapping[str, str] | None = None) -> Response:
    """The one permission of this account, with its date and the form that ends it.

    Withdrawing is the secondary style, the shape of the pause switch of the connections
    page: it is the way back, present but not advertised, and nothing is destroyed by it
    that one more sign in cannot recreate.
    """
    return layout.page(
        strings.EXCHANGE_BOUND_TITLE,
        [
            layout.paragraph(strings.EXCHANGE_BOUND_BODY.format(user=layout.account_name(user))),
            layout.detail_list(
                [
                    (strings.EXCHANGE_DETAIL_CREATED, _allowed_on(binding.created_at)),
                    (strings.EXCHANGE_DETAIL_PARTY, layout.client_name(binding.acting_party)),
                ]
            ),
            layout.paragraph(strings.EXCHANGE_REVOKE_HINT, muted=True),
            layout.form(
                ENROLL_PATH,
                [
                    layout.button_secondary(
                        strings.EXCHANGE_REVOKE_ACTION, name=ACTION_FIELD, value=ACTION_REVOKE
                    )
                ],
                hidden={AUTH_PARAM: binding.auth_id, TOKEN_PARAM: binding.token},
                env=env,
            ),
        ],
        env=env,
    )


def _result(result: str) -> list[str]:
    """The callout above everything else the invitation carries, if any.

    A finished withdrawal is a success callout; a withdrawal of something that is not
    there any more is a calm warning, and it is also the answer to a handle that never
    existed, one of another account and a wrong form value (T-23-28, the S8 contract).
    """
    if result == RESULT_REVOKED:
        return [
            layout.callout("success", strings.EXCHANGE_REVOKED_TITLE, strings.EXCHANGE_REVOKED_BODY)
        ]
    if result == RESULT_GONE:
        return [layout.callout("warning", strings.EXCHANGE_GONE_TITLE, strings.EXCHANGE_GONE_BODY)]
    if result:
        raise ValueError(f"unknown result {result!r}")
    return []


def _onwards(flow_id: str, env: Mapping[str, str] | None) -> str:
    """The two ways on that every screen after the start offers: check now, or start over.

    "Check now" is a GET form and asks the same question the refresh asks, for a browser
    where the refresh is switched off; its hidden value is how the flow id becomes the
    address. "Start over" is a plain link back to the first page.
    """
    return layout.form(
        ENROLL_PATH,
        [layout.button_secondary(strings.ACTION_CHECK_NOW, name="check", value="now")],
        hidden={FLOW_PARAM: flow_id},
        method="get",
        env=env,
    ) + layout.action(strings.ACTION_START_OVER, ENROLL_PATH, env=env)


def _meta_refresh(seconds: int = REFRESH_SECONDS) -> str:
    """The whole automation of the waiting screen, as one tag without a target.

    Without a URL the browser reloads the address it is on, which already carries the flow
    id. That is why this page needs no script, and why it cannot be talked into reloading
    somewhere else.
    """
    return f'<meta http-equiv="refresh" content="{int(seconds)}">'


def _allowed_on(created_at: int) -> str:
    """The day the permission was granted, as "12 August 2026" and computed in UTC.

    The rendering of the connections list, for the reason given there: day, full month
    name, year, no time of day and no browser timezone.
    """
    moment = datetime.fromtimestamp(int(created_at), tz=UTC)
    return f"{moment.day} {moment.strftime('%B')} {moment.year}"


def _host(env: Mapping[str, str] | None) -> str:
    """Where the user signs in, from configuration, never the Host header (T-03-02)."""
    return config.sign_in_host(env)
