"""Every user facing sentence of the phase, one constant per sentence (03-UI-SPEC.md).

The separation is not tidiness. A later locale has to be a data change and never a rewrite
of the templates, so no template function in this package carries a literal a user reads.
That is the same rule the ``_HINT`` constants of ``config.py``, ``ocs.py``, ``deps.py`` and
``ids.py`` already follow for the sentences a model reads.

v1 ships English only, consistent with ``docs/client-setup.md``. The German reference
wording lives in the table "German reference wording" of ``03-UI-SPEC.md`` and is
deliberately not mirrored here as a dictionary: an unused mapping would be dead code, the
dead code gate would report it, and a whitelist entry for a translation nobody serves yet
is worse than a table in the document that owns the copy anyway.

The placeholders are ``str.format`` names, and there are exactly eight of them across the
whole surface: ``client``, ``host``, ``user``, ``redirect_uri``, ``seconds`` and ``ref``
from phase 3, plus ``date`` and ``connections_url`` which phase 4 adds (04-UI-SPEC.md).
Every one of them is filled at render time and escaped by ``layout``, at the single point
where the template writes it.

Copy rules the wording below follows, from the same document: every error names what
happened and what to do next, no OAuth error code, no parameter name, no internal host, no
code or token fragment, no blame, no exclamation mark, no emoji, never "click here".

All names are listed in ``__all__``. That is what a text catalogue is, and it is also what
tells the dead code gate that a sentence which no page uses yet is published on purpose:
the screens that consume the consent and result copy are built in 03-04 to 03-06 against
exactly these names.
"""

