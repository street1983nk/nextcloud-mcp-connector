"""The registration of the occ commands of this app with Nextcloud.

Four of them since plan 24-06: ``mcp_connector:purge`` ends every connection of this
instance, ``mcp_connector:audit:verify`` checks the chain of the audit log, the third one,
whose name stands at :data:`OCC_AUDIT_READ_COMMAND_NAME`, reads the rows of that log out and
hands them over (AUDIT-04), and the fourth holds a presented token against the configured
token exchange path without using it for anything (EXCH-06). They are registered one by one,
because
``OccCommandController::registerCommand`` takes exactly one command per ``POST`` (app_api
v34.0.3), and each of them gets its own ``try`` for the reason ``exapp/lifecycle.py`` gives
its second form registration: they are independent, so a failure of one may not cost the
other.

One rule of this module is sharper than every other one in it, and it is written out at the
third scheme entry: a ``mode`` Symfony rejects does not break the command that carries it,
it breaks the occ command line of the whole instance, because
``appinfo/register_command.php`` of app_api builds every registered ExApp command at the
start of every occ call and catches container exceptions only. So the modes come from the
positive list ``required``, ``optional``, ``none``, no command registers an argument, and a
test in ``tests/unit/test_exapp_lifecycle.py`` holds every scheme against that list.

Built like :mod:`mcp_connector.exapp.settings_form` and
:mod:`mcp_connector.exapp.admin_settings`, which are the one to one model for the transport,
the app context and the error model: one attempt, no retry, one log line on failure, never
an exception out of this module. The reason for that tolerance is pitfall 11 of phase 2: the
registration happens in the ``enabled=1`` branch, and a non empty ``error`` field there
makes AppAPI disable the app again at once.

Two things differ from the two forms, and they are the whole content of this module: the
path (``POST /ocs/v2.php/apps/app_api/api/v1/occ_command``, verified against app_api 34.0.3,
``appinfo/routes.php`` ``OccCommand#registerCommand`` and
``lib/Service/ExAppOccService.php``) and the body, which describes a Symfony command
Nextcloud then builds and offers in ``occ list``.

Nobody has to unregister anything: ``ExAppService::unregisterExApp`` calls
``unregisterExAppOccCommands($appId)`` itself, the same way it removes the settings forms.
And ``disableExApp`` removes nothing, which is why the disable branch of
``exapp/lifecycle.py`` stays empty.

Every ``execute_handler`` is derived from the path constant of its handler module rather
than written a second time. A registration whose handler name drifts away from the route is
a command that exists, is documented, and answers 404 on the one day somebody needs it.
"""

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from .. import config
from ..audit.store import READ_LIMIT_DEFAULT, READ_LIMIT_MAX
from ..errors import ToolError
from ..nextcloud.clients.ocs import OCS_HEADERS
from ..nextcloud.credentials import appapi_auth_headers
from ..nextcloud.http import shared_client
from .audit_read import (
    AUDIT_READ_PATH,
    INSTANCE_KEYWORD,
    LIMIT_OPTION,
    MAX_SINCE_DAYS,
    REFUSALS_KEYWORD,
    SINCE_OPTION,
    USER_OPTION,
)
from .audit_verify import AUDIT_VERIFY_PATH, JSON_OPTION
from .exchange_check import EXCHANGE_CHECK_PATH, TOKEN_OPTION
from .purge import FORCE_OPTION, PURGE_PATH

__all__ = [
    "OCC_AUDIT_COMMAND_NAME",
    "OCC_AUDIT_HANDLER",
    "OCC_AUDIT_JSON_DESCRIPTION",
    "OCC_AUDIT_READ_COMMAND_NAME",
    "OCC_AUDIT_READ_HANDLER",
    "OCC_AUDIT_READ_JSON_DESCRIPTION",
    "OCC_AUDIT_READ_LIMIT_DESCRIPTION",
    "OCC_AUDIT_READ_SINCE_DESCRIPTION",
    "OCC_AUDIT_READ_USER_DESCRIPTION",
    "OCC_COMMAND_NAME",
    "OCC_COMMAND_PATH",
    "OCC_EXCHANGE_CHECK_COMMAND_NAME",
    "OCC_EXCHANGE_CHECK_DESCRIPTION",
    "OCC_EXCHANGE_CHECK_HANDLER",
    "OCC_EXCHANGE_CHECK_JSON_DESCRIPTION",
    "OCC_EXCHANGE_CHECK_TOKEN_DESCRIPTION",
    "OCC_FORCE_DESCRIPTION",
    "OCC_HANDLER",
    "command_schemes",
    "register_occ_commands",
]

