"""The administration form of BL-06, TALK-04 and D-14: seven values a store installation needs.

Built like :mod:`mcp_connector.exapp.settings_form`, which is the one to one model for the
transport, the app context and the error model. Four things differ, and they are the whole
content of this module: a second form id, ``section_type: "admin"``, a filled ``fields`` and
the fact that the values of this form do reach the ExApp.

That last point is the reason this form exists at all. AppAPI's ``SetValueListener`` stores
the value of an *admin* field with
``ExAppConfigService::setAppConfigValue($app, $fieldId, $value)``, so the field id is the
configuration key, without a prefix, and :mod:`mcp_connector.exapp.config_values` reads it
back over the very channel the data key already travels. The field ids are therefore taken
from ``config_values.CONFIG_KEYS`` instead of being written a second time, and a test holds
that equality: a form whose ids drift from the read path is a form whose values nobody reads.

**Two traps, both verified in the source of the components we do not own.**

* ``sensitive: true`` at a field makes the ``SetValueListener`` encrypt the value with
  ``ICrypto`` before storing it, using the server secret. The ExApp then reads back a blob it
  cannot open, so a value it needs at runtime would be lost behind a flag that looks like
  hardening (T-05-05). None of the seven fields carries it, in any spelling, and for the
  audit switch of D-14 the consequence would be the worst of the seven: a switch that cannot
  be read back as off either (T-18-19).
* Declarative Settings have no button type. The complete list is ``text``, ``password``,
  ``email``, ``tel``, ``url``, ``number``, ``checkbox``, ``multi-checkbox``, ``radio``,
  ``select`` and ``multi-select`` (nextcloud/server stable34,
  ``lib/public/Settings/DeclarativeSettingsTypes.php``). This is why the destructive action of
  this phase is an occ command in plan 05-06 and not a knob in this form.

The security hint of BL-06 lives in the description of the ``oauth_dcr`` field itself, not
only in ``docs/oauth-setup.md``: an administrator reading a switch is the one person who can
act on it (security domain V14, T-05-06). The same rule is why both switch descriptions name
the coupling between them: ``registry.client_policy`` reads the metadata document way as
"this switch AND the registration switch", and a form that shows two independent checkboxes
for one derived answer is a form that produces a state the code never has.
"""

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from .. import config
from ..errors import ToolError
from ..nextcloud.clients.ocs import OCS_HEADERS
from ..nextcloud.credentials import appapi_auth_headers
from ..nextcloud.http import shared_client
from .config_values import CONFIG_KEYS
from .settings_form import SETTINGS_PATH
from .ui import strings
from .ui.connections import CONNECTIONS_PATH

__all__ = ["ADMIN_FORM_ID", "PUBLIC_DOCS_URL", "form_scheme", "register_admin_form"]

#: The second form id of this app. ``insertOrUpdate`` keys on (appid, formid), so this one
#: never collides with the personal signpost and re-enabling updates it in place.
ADMIN_FORM_ID = "mcp_connector_admin"

#: What makes this an administration form, and what makes AppAPI store its values in the
#: ExApp configuration rather than in the preferences of one user.
ADMIN_SECTION_TYPE = "admin"

#: Where the entry sits. ``security`` is where an administrator already manages the sign in
#: and the app passwords of the instance, which is the same subject as these seven values:
#: the sixth decides whether this app may write into a conversation on behalf of an account,
#: and the seventh whether it keeps a record of what assistants did (D-14).
ADMIN_SECTION_ID = "security"

ADMIN_FORM_PRIORITY = 10

#: Where the ``doc_url`` of this form points as long as this app does not know its own
#: public address. The loopback default is no address to send an administrator to: in her
#: browser it is her own machine, not this container, so the link of the form that fixes
#: exactly that state would be the one link that leads nowhere (IN-03). The address is the
#: one ``appinfo/info.xml`` already names in all three languages.
PUBLIC_DOCS_URL = "https://github.com/street1983nk/nextcloud-mcp-connector/blob/main/docs/faq.md"

logger = logging.getLogger("mcp_connector.exapp.admin_settings")