__all__ = [
    "ACCESS_DISABLED_DESCRIPTION",
    "ACTION_CANCEL_CONNECTION",
    "ACTION_CANCEL_SIGN_IN",
    "ACTION_CHECK_NOW",
    "ACTION_OPEN_CONNECTIONS",
    "ACTION_START_OVER",
    "ADMIN_FIELD_ALLOWED_CLIENTS_DESCRIPTION",
    "ADMIN_FIELD_ALLOWED_CLIENTS_LABEL",
    "ADMIN_FIELD_ALLOWLIST_DESCRIPTION",
    "ADMIN_FIELD_ALLOWLIST_LABEL",
    "ADMIN_FIELD_AUDIT_LOG_DESCRIPTION",
    "ADMIN_FIELD_AUDIT_LOG_LABEL",
    "ADMIN_FIELD_CIMD_DESCRIPTION",
    "ADMIN_FIELD_CIMD_LABEL",
    "ADMIN_FIELD_DCR_DESCRIPTION",
    "ADMIN_FIELD_DCR_LABEL",
    "ADMIN_FIELD_PUBLIC_URL_DESCRIPTION",
    "ADMIN_FIELD_PUBLIC_URL_LABEL",
    "ADMIN_FIELD_TALK_SEND_DESCRIPTION",
    "ADMIN_FIELD_TALK_SEND_LABEL",
    "ADMIN_PUBLIC_URL_EXAMPLE",
    "ADMIN_SETTINGS_DESCRIPTION",
    "ADMIN_SETTINGS_PLACE",
    "ADMIN_SETTINGS_TITLE",
    "CLIENT_NAME_FALLBACK",
    "CONNECTIONS_DETAIL_CONNECTED",
    "CONNECTIONS_EMPTY_BODY",
    "CONNECTIONS_EMPTY_TITLE",
    "CONNECTIONS_FOOTNOTE",
    "CONNECTIONS_PAUSED_BODY",
    "CONNECTIONS_PAUSED_TITLE",
    "CONNECTIONS_ROW_CONNECTED",
    "CONNECTIONS_SECTION",
    "CONNECTIONS_TITLE",
    "CONNECT_BODY",
    "CONNECT_DETAIL_CREDENTIAL",
    "CONNECT_DETAIL_USER",
    "CONNECT_HANDOFF_BODY",
    "CONNECT_HANDOFF_TITLE",
    "CONNECT_RESULT_BODY",
    "CONNECT_RESULT_HOWTO",
    "CONNECT_RESULT_ONCE",
    "CONNECT_RESULT_ONCE_TITLE",
    "CONNECT_RESULT_REVOKE",
    "CONNECT_TITLE",
    "CONNECT_WAIT_BODY",
    "CONNECT_WAIT_TITLE",
    "CONSENT_APPROVE",
    "CONSENT_CONFIRM_ACTION",
    "CONSENT_CONFIRM_BODY",
    "CONSENT_DENY",
    "CONSENT_DETAIL_APP_NAME",
    "CONSENT_DETAIL_CLIENT_HOST",
    "CONSENT_DETAIL_CLIENT_ID",
    "CONSENT_DETAIL_REDIRECT",
    "CONSENT_FOOTER",
    "CONSENT_GRANT_NO_REMOVAL",
    "CONSENT_GRANT_READ",
    "CONSENT_GRANT_REVOKE",
    "CONSENT_GRANT_TITLE",
    "CONSENT_GRANT_WRITE",
    "CONSENT_IDENTITY",
    "CONSENT_LOOPBACK_BODY",
    "CONSENT_LOOPBACK_TITLE",
    "CONSENT_TITLE",
    "CONSENT_WARNING_BODY",
    "CONSENT_WARNING_TITLE",
    "DISCONNECT_ACTION",
    "DISCONNECT_AGAIN",
    "DISCONNECT_BODY",
    "DISCONNECT_DONE_BODY",
    "DISCONNECT_DONE_TITLE",
    "DISCONNECT_GONE_BODY",
    "DISCONNECT_GONE_TITLE",
    "DISCONNECT_KEEP",
    "DISCONNECT_TITLE",
    "EMPTY_BODY",
    "EMPTY_TITLE",
    "ERROR_ALLOWLIST_BODY",
    "ERROR_ALLOWLIST_TITLE",
    "ERROR_EXPIRED_BODY",
    "ERROR_EXPIRED_TITLE",
    "ERROR_GENERIC_BODY",
    "ERROR_GENERIC_TITLE",
    "ERROR_PAUSED_BODY",
    "ERROR_REDIRECT_BODY",
    "ERROR_REDIRECT_TITLE",
    "ERROR_REGISTRATION_OFF_BODY",
    "ERROR_REGISTRATION_OFF_TITLE",
    "ERROR_SIGN_IN_BODY",
    "ERROR_SIGN_IN_TITLE",
    "ERROR_THROTTLED_BODY",
    "ERROR_THROTTLED_TITLE",
    "ERROR_TIMEOUT_BODY",
    "ERROR_TIMEOUT_TITLE",
    "EXCHANGE_BODY",
    "EXCHANGE_BOUND_BODY",
    "EXCHANGE_BOUND_TITLE",
    "EXCHANGE_CONFIRM_BODY",
    "EXCHANGE_CONFIRM_TITLE",
    "EXCHANGE_DETAIL_CREATED",
    "EXCHANGE_DETAIL_PARTY",
    "EXCHANGE_GONE_BODY",
    "EXCHANGE_GONE_TITLE",
    "EXCHANGE_REACH",
    "EXCHANGE_REVOKED_BODY",
    "EXCHANGE_REVOKED_TITLE",
    "EXCHANGE_REVOKE_ACTION",
    "EXCHANGE_REVOKE_ANYTIME",
    "EXCHANGE_REVOKE_HINT",
    "EXCHANGE_TITLE",
    "EXCHANGE_WAIT_BODY",
    "FOOTER_PASSWORD_PROMPT",
    "IDENTITY_HANDOFF_ACTION",
    "IDENTITY_HANDOFF_BODY",
    "IDENTITY_HANDOFF_TITLE",
    "RESULT_CONNECTED_BODY",
    "RESULT_CONNECTED_TITLE",
    "RESULT_DENIED_BODY",
    "RESULT_DENIED_TITLE",
    "RESULT_RETURN_ACTION",
    "RESULT_RETURN_BODY",
    "SETTINGS_DESCRIPTION",
    "SETTINGS_PLACE",
    "SETTINGS_TITLE",
    "SETUP_PUBLIC_URL_BODY",
    "SETUP_PUBLIC_URL_HINT",
    "SETUP_PUBLIC_URL_TITLE",
    "SIGNIN_BODY",
    "SIGNIN_CTA",
    "SIGNIN_TITLE",
    "SWITCH_OFF_STATE",
    "SWITCH_ON_STATE",
    "SWITCH_TURN_OFF",
    "SWITCH_TURN_ON",
    "WAIT_BODY",
    "WAIT_STATUS",
    "WAIT_TITLE",
    "WORDMARK",
]

# --- Sender identity, on every page ------------------------------------------------------

#: The wordmark of the bar above the card, next to the configured host. Together they are
#: the answer to "who is asking", which the user must be able to read on every screen.
WORDMARK = "MCP Connector for Nextcloud"

#: Default footer. The one sentence that makes a phishing copy of this page useless.
FOOTER_PASSWORD_PROMPT = (
    "The password prompt is always Nextcloud itself. If any other page asks you for your "  # noqa: S105 - a sentence about passwords, not a password
    "Nextcloud password, close it."
)

#: What a client is called when its registration carries no usable name at all.
CLIENT_NAME_FALLBACK = "An unnamed app"

# --- S1, sign in handoff -----------------------------------------------------------------

SIGNIN_TITLE = "Sign in to continue"

SIGNIN_BODY = (
    "{client} wants to connect to your Nextcloud. Sign in at {host} first. This page never "
    "asks for your password."
)

SIGNIN_CTA = "Continue to Nextcloud sign in"