#: The OCS route AppAPI exposes for the occ commands of an ExApp.
OCC_COMMAND_PATH = "/ocs/v2.php/apps/app_api/api/v1/occ_command"

#: What an administrator types. The app id as the namespace, which is what every ExApp
#: command of an app shares and what makes it findable in ``occ list``.
OCC_COMMAND_NAME = "mcp_connector:purge"

#: The route on us AppAPI calls when the command runs, without the leading slash: one
#: derivation from the route itself, so the two cannot say different things.
OCC_HANDLER = PURGE_PATH.removeprefix("/")

OCC_DESCRIPTION = (
    "End every MCP connection of this instance: hand every Nextcloud app password this app "
    "created back to Nextcloud, empty its database and delete its encryption key. Run this "
    "before removing the app, because removing the app does not do it."
)

OCC_FORCE_DESCRIPTION = (
    "Required. This cannot be undone: every connected assistant has to be authorized again."
)

#: What an administrator types for the check of AUDIT-02. The namespace has two levels on
#: purpose: AUDIT-04 added a second command in plan 19-07 that reads entries out and hands
#: them over, and ``mcp_connector:audit:`` carries both of them, so that day cost no renaming
#: and no second invention of a name.
OCC_AUDIT_COMMAND_NAME = "mcp_connector:audit:verify"

#: The route on us AppAPI calls when the check runs, derived exactly like :data:`OCC_HANDLER`.
OCC_AUDIT_HANDLER = AUDIT_VERIFY_PATH.removeprefix("/")

OCC_AUDIT_DESCRIPTION = (
    "Check every entry of the audit log against the chain it belongs to and report either "
    "that no break was found or the first place a chain is broken."
)

OCC_AUDIT_JSON_DESCRIPTION = (
    "Answer with the same result as JSON, for a script that watches this instead of the "
    "exit code, which is always 0."
)

#: What an administrator types for the read of AUDIT-04, and the name the comment above
#: reserved for it. It stands here exactly once as a literal: AppAPI's ``insertOrUpdate``
#: keys a registration on the app id and the name, so a renamed command does not replace the
#: old one, it leaves it behind as an entry in ``occ list`` that answers 404 (pitfall 5).
OCC_AUDIT_READ_COMMAND_NAME = "mcp_connector:audit:read"

#: The route on us AppAPI calls when the read runs, derived exactly like :data:`OCC_HANDLER`
#: and like :data:`OCC_AUDIT_HANDLER`, so the registration and the route cannot drift apart.
OCC_AUDIT_READ_HANDLER = AUDIT_READ_PATH.removeprefix("/")

OCC_AUDIT_READ_DESCRIPTION = (
    "Read the audit log of this instance and hand it over: which account ran which tool, "
    "when, through which app, and whether the call was carried out or refused. No parameter "
    "value and no part of a result is written down, so none can be printed here either."
)

#: The three descriptions below belong to options that carry a value, which is new in this
#: module: the two commands above have flags only.
#: Two words of this option are not accounts, and both of them win against an account of the
#: same name, which is the trade the two constants in ``exapp/audit_read.py`` name. They are
#: spelled through those constants rather than as literals, so a renamed keyword moves this
#: help text with it instead of leaving a wrong one behind. ``refusals`` arrived with the
#: refusal chain of plan 24-03 and was handed to this plan for exactly this line: a reserved
#: word that stands in no ``occ list`` help text is a word only the source knows about.
OCC_AUDIT_READ_USER_DESCRIPTION = (
    "Read the entries of one Nextcloud account only, named by its user id, or of the "
    f"instance itself with the word {INSTANCE_KEYWORD}, or the refused token exchange "
    f"attempts of this instance with the word {REFUSALS_KEYWORD}. Those two words are the "
    "ones here that are not accounts. Without this option every account is read."
)