def form_scheme(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build the administration form against one environment.

    A function and not a module level constant, for the reason ``settings_form`` gives: the
    documentation address in it comes from the public URL of this deployment, which is
    configuration and not a compile time fact.

    The seven fields are built from :data:`CONFIG_KEYS`, in that order, so the form and the
    read path cannot drift apart. Every field carries a ``default``, which is what the shape
    documented for Declarative Settings looks like; the five switches show the state this app
    ships with, so an administrator sees what is in force before touching anything.
    """
    configured = config.public_url(env)
    # A fresh store installation has set nothing, so this is the default in code, and a link
    # built from it points at the administrator's own machine (IN-03). The public FAQ is what
    # helps in that state; once an address is known, the connections page of this deployment
    # is the better target, because it shows the setup state of this very installation.
    doc_url = (
        PUBLIC_DOCS_URL
        if configured == config.DEFAULT_PUBLIC_URL
        else f"{configured}{CONNECTIONS_PATH}"
    )
    (
        public_url_field,
        dcr_field,
        cimd_field,
        allowlist_field,
        allowed_field,
        talk_send_field,
        audit_log_field,
        files_update_field,
    ) = CONFIG_KEYS
    return {
        "id": ADMIN_FORM_ID,
        "priority": ADMIN_FORM_PRIORITY,
        "section_type": ADMIN_SECTION_TYPE,
        "section_id": ADMIN_SECTION_ID,
        "title": strings.ADMIN_SETTINGS_TITLE,
        "description": strings.ADMIN_SETTINGS_DESCRIPTION,
        "doc_url": doc_url,
        "fields": [
            {
                "id": public_url_field,
                "title": strings.ADMIN_FIELD_PUBLIC_URL_LABEL,
                "description": strings.ADMIN_FIELD_PUBLIC_URL_DESCRIPTION,
                "type": "url",
                "placeholder": strings.ADMIN_PUBLIC_URL_EXAMPLE,
                "default": "",
            },
            {
                "id": dcr_field,
                "title": strings.ADMIN_FIELD_DCR_LABEL,
                "description": strings.ADMIN_FIELD_DCR_DESCRIPTION,
                "type": "checkbox",
                # The state this app ships with (D-35): success criteria 1 and 2 are about
                # connecting a hosted assistant without an administrator in the loop.
                "default": True,
            },
            {
                "id": cimd_field,
                "title": strings.ADMIN_FIELD_CIMD_LABEL,
                "description": strings.ADMIN_FIELD_CIMD_DESCRIPTION,
                "type": "checkbox",
                # The state this app ships with, and the same one the deploy variable
                # defaults to (``registry.client_policy``). What this checkbox cannot show
                # is the coupling: the policy is this value AND the switch above, and a
                # checkbox has no third position for "on but closed by the other one", so
                # the description says it in words rather than in the widget.
                "default": True,
            },
            {
                "id": allowlist_field,
                "title": strings.ADMIN_FIELD_ALLOWLIST_LABEL,
                "description": strings.ADMIN_FIELD_ALLOWLIST_DESCRIPTION,
                "type": "checkbox",
                "default": False,
            },
            {
                "id": allowed_field,
                "title": strings.ADMIN_FIELD_ALLOWED_CLIENTS_LABEL,
                "description": strings.ADMIN_FIELD_ALLOWED_CLIENTS_DESCRIPTION,
                "type": "text",
                "default": "",
            },
            {
                "id": talk_send_field,
                "title": strings.ADMIN_FIELD_TALK_SEND_LABEL,
                "description": strings.ADMIN_FIELD_TALK_SEND_DESCRIPTION,
                "type": "checkbox",
                # The state this app ships with (TALK-04): this switch is the countermeasure
                # for the outgoing channel, not its precondition, so it is on and an
                # administrator who wants it closed closes it. Off by default would take a
                # promised capability away from every installation that never reads this
                # form, and ``config.talk_send_enabled`` answers True for the same reason.
                "default": True,
            },
            {
                "id": audit_log_field,
                "title": strings.ADMIN_FIELD_AUDIT_LOG_LABEL,
                "description": strings.ADMIN_FIELD_AUDIT_LOG_DESCRIPTION,
                "type": "checkbox",
                # The one field of this form that ships off, and the only sensible state for
                # it (D-14): what this switch starts is a record about named people doing
                # named things, and a record nobody asked for is exactly the thing an
                # administrator has to be able to decide about. So the box is unticked, which
                # is what ``config.audit_log_enabled`` answers for an unset value, and an
                # installation that never opens this form records nothing at all.
                "default": False,
            },
            {
                "id": files_update_field,
                "title": strings.ADMIN_FIELD_FILES_UPDATE_LABEL,
                "description": strings.ADMIN_FIELD_FILES_UPDATE_DESCRIPTION,
                "type": "checkbox",
                "default": False,
            },
        ],
    }


async def register_admin_form(*, env: Mapping[str, str] | None = None) -> None:
    """Put the administration form into Nextcloud's settings. Never raises, for any reason.

    One attempt, no retry, one log line on failure: the same error model as the personal
    signpost and the init progress push. The call runs in the app context, so the user id in
    the outgoing token is empty, because this is the ExApp registering something about
    itself and not a request on behalf of a person.
    """
    try:
        settings = config.exapp_settings(env)
    except ToolError:
        # A missing deploy variable is a startup problem and is reported there. Raising here
        # would travel into the enable handler, which must answer with an empty error field.
        logger.error("the admin form was not registered: the deploy environment is incomplete")
        return

    url = f"{settings.base_url}{SETTINGS_PATH}"
    headers = dict(OCS_HEADERS)
    headers.update(
        appapi_auth_headers(
            "",
            app_id=settings.app_id,
            app_version=settings.app_version,
            aa_version=settings.aa_version,
            app_secret=settings.app_secret,
        )
    )

    client = shared_client()
    try:
        response = await client.post(url, json={"formScheme": form_scheme(env)}, headers=headers)
    except httpx.HTTPError:
        # No value from the request is repeated here: the headers carry the app secret.
        logger.error("the admin form registration to %s did not reach Nextcloud", url)
        return

    if response.status_code // 100 != 2:
        logger.error("the admin form registration to %s answered %s", url, response.status_code)