# --- S2, waiting for the sign in ---------------------------------------------------------

WAIT_TITLE = "Waiting for your sign in"

WAIT_STATUS = "Waiting for your sign in at {host}."

WAIT_BODY = (
    "Finish the sign in in the other window. This page checks every few seconds and "
    "continues on its own as soon as you are signed in."
)

# --- Secondary actions, shared across the screens ----------------------------------------

ACTION_CANCEL_CONNECTION = "Cancel connection"

ACTION_CANCEL_SIGN_IN = "Cancel sign in"

ACTION_CHECK_NOW = "Check now"

ACTION_START_OVER = "Start over"

# --- The browser onboarding of AUTH-02 (plan 03-04) ---------------------------------------
#
# The same three screens as S1, S2 and the out of band variant of S4, for the user who has no
# OAuth capable client: an invitation, then the handoff with the Nextcloud link, then the
# waiting state, then the one time result. The wording never calls the credential a password
# of the user, because it is not one: it is an app password this connection owns, and the
# user can end it on its own in Nextcloud.

CONNECT_TITLE = "Connect an assistant app"

CONNECT_BODY = (
    "This creates a credential for an assistant app that cannot sign in at {host} by itself. "
    "The sign in happens at {host}, on its own pages, including your second factor. This page "
    "never asks for your password."
)

CONNECT_HANDOFF_TITLE = "Sign in at {host}"

CONNECT_HANDOFF_BODY = (
    "The sign in opens in a new window. Approve the connection there, then come back to this "
    "page. It is waiting for the result and needs nothing else from you."
)

CONNECT_WAIT_TITLE = "Waiting for your sign in"

CONNECT_WAIT_BODY = (
    "Finish the sign in in the other window. This page checks every few seconds and shows the "
    "result as soon as it arrives. If the other window is gone, start over."
)

CONNECT_DETAIL_USER = "Signed in as"

CONNECT_DETAIL_CREDENTIAL = "Credential for your assistant app"

CONNECT_RESULT_BODY = (
    "The connection is ready. Copy the credential below into your assistant app, together with "
    "the user name above."
)

CONNECT_RESULT_ONCE_TITLE = "Shown once"

CONNECT_RESULT_ONCE = (
    "This is the only time the credential is shown. Nothing of it is stored on this server. If "
    "you lose it, start over and create a new one."
)

CONNECT_RESULT_HOWTO = (
    "In your assistant app, use the user name and the credential as Basic credentials for the "
    "connector endpoint, exactly as described in the client setup guide."
)

CONNECT_RESULT_REVOKE = (
    "You can end this connection at any time in Nextcloud under Settings, Security, Devices and "
    "sessions. It is listed there under the name of this connector."
)

# --- The exchange enrollment of CRED-02 (plan 23-06, standalone only) ----------------------
#
# The page on which a person allows their organization's service to act on their Nextcloud,
# sees that permission and withdraws it. The wording never names the mechanics: no
# credential kind, no protocol word, no value a machine reads. What the reader has to know
# is who acts, how far it reaches, and that the permission is theirs to take back, at once.

EXCHANGE_TITLE = "Access for your organization's service"

EXCHANGE_BODY = (
    "Your organization runs a service that can use your Nextcloud on your behalf. It only "
    "works after you allow it here once, with your own sign in at {host}. This page never "
    "asks for your password."
)

EXCHANGE_REACH = (
    "The service reaches exactly as far as your own account reaches, and nothing further."
)

EXCHANGE_REVOKE_ANYTIME = (
    "You can withdraw this permission on this page at any time, and a withdrawal takes "
    "effect immediately."
)

EXCHANGE_WAIT_BODY = (
    "Finish the sign in in the other window. This page checks every few seconds and "
    "continues on its own as soon as you are signed in. If the other window is gone, "
    "start over."
)

#: The step between the finished Nextcloud sign in and the permission: the same independent
#: sign-on the consent decision demands (CR-01), because the sign in alone does not prove
#: who is sitting in front of this page.
EXCHANGE_CONFIRM_TITLE = "Confirm it is you"

EXCHANGE_CONFIRM_BODY = (
    "Before the permission is created, confirm with your organization's single sign-on "
    "that this is you."
)

EXCHANGE_BOUND_TITLE = "Access is set up"

EXCHANGE_BOUND_BODY = (
    "Your organization's service may use your Nextcloud as {user}, exactly as far as your "
    "own account reaches."
)

EXCHANGE_DETAIL_CREATED = "Allowed on"

EXCHANGE_DETAIL_PARTY = "Acting service"

EXCHANGE_REVOKE_HINT = (
    "Withdrawing takes effect immediately: the very next request of the service is refused."
)

EXCHANGE_REVOKE_ACTION = "Withdraw this permission"

EXCHANGE_REVOKED_TITLE = "Permission withdrawn"