OCC_AUDIT_READ_SINCE_DESCRIPTION = (
    "How many whole days back to read, counted from the moment of the call. Days and never "
    f"a date, because a number can be checked before it is used. At most {MAX_SINCE_DAYS}, "
    "which is also the window a value this app cannot read as a number falls back to."
)

OCC_AUDIT_READ_LIMIT_DESCRIPTION = (
    f"How many entries at most, newest first. Without it {READ_LIMIT_DEFAULT} are read, and "
    f"{READ_LIMIT_MAX} is the ceiling whatever number is given. Every answer names the "
    "ceiling it applied, so a part of the log cannot be mistaken for the whole of it."
)

#: Not :data:`OCC_AUDIT_JSON_DESCRIPTION` a second time, and the difference is the reason:
#: for the check that text says "the same result", while here the machine readable shape is
#: also the hand over AUDIT-04 asks for, and it carries the entries in the order of the chain
#: instead of the order the console shows. One sentence about a shape that differs would be
#: wrong in one of the two commands, so each of them keeps its own.
OCC_AUDIT_READ_JSON_DESCRIPTION = (
    "Hand the same entries over as one JSON document, in the order of the chain, for a "
    "script that keeps them or checks them. Its first key says whether the read happened, "
    "because the exit code of this command is always 0."
)

#: What an administrator types for the dry run of EXCH-06. Two levels in the namespace like
#: the two audit commands, and for the same reason: ``mcp_connector:exchange:`` is the room a
#: second command about this path would move into without renaming this one. The literal
#: stands here exactly once, because AppAPI's ``insertOrUpdate`` keys a registration on the
#: app id and the name, so a renamed command does not replace the old one, it leaves it behind
#: as an entry in ``occ list`` that answers 404 (pitfall 5).
OCC_EXCHANGE_CHECK_COMMAND_NAME = "mcp_connector:exchange:check"

#: The route on us AppAPI calls when the dry run runs, derived exactly like :data:`OCC_HANDLER`
#: and its two siblings, so the registration and the route cannot drift apart.
OCC_EXCHANGE_CHECK_HANDLER = EXCHANGE_CHECK_PATH.removeprefix("/")

#: What the command is for, and in its second half what it deliberately is not. The three
#: absences are success criterion 3 of this phase and are named here rather than only in the
#: handler, because the person deciding whether to run this against a token somebody handed
#: them reads this text and not the source.
OCC_EXCHANGE_CHECK_DESCRIPTION = (
    "Hold a presented token against the token exchange path configured on this instance and "
    "report every rule with its outcome. The check is a dry run: it makes no Nextcloud call, "
    "it creates no session and no authorization, and it writes no row into the audit log. It "
    "costs one outgoing key set request to the configured provider."
)

#: The description that names a price instead of hiding it, after the model of
#: :data:`OCC_FORCE_DESCRIPTION`. There is no technical way around the cost (pitfall 6 of
#: 24-RESEARCH.md): a ``--token-file`` would lie on the Nextcloud host while the handler reads
#: in the ExApp container, and AppAPI hands no stdin through to an ExApp command. So the value
#: travels as an option and the consequence is said out loud, in the one text an administrator
#: sees before they type the command.
OCC_EXCHANGE_CHECK_TOKEN_DESCRIPTION = (
    "The token to check. Its value stands in the process list of the Nextcloud host while "  # noqa: S105 - a help text, not a secret
    "the command runs, and in the shell history afterwards, so use a short lived test token "
    "here and never a productive one. The answer never repeats the value."
)

#: Not :data:`OCC_AUDIT_JSON_DESCRIPTION` or its read counterpart a second time, and the
#: difference is the reason: what a script watches here is the ``passed`` key, and naming that
#: key is the whole point of the sentence. The exit code cannot carry the verdict, because
#: AppAPI drops the body of any answer that is not a 200 and this answer is the body.
OCC_EXCHANGE_CHECK_JSON_DESCRIPTION = (
    "Answer with the same result as JSON, whose key passed carries the verdict. A script "
    "watches that key and not the exit code, which is always 0."
)

logger = logging.getLogger("mcp_connector.exapp.occ")


def command_schemes() -> list[dict[str, Any]]:
    """The commands this app registers, one entry per ``POST``.

    A list and not one object, because ``OccCommandController::registerCommand`` takes
    exactly one command per request (signature verified against app_api v34.0.3), so two
    commands are two registrations and never one body with two names in it.

    A function rather than a module level constant so the shapes have one place a test reads
    and the registration cannot be asserted against a copy of itself. Nothing in them comes
    from configuration: unlike the two settings forms these bodies carry no URL, because a
    command is invoked on the command line and not followed in a browser.
    """
    return [
        {
            "name": OCC_COMMAND_NAME,
            "description": OCC_DESCRIPTION,
            # Visible in ``occ list``: an administrator who has to find this command on the
            # day of an uninstall should not have to know it exists (05-RESEARCH.md,
            # pattern 3).
            "hidden": 0,
            "arguments": [],
            # Mode ``none`` is a flag without a value, so ``--force`` is presence and nothing
            # else. The handler checks it again, because what AppAPI hands over is input.
            "options": [
                {"name": FORCE_OPTION, "mode": "none", "description": OCC_FORCE_DESCRIPTION}
            ],
            "usages": [f"{OCC_COMMAND_NAME} --{FORCE_OPTION}"],
            "execute_handler": OCC_HANDLER,
        },
        {
            "name": OCC_AUDIT_COMMAND_NAME,
            "description": OCC_AUDIT_DESCRIPTION,
            "hidden": 0,
            "arguments": [],
            # The same mode as the option above, and for once the handler reads it for a
            # shape and not for a permission: with it the answer arrives as JSON.
            "options": [
                {"name": JSON_OPTION, "mode": "none", "description": OCC_AUDIT_JSON_DESCRIPTION}
            ],
            # Both ways round, because the plain one is the one an administrator types and
            # the other is the one a monitoring script needs to find.
            "usages": [OCC_AUDIT_COMMAND_NAME, f"{OCC_AUDIT_COMMAND_NAME} --{JSON_OPTION}"],
            "execute_handler": OCC_AUDIT_HANDLER,
        },
        # The read of AUDIT-04, and the first entry of this module whose options carry
        # values. Three modes exist here and no fourth: ``required``, ``optional`` and
        # ``none``. The reason is not tidiness. ``appinfo/register_command.php`` of app_api
        # builds EVERY registered ExApp command at the start of EVERY occ call and catches
        # ``NotFoundExceptionInterface`` and ``ContainerExceptionInterface`` only, so an
        # exception out of Symfony's ``configure()`` does not cost this command, it costs the
        # occ command line of the whole instance. ``array`` is the trap that does it: AppAPI
        # turns it into ``InputOption::VALUE_IS_ARRAY`` alone, and Symfony refuses an array
        # option without a value mode with an ``InvalidArgumentException``. ``negatable``
        # next to a value is refused the same way. Neither is worth a filter.
        #
        # ``arguments`` stays empty for the second half of the same measurement: AppAPI reads
        # ``$argument['default']`` unconditionally once the mode is ``optional`` or ``array``,
        # while it reads ``$option['default'] ?? null``. An argument without that key would
        # therefore write a PHP warning on every occ call of the instance (app_api v34.0.3,
        # ``lib/Service/ExAppOccService.php:217-256``). So every filter of this command is an
        # option, every value option carries a ``default``, and a test holds all three schemes
        # of this module against the positive list.
        {
            "name": OCC_AUDIT_READ_COMMAND_NAME,
            "description": OCC_AUDIT_READ_DESCRIPTION,
            "hidden": 0,
            "arguments": [],
            "options": [
                {
                    "name": USER_OPTION,
                    "mode": "optional",
                    "description": OCC_AUDIT_READ_USER_DESCRIPTION,
                    "default": None,
                },
                {
                    "name": SINCE_OPTION,
                    "mode": "optional",
                    "description": OCC_AUDIT_READ_SINCE_DESCRIPTION,
                    "default": None,
                },
                {
                    "name": LIMIT_OPTION,
                    "mode": "optional",
                    "description": OCC_AUDIT_READ_LIMIT_DESCRIPTION,
                    "default": None,
                },
                # The same flag as the check above and the same spelling, taken from the one
                # import this module has for it. The two handler modules spell the name twice
                # for the import cycle their own comments describe, and a test holds the two
                # spellings equal, so this registration cannot offer a flag the read handler
                # does not read.
                {
                    "name": JSON_OPTION,
                    "mode": "none",
                    "description": OCC_AUDIT_READ_JSON_DESCRIPTION,
                },
            ],
            # The bare command first, because that is what an administrator types, then one
            # line per half of what the options are for: a narrowed read on a console, and
            # the hand over a script keeps.
            "usages": [
                OCC_AUDIT_READ_COMMAND_NAME,
                f"{OCC_AUDIT_READ_COMMAND_NAME} --{USER_OPTION}=alice --{LIMIT_OPTION}=50",
                f"{OCC_AUDIT_READ_COMMAND_NAME} --{SINCE_OPTION}=7 --{JSON_OPTION}",
            ],
            "execute_handler": OCC_AUDIT_READ_HANDLER,
        },
        # The dry run of EXCH-06. The comment block above holds for this entry as well and is
        # deliberately not repeated: the modes come from the same positive list, the arguments
        # stay empty for the same measurement, and the one value option below carries its
        # ``default`` for the same reason AppAPI reads ``$option['default'] ?? null``.
        #
        # What is new here is what the value is. This option carries a bearer token of a
        # foreign realm, so it is the first one of this module whose description has to name a
        # cost rather than only a meaning, in the shape ``OCC_FORCE_DESCRIPTION`` set for the
        # purge (pitfall 6).
        {
            "name": OCC_EXCHANGE_CHECK_COMMAND_NAME,
            "description": OCC_EXCHANGE_CHECK_DESCRIPTION,
            "hidden": 0,
            "arguments": [],
            "options": [
                {
                    "name": TOKEN_OPTION,
                    "mode": "optional",
                    "description": OCC_EXCHANGE_CHECK_TOKEN_DESCRIPTION,
                    "default": None,
                },
                # ``optional`` and not ``required``, although a check without a token can
                # check nothing: a required option is a Symfony rule, and the handler already
                # answers a missing token with the first named step of the rule. A named
                # outcome is what an administrator can act on; a usage error from Symfony is
                # not, and it would arrive without any of the sentences this answer carries.
                {
                    "name": JSON_OPTION,
                    "mode": "none",
                    "description": OCC_EXCHANGE_CHECK_JSON_DESCRIPTION,
                },
            ],
            # The plain form first, because that is what an administrator types, then the one
            # a script needs to find. The token value is shown as a placeholder: a usage line
            # is help text, and a help text that carried something token shaped would invite
            # somebody to paste it.
            "usages": [
                f"{OCC_EXCHANGE_CHECK_COMMAND_NAME} --{TOKEN_OPTION}=<token>",
                f"{OCC_EXCHANGE_CHECK_COMMAND_NAME} --{TOKEN_OPTION}=<token> --{JSON_OPTION}",
            ],
            "execute_handler": OCC_EXCHANGE_CHECK_HANDLER,
        },
    ]