EXCHANGE_REVOKED_BODY = (
    "The service no longer has access to your Nextcloud. You can allow it again below at any time."
)

#: The answer to a resubmitted withdrawal, an unknown handle, a handle of another account
#: and a wrong or missing form value, which are one answer on purpose: a page that told
#: them apart would answer a stranger whether that permission exists (the S8 contract).
EXCHANGE_GONE_TITLE = "Already withdrawn"

EXCHANGE_GONE_BODY = "That permission is not there any more. Nothing changed."

# --- S3, consent -------------------------------------------------------------------------

CONSENT_TITLE = "Allow {client} to use your Nextcloud?"

CONSENT_IDENTITY = "You are signed in as {user} at {host}."

CONSENT_WARNING_TITLE = "Unverified client"

CONSENT_WARNING_BODY = (
    "This app registered itself automatically. Nextcloud has not verified it. Only approve "
    "it if you started this connection yourself."
)

#: The second warning of this screen, for a client whose return addresses are all on the
#: computer the reader is sitting at. The MCP specification asks for it in those words
#: ("SHOULD display additional warnings for localhost-only redirect URIs") and says in the
#: line above why: "Client ID Metadata Documents cannot prevent localhost URL impersonation
#: by themselves." So the body names what is known and what is not, and it stays away from
#: the word the neighbouring warning uses as a negation: nothing here is confirmed by
#: anybody, and a sentence that sounded like it was would be the one lie this screen cannot
#: afford (T-06-38).
CONSENT_LOOPBACK_TITLE = "Comes back to this computer"

CONSENT_LOOPBACK_BODY = (
    "This app is sent back to a port on the computer you are using. The address its client "
    "information is published at is known, but which program answers on that port is not. "
    "Only approve it if you just started this connection in the app you meant to connect."
)

CONSENT_DETAIL_APP_NAME = "App name"

CONSENT_DETAIL_REDIRECT = "Sends you back to"

CONSENT_DETAIL_CLIENT_ID = "Client ID"

#: The host of the client identifier, shown next to the identifier itself and never instead
#: of it. The specification's word for this one is MUST ("clearly display the redirect URI
#: hostname during authorization"), and the draft asks for the same in section 6.4. It is a
#: line of its own in the same list because the identifier of such a client is a URL, and a
#: reader who is deciding whether to trust an app should not have to take a URL apart to see
#: whose it is.
CONSENT_DETAIL_CLIENT_HOST = "Client ID host"

CONSENT_GRANT_TITLE = "What this allows"

CONSENT_GRANT_READ = (
    "Read your files, calendar, notes, contacts and Deck cards, exactly as far as your own "
    "account reaches"
)

CONSENT_GRANT_WRITE = (
    "Create and change notes, calendar entries, Deck cards and files that do not exist yet"
)

# The constant is named after the promise and not after the HTTP verb: the contract gate in
# tests/contract/test_no_destructive_calls.py rejects that verb in upper case anywhere in
# production code, and it guards exactly the promise this sentence makes to the user.
CONSENT_GRANT_NO_REMOVAL = "Nothing is deleted. The connector has no delete tools."

CONSENT_GRANT_REVOKE = "Access ends when you revoke it in Nextcloud settings."

CONSENT_APPROVE = "Approve access"

#: A standalone deployment asks the browser to confirm its account at the organization's
#: single sign-on before it offers the decision (CR-01 without AppAPI).
CONSENT_CONFIRM_BODY = (
    "Before you decide, confirm with your organization's single sign-on that this is you."
)

CONSENT_CONFIRM_ACTION = "Continue with single sign-on"

CONSENT_DENY = "Deny access"

CONSENT_FOOTER = (
    "Approving does not share your password. The connector receives its own credential and "
    "never sees the password you typed at {host}."
)

# --- S4, result pages --------------------------------------------------------------------

RESULT_CONNECTED_TITLE = "Connected"

RESULT_CONNECTED_BODY = "{client} may now use your Nextcloud as {user}. You can close this window."

RESULT_DENIED_TITLE = "Access denied"

RESULT_DENIED_BODY = "{client} did not get access. Nothing was shared. You can close this window."

#: The return page of a decision that has somewhere to go back to (CR-03). The decision is
#: a form submission, and Chromium and WebKit check ``form-action`` against the target of a
#: redirect that follows one, so an answer of "302 to the client" is refused by the browser
#: under the policy of this phase. The answer is this page instead: it continues on its own
#: and names the button that does the same thing, so the return never depends on a redirect
#: the browser may refuse or on a policy that names a foreign origin.
RESULT_RETURN_BODY = "Taking you back to {client}. If nothing happens, use the button below."

RESULT_RETURN_ACTION = "Continue to {client}"