async def register_occ_commands(*, env: Mapping[str, str] | None = None) -> None:
    """Register every command of this app with Nextcloud. Never raises, for any reason.

    The call runs in the app context, so the user id in the outgoing token is empty: this is
    the ExApp registering something about itself and not a request on behalf of a person.

    One ``try`` per command, and that is the same reason ``exapp/lifecycle.py`` gives for
    putting the admin form registration in a block of its own: the commands are independent
    of each other, so a Nextcloud that refuses one of them must not cost the other. Every
    failure names the command it happened to, because "the registration failed" over two
    commands is a line that sends an administrator to the wrong one.
    """
    try:
        settings = config.exapp_settings(env)
    except ToolError:
        # A missing deploy variable is a startup problem and is reported there. Raising here
        # would travel into the enable handler, which must answer with an empty error field.
        logger.error("no occ command was registered: the deploy environment is incomplete")
        return

    url = f"{settings.base_url}{OCC_COMMAND_PATH}"
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
    for scheme in command_schemes():
        try:
            response = await client.post(url, json=scheme, headers=headers)
        except httpx.HTTPError:
            # No value from the request is repeated here: the headers carry the app secret.
            # The name of the command is not a value of the request, it is a constant of this
            # module, so it can be named and has to be.
            logger.error(
                "the registration of %s to %s did not reach Nextcloud", scheme["name"], url
            )
            continue

        if response.status_code // 100 != 2:
            logger.error(
                "the registration of %s to %s answered %s",
                scheme["name"],
                url,
                response.status_code,
            )