#: The page that hands a browser to the single sign-on. A navigation and not a redirect, for
#: the reason :data:`RESULT_RETURN_BODY` gives: the start is a form submission.
IDENTITY_HANDOFF_TITLE = "Continue to single sign-on"

IDENTITY_HANDOFF_BODY = (
    "Taking you to your organization's sign-in. If nothing happens, use the button below."
)

IDENTITY_HANDOFF_ACTION = "Continue to sign-in"

# --- Empty state -------------------------------------------------------------------------

EMPTY_TITLE = "Nothing to approve"

EMPTY_BODY = (
    "This page only appears while an app is asking for access. Start the connection again "
    "in your assistant app."
)

# --- S5 to S8, the connections page of one account (EXAPP-02, 04-UI-SPEC.md) -------------
#
# The page a user opens to see which assistant apps can reach their Nextcloud, to end one
# of those connections, and to pause the whole access of their account. "Disconnect" and
# never "revoke": the word of the specification belongs in ``docs/``, where it talks to
# administrators; the person on this page connected an app and wants it gone.

CONNECTIONS_TITLE = "Your connections"

CONNECTIONS_SECTION = "Connected apps"

CONNECTIONS_DETAIL_CONNECTED = "Connected on"

CONNECTIONS_ROW_CONNECTED = "Connected on {date}"

CONNECTIONS_FOOTNOTE = (
    "Apps you connected with a credential from the onboarding page are not listed here. "
    "They appear in Nextcloud under Settings, Security, Devices and sessions."
)

CONNECTIONS_EMPTY_TITLE = "No connected apps"

CONNECTIONS_EMPTY_BODY = (
    "No assistant app is connected to your Nextcloud through this connector. Connect one "
    "from the app itself, or use the onboarding page for an app that cannot sign in by "
    "itself."
)

CONNECTIONS_PAUSED_TITLE = "Access is paused"

#: Without a pointer to the Nextcloud settings on purpose (04-UI-SPEC.md, amended
#: 2026-08-17): the switch that turns access back on is rendered directly above this
#: callout, so a sentence that sent the reader somewhere else would be wrong by a line.
CONNECTIONS_PAUSED_BODY = (
    "MCP access is switched off for your account, so connected apps are refused. Nothing "
    "was disconnected."
)

#: The bare verb, on purpose: every row already carries the app name as its title, and the
#: name reaches assistive technology through the ``aria-label`` of the button instead.
DISCONNECT_ACTION = "Disconnect"

DISCONNECT_KEEP = "Keep this connection"

DISCONNECT_TITLE = "Disconnect {client}?"

DISCONNECT_BODY = (
    "{client} loses access to your Nextcloud immediately. Nothing in your Nextcloud is "
    "deleted or changed."
)

DISCONNECT_AGAIN = "You can connect it again at any time from the app itself."

DISCONNECT_DONE_TITLE = "Disconnected"

DISCONNECT_DONE_BODY = (
    "{client} no longer has access. If the app is still open, it will report that it lost "
    "its connection."
)

#: The answer to a resubmitted form, a handle that is gone and a handle of another account,
#: which are one answer on purpose: a page that told them apart would answer a stranger who
#: guessed a handle whether that connection exists (T-04-31).
DISCONNECT_GONE_TITLE = "Already disconnected"

DISCONNECT_GONE_BODY = "That connection is not listed any more. Nothing changed."

# --- The switch, as it is rendered on that page ------------------------------------------
#
# One sentence of state plus one button, and the action is a named state (pause, resume)
# rather than a toggle: a resubmitted form then re-states a state instead of flipping it.

SWITCH_ON_STATE = "MCP access is on. Connected apps can use your Nextcloud."

SWITCH_OFF_STATE = "MCP access is paused. Connected apps are refused, nothing is disconnected."

SWITCH_TURN_OFF = "Pause access"

SWITCH_TURN_ON = "Turn access back on"

# --- E1 to E8, eight of the nine error pages ----------------------------------------------
#
# The ninth, E9, stands at the end of this file with the reason it stands there.
#
# The trigger of each page and its status code live in ``errors.py``. Here is only the copy,
# so that a wording fix never touches a status code and a status code fix never touches the
# wording. Every body ends with the next step, because a user who reads only the last
# sentence of an error page still has to know what to do.

ERROR_ALLOWLIST_TITLE = "This app is not allowed"

ERROR_ALLOWLIST_BODY = (
    "An administrator has not allowed {client} to connect to this Nextcloud. Ask your "
    "administrator to add it, then try again."
)

ERROR_REGISTRATION_OFF_TITLE = "Automatic registration is off"

ERROR_REGISTRATION_OFF_BODY = (
    "An administrator switched off automatic app registration on this Nextcloud. Ask your "
    "administrator to register {client} manually, then try again."
)

ERROR_EXPIRED_TITLE = "This link has expired"

ERROR_EXPIRED_BODY = (
    "Authorization links are valid for a few minutes and can be used once. Start the "
    "connection again in your assistant app."
)

ERROR_TIMEOUT_TITLE = "Sign in timed out"

ERROR_TIMEOUT_BODY = (
    "The sign in was not completed in time. Start the connection again in your assistant app."
)

#: E5, the page a request gets when the address a client asked to be returned to is not one
#: of the addresses it registered. The last sentence names a way in rather than a cause, and
#: it was added on 2026-08-20 on the owner's decision on BL-14, option "make the dropped
#: part visible plus documentation": a measured run showed a real client refused here for
#: good and reading only a refusal (06-08-MEASUREMENTS.md, Cursor 3.2.16, which keeps asking
#: to be returned to a private-use address that D-35 does not register).
#:
#: Two limits shape that sentence. It names the app password path in words and never as a
#: link, for the reason spelled out at E8 below: the one outbound link of this app is the
#: sign in address Nextcloud itself hands us. And it says nothing about which check fell,
#: because four call sites in ``oauth/consent.py`` answer with this one page (a missing
#: address, an unreadable one, one that does not match the registration, and one our own
#: rule refuses), so a sentence that were true for only one of them would be the
#: information service T-03-24 forbids.
ERROR_REDIRECT_TITLE = "This app cannot be sent back safely"

ERROR_REDIRECT_BODY = (
    "The address {client} asked us to return to does not match its registration. For your "
    "safety nothing was shared. Start the connection again in your assistant app, and tell "
    "your administrator if it keeps happening. Some assistant apps cannot use this sign in "
    "at all, and for those the way in is an app password from your Nextcloud security "
    "settings."
)

ERROR_THROTTLED_TITLE = "Too many attempts"

ERROR_THROTTLED_BODY = "Wait {seconds} seconds and try again."

#: E8, the connections page without a Nextcloud account behind the browser. The host is
#: named in words and never as a link: the one outbound link of this app is the sign in
#: address Nextcloud itself hands us, and inventing one here would be the phishing shape
#: the footer of every page warns about (04-UI-SPEC.md, E8).
ERROR_SIGN_IN_TITLE = "Sign in to see your connections"

ERROR_SIGN_IN_BODY = (
    "This page shows the apps connected to your own Nextcloud account. Sign in at {host} "
    "and open it again."
)

ERROR_GENERIC_TITLE = "Something went wrong"

ERROR_GENERIC_BODY = (
    "The connection could not be completed. Try again. If it keeps failing, an administrator "
    "can find the details in the app log under reference {ref}."
)

# --- R1, the refusal of a paused account ------------------------------------------------
#
# Not a page: the wire answer of the transport boundary when the owner of an account has
# switched MCP access off (04-UI-SPEC.md "Refusal Contract", D-51). What the user sees is
# whatever their assistant app prints from it, so the answer carries the whole sentence.
# The two constants live here with the page copy because they are the same kind of thing,
# one sentence a person reads, and because a later locale has to be a data change here too.

# --- The entry Nextcloud renders in the personal settings (D-44, link only) ---------------
#
# A Declarative Settings form with no field at all: AppAPI stores the value of a field
# itself and never calls the ExApp when a user changes it (04-RESEARCH.md), so a checkbox
# there would be a switch this app cannot observe. What the entry does instead is point at
# the page that carries the real switch, which is why the address is spelled out as text
# next to the ``doc_url`` link. Consumed by the registration of plan 04-04.

SETTINGS_TITLE = "MCP Connector"

SETTINGS_DESCRIPTION = (
    "Assistant apps such as Claude or ChatGPT can reach your files, calendar, notes, "
    "contacts and Deck cards through this connector, exactly as far as your own account "
    "reaches. Your connected apps and the switch that pauses them are at {connections_url}."
)

#: Where the entry of this app sits in Nextcloud, in one constant. The place is named once
#: and only once (04-UI-SPEC.md): if the settings section has to move, one edit moves every
#: sentence that points at it.
SETTINGS_PLACE = "Settings, Security, MCP Connector"

# --- The form Nextcloud renders in the administration settings (BL-06, EXAPP-04) ---------
#
# The counterpart of the personal entry above, and the opposite decision about ``fields``.
# A value of an *admin* form does reach this app: AppAPI stores it in the ExApp configuration
# with the field id as the key, and ``exapp/config_values.py`` reads it back over the same
# channel the data key already uses. That is what makes a one click installation from the app
# store work without a single environment variable (05-RESEARCH.md, pattern 1 and pitfall 2).
#
# Two rules the copy below follows for reasons that are not editorial. No field is marked
# sensitive, so no sentence here promises that a value is hidden. And no sentence promises an
# immediate effect: the values are read when the app starts and when it is enabled, so a
# change takes effect after the app has been disabled and enabled again.

ADMIN_SETTINGS_TITLE = "MCP Connector"

ADMIN_SETTINGS_DESCRIPTION = (
    "Settings an installation from the app store needs. A field left empty keeps whatever the "
    "deploy environment of the container sets, and a value set here wins over it. The first "
    "five fields are about connecting an assistant app; the two switches after them are not: "
    "one decides whether an assistant may send a Talk message through this app, the other "
    "whether this app keeps a record of tool calls. Changes take effect after you disable and "
    "enable this app again."
)

#: Where the administration form of this app sits, named once so a move is one edit. The
#: counterpart of ``SETTINGS_PLACE`` for the personal entry.
ADMIN_SETTINGS_PLACE = "Administration settings, Security, MCP Connector"

#: The example address, in the shape a HaRP deployment actually serves: the public address of
#: the Nextcloud plus the ExApp path. Used in the field description and as its placeholder,
#: because an administrator who has never seen this path cannot guess it.
ADMIN_PUBLIC_URL_EXAMPLE = "https://cloud.example.com/exapps/mcp_connector"

ADMIN_FIELD_PUBLIC_URL_LABEL = "Public address of this connector"

ADMIN_FIELD_PUBLIC_URL_DESCRIPTION = (
    "The address assistant apps reach this connector at, including the app path, for example "
    f"{ADMIN_PUBLIC_URL_EXAMPLE}. Leave it empty to use the address derived from this "
    "Nextcloud, or enter a value to override that, with https and no trailing slash. A "
    "change takes effect after you disable and enable this app again."
)

ADMIN_FIELD_DCR_LABEL = "Let assistant apps register themselves"

ADMIN_FIELD_DCR_DESCRIPTION = (
    "Hosted assistants such as Claude or ChatGPT register themselves when a user connects "
    "them, which is what makes a connection work without an administrator. On a public "
    "instance, either switch the allow list below on or switch this off, so that only apps "
    "you named can connect. Switching this off also closes the next switch, the one about a "
    "document an app publishes itself: a closed door cannot be walked around through the "
    "other way in."
)

ADMIN_FIELD_CIMD_LABEL = "Let assistant apps identify themselves by their own document"

#: The form half of ``NC_MCP_OAUTH_CIMD``, and the one field whose state is not its own: the
#: code derives the answer as "this switch AND the switch above" (``oauth/registry.py``), so
#: the description has to name that coupling in both directions. Without that sentence an
#: administrator reads two independent switches, turns this one on while self registration is
#: off, and measures a state the code never produces (the reason the manifest description of
#: the same variable carries the same sentence).
ADMIN_FIELD_CIMD_DESCRIPTION = (
    "Some assistants, Claude Code among them, do not register here at all: they name the "
    "address of a small document they publish themselves, and this connector reads it. This "
    "switch only applies while the switch above is on. With self registration off, both ways "
    "are closed, whatever this switch says. Switching this one off leaves self registration "
    "exactly as it is."
)

ADMIN_FIELD_ALLOWLIST_LABEL = "Allow only the apps listed below"

ADMIN_FIELD_ALLOWLIST_DESCRIPTION = (
    "With this on, an app may connect only if it is in the list below. An empty list "
    "therefore allows nothing, which is deliberate: a list nobody filled in is not a "
    "permission to connect."
)

ADMIN_FIELD_ALLOWED_CLIENTS_LABEL = "Allowed apps"

ADMIN_FIELD_ALLOWED_CLIENTS_DESCRIPTION = (
    "One entry per app, separated by commas. An entry is either the client ID of a "
    "registration or the address an app is sent back to after a connection, which is the "
    "value you can write down before an app has ever connected."
)

ADMIN_FIELD_TALK_SEND_LABEL = "Let assistant apps send Talk messages"

#: The form half of ``NC_MCP_TALK_SEND`` (TALK-04), and the one field of this form that is
#: not about connecting an assistant. Three things and nothing more: what off means, that
#: reading is untouched by it, and the activation cycle in the sentence this file already
#: spells three times. The wording says "through this connector", because the switch neither
#: can nor does stop anybody from writing in Talk itself.
ADMIN_FIELD_TALK_SEND_DESCRIPTION = (
    "With this off, no assistant can send a Talk message through this connector, whatever an "
    "account is allowed to do in Talk itself. Reading is not affected: conversations and their "
    "history stay readable. A change takes effect after you disable and enable this app again."
)

ADMIN_FIELD_AUDIT_LOG_LABEL = "Keep a record of tool calls"

#: The form half of ``NC_MCP_AUDIT_LOG`` (D-14), now the long version phase 18 left to phase
#: 19 on purpose (AUDIT-05, D-v1.5-02, D-v1.5-04). Six things, none of them optional:
#:
#: 1. What a row holds, including the three fields the short version kept quiet about, which
#:    is the review finding IN-06 of phase 18: the names of the parameters, the reason of a
#:    refusal as a fixed identifier, and how long the call took.
#: 2. What a row never holds: no parameter value, no part of a result, no network address,
#:    no user agent, no text of an error message.
#: 3. What the record does not prove. This is the pledge of D-v1.5-02, and it is bound to
#:    ``exapp/audit_verify.LIMIT_SENTENCE``, the same limit said to whoever runs the check:
#:    the words "changed or removed unnoticed" and "recompute" are in both sentences, and
#:    ``tests/unit/test_exapp_admin_settings.py`` holds the two against each other so the
#:    form and the console cannot end up saying different amounts about one limit.
#: 4. That a record tied to named accounts can come under the codetermination of a works
#:    council (D-v1.5-04). A hint, never advice: an app cannot judge that for an instance.
#: 5. How long a row is kept and what it outlives, with the numbers of ``audit/store.py``
#:    (``RETENTION_DAYS``, ``SIZE_LIMIT_BYTES``) rather than a promise of forever.
#: 6. The activation cycle in the sentence this file already spells for every other value.
#:
#: What the wording must not do: name a level. There is one extent of what is recorded and
#: no second one to pick, so no sentence here offers a choice the code cannot answer.
ADMIN_FIELD_AUDIT_LOG_DESCRIPTION = (
    "With this on, every tool call is written down: the account it ran for, the name of the "
    "tool, the time, the app that called, whether the call succeeded, how long it took, and, "
    "where a call was refused, a fixed identifier of the reason. A row also holds the names "
    "of the parameters, never their values. No parameter value and no part of a result is "
    "stored, and neither is a network address, a user agent or the text of an error message. "
    "A later check of the record shows that an entry was changed or removed unnoticed. It "
    "does not show who is able to write the file behind it, because whoever can write it can "
    "recompute the chain behind the change. A record that ties calls to named accounts can "
    "come under the codetermination of a works council in Germany and in Austria, so whoever "
    "switches this on settles that beforehand; this is a hint and not legal advice. Rows are "
    "kept for 180 days by default, the record stops growing at 100 MB where the oldest rows "
    "give way, and an account removed in Nextcloud takes its own rows with it. A row outlives "
    "occ mcp_connector:purge and the removal of this app, and only deleting the data volume "
    "of this app deletes the record with it. This is off unless you switch it on, and a "
    "change takes effect after you disable and enable this app again."
)

# --- The setup state a missing public address produces (consumed by plan 05-04) -----------
#
# Not an error: a store installation has no public address yet, and this is the one thing an
# administrator has to do before any client can connect. The copy therefore names the place
# and the step, and it never blames the reader.

SETUP_PUBLIC_URL_TITLE = "This connector needs its public address"

SETUP_PUBLIC_URL_BODY = (
    "An administrator has to enter the address assistant apps reach this connector at. It is "
    f"the first field in {ADMIN_SETTINGS_PLACE}. After saving it, disable and enable this app "
    "again, then open this page once more."
)

SETUP_PUBLIC_URL_HINT = (
    f"The address looks like {ADMIN_PUBLIC_URL_EXAMPLE}: the address of this Nextcloud as it "
    "is reachable from the internet, followed by the path of this app."
)

#: The ``error_description`` of R1. A constant with no placeholder on purpose (T-03-66): it
#: names the rule and the place and never a value out of the request, so no account name,
#: no client name, no token fragment and no internal host can travel in it.
ACCESS_DISABLED_DESCRIPTION = (
    "MCP access is switched off for this Nextcloud account. The owner of the account can "
    "switch it back on on the connector's connections page, linked in Nextcloud under "
    f"{SETTINGS_PLACE}."
)

# --- E9, the page of an account that paused its own access (BL-10) ------------------------
#
# The page half of the same rule R1 answers on the wire, and the answer of the three points
# at which plan 05-02 enforces the switch: the finished sign in of the OAuth flow, the
# finished sign in of the browser onboarding, and the decision on the consent screen. All
# three are reached by a browser in the middle of a sign in, so the answer is a page.
#
# The title is the one the connections page already carries for the same condition, because
# it is the same condition and a second wording for it would be a second promise to keep.
# The body is a second one, though: ``CONNECTIONS_PAUSED_BODY`` deliberately points nowhere,
# because it is rendered one line under the switch itself, and this page is not.
#
# These two constants stand here and not in the block of E1 to E8 above for one mechanical
# reason: the body names ``SETTINGS_PLACE``, which is defined below that block, and the place
# is named in exactly one constant (04-UI-SPEC.md).

ERROR_PAUSED_BODY = (
    f"{SWITCH_OFF_STATE} The switch that turns it back on is on the connections page below, "
    f"which Nextcloud also links under {SETTINGS_PLACE}."
)

#: The label of the one link of that page. It names the destination, like every other link
#: of this surface, and never "click here".
ACTION_OPEN_CONNECTIONS = "Open your connections"
