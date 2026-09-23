# Vulture whitelist: names that are reachable, but not through a call vulture can see.
#
# Passing this file to vulture is what lets the dead code gate run at full confidence
# instead of at --min-confidence 80. At 80 the tool reports nothing at all here, which
# makes the CI step decorative in exactly the way the token budget gate used to be.
#
# Every entry below needs a reason. "vulture complained" is not one. A name that cannot be
# justified in one line is dead code and belongs in a delete commit, not in this file.
#
# The bare names are the documented vulture whitelist format: the file is parsed, never
# imported, so undefined names are intentional (ruff and pyright are configured to skip it
# in pyproject.toml).

# --- The tool functions without a visible caller --------------------------------------
# Registered by the @mcp.tool decorator at import time and called by the MCP runtime, never
# from our own code. Every one of them is covered by tests/contract/test_tool_surface.py,
# which fails if any of them stops being listed. The count is deliberately not written here:
# it lives in that contract test, which is the only place that can keep it true.
files_search
files_list
files_read
files_upload
calendar_list_events
calendar_create_event
notes_search
notes_read
notes_create
deck_browse
deck_create_card
tables_browse
tables_create_row
talk_browse
talk_send
mail_browse
contacts_search

# --- Framework entry points -----------------------------------------------------------
# health: registered with @mcp.custom_route and checked by tests/unit/test_transport_
#   security.py and the client matrix, which waits for it before every run.
# verify_token: the one method of the SDK TokenVerifier protocol; the SDK calls it on every
#   authenticated request, tests/unit/test_http_modes.py calls it directly.
# auth_flow: the one method of the httpx.Auth interface; httpx calls it for every request
#   that was given auth=creds.auth(), and tests/unit/test_appapi_credentials.py drives it
#   directly to read the four AppAPI headers off the signed request.
health
_.verify_token
_.auth_flow

# --- Fields of an SDK model that only the serialised document reads --------------------
# scopes_supported, authorization_response_iss_parameter_supported,
#   client_id_metadata_document_supported: three of the four fields oauth/metadata.py sets on
#   the OAuthMetadata model of the SDK after build_metadata built it. Nothing in this
#   repository reads them back; they are written, dumped to JSON and answered to the client,
#   which is exactly what tests/unit/test_oauth_metadata.py asserts on. Assigning them on the
#   model instead of on the dumped dict keeps the field names checked by pydantic and pyright,
#   which is why the write looks unused to vulture.
_.scopes_supported
_.authorization_response_iss_parameter_supported
_.client_id_metadata_document_supported

# --- Read from outside the production call graph --------------------------------------
# deck_api_versions: a capabilities field the Deck integration test asserts on; it exists so
#   an instance that only offers API 1.1 is a named finding instead of a mystery 404.
# NSMAP: the complete DAV namespace map, used by tests/unit/test_xml.py and by every future
#   XML body; splitting it up per call site would invite a typo in a namespace URI.
# get_board: the single board read of the Deck client, covered by tests/unit/test_deck_
#   client.py. deck_browse reaches boards through get_boards, so the singular form currently
#   has no production caller. It stays because it is the only place that knows the shape of
#   the single board route, and it costs eight lines.
deck_api_versions
NSMAP
get_board

# --- The transport layer of the Tables family (plan 08-02, dissolved in plan 08-03) -----
# Empty on purpose, and that is the rule of this file at work rather than an omission. Plan
# 08-02 parked get_tables, get_table, get_columns, get_rows_simple and create_row here,
# because the transport of nextcloud/clients/tables.py was written and tested in one piece
# before its caller existed. Plan 08-03 added tools/tables.py, which calls all five, so every
# one of them left the list with the plan that calls it.

# tables_api_versions: the same case as deck_api_versions above. The gate for the app reads
# tables_available, the version tuple exists so an instance that only offers one generation is
# a named finding instead of a mystery 404 on the rows route. Asserted on in
# tests/unit/test_ocs_capabilities.py.
tables_api_versions

# --- The Talk capabilities of phase 9 (plan 09-01, thinned out in plan 09-03) -----------
# Plan 09-01 parked five names here, because the transport and the app detection of the Talk
# family were written and tested in one piece before their caller existed. Plan 09-03 added
# tools/talk.py, and four of the five left the list with it: get_rooms and get_messages are
# called by talk_browse, send_message and spreed_chat_max_length by talk_send. web_url never
# entered the list, because the name already has a production caller in the Tables family.
#
# spreed_features: the one that stays, and it is the same case as tables_api_versions and
#   deck_api_versions above rather than a parked caller. There is no apiVersions and no
#   enabled field in the spreed section, so this tuple is what the app says about itself, and
#   it exists so an instance whose Talk lacks a chat feature is a named finding instead of a
#   mystery 400. The gate for the app reads spreed_available, which has a production reader in
#   Capabilities.has. Asserted on in tests/unit/test_ocs_capabilities.py.
spreed_features

# talk_send_enabled: gone from this list with plan 09-03, which is the plan that calls it.
# The name was parked in plan 09-02 together with the form, the read path and the export in
# entry_exapp.main, and its production caller is now the first executable line of
# tools.talk.send.

# --- The transport layer of the Mail family (plan 10-02, thinned out in plan 10-04) -------
# The same parked-caller case as Tables in 08-02 and Talk in 09-01: the transport of
# nextcloud/clients/mail.py was written and tested in one piece before its caller existed.
# Plan 10-04 added tools/mail.py, and two of the three left the list with it: get_accounts and
# get_mailboxes are called by mail_browse on its two flat levels. get_messages never entered
# the list, because the name already has a production caller in the Talk family, so vulture
# never reports it and an entry here would be a line nobody could ever check.
#
# get_message and to_text: both gone from this list with plan 10-05, which is the plan that
# calls them. The full message route was parked in plan 10-02 and the HTML to text converter in
# plan 10-03, in both cases because the piece and the tests that pin it belong together and
# the caller was one wave away; ``chatgpt._fetch_mail`` is that caller and it uses both in the
# same three lines. Nothing of the Mail family is parked any more, which is what the empty
# space below this paragraph says.

# --- The context route of one Talk message (plan 11-02, dissolved in plan 11-03) ---------
# Empty on purpose, and that is the rule of this file at work rather than an omission. Plan
# 11-02 parked get_message_context here, because the route and the tests that pin it belong in
# one piece and its caller was one plan away. Plan 11-03 added the ``message:`` branch of
# ``chatgpt.fetch``, which calls it, so the name left the list with the plan that calls it,
# exactly as the entry announced it would.

# --- The store API of phase 3 ----------------------------------------------------------
# oauth/store.py was built in one piece in plan 03-02, because its schema and its
# transactions only make sense together, and its callers arrived plan by plan afterwards.
# Plan 03-07 was the last of them: the rotation calls redeem_refresh_token, load_refresh_
# token and revoke_family, and the revocation calls revoke_authorization, note_cleanup and
# clear_cleanup. What is left below is the one name that is still reachable through the
# store alone. Every entry that gained a production caller left this list with the plan
# that called it.
#
# load_access_token: the store method is called by the verifier on every request, but the
#   name also belongs to the provider method of the same name, which refuses on purpose and
#   therefore has no caller (see the module docstring of oauth/provider.py). One whitelist
#   entry covers both, and dropping it would flag the deliberate refusal as dead code.
_.load_access_token

# --- The store API of phase 4 ----------------------------------------------------------
# Empty, and that is the rule of this file at work rather than an omission. Plan 04-01
# built the per account switch and the account's own connection list as store truths and
# parked three names here; every one of them left the list with the plan that called it.
# access_disabled went in task 2 of that plan (the transport boundary reads it on every MCP
# request), set_access and authorizations_of_user went in plan 04-03, where the connections
# page pauses an account and lists its connections. families_of_authorization never entered
# the list at all: it arrived with its caller, provider.end_connection.

# Fields of the row objects that this phase writes and a later plan reads:
# created_at and issued_at (the admin view of phase 4 shows when a connection was made),
# cleanup_at (03-07 writes it when a Nextcloud app password could not be handed back; the
# sweep selects on the column in SQL, and the field itself is for the same admin view).
_.created_at
_.issued_at
_.cleanup_at

# --- The store API of phase 18 ----------------------------------------------------------
# audit/store.py was built in one piece in plan 18-01, for the same reason oauth/store.py was
# in plan 03-02: its schema, its canonical field order and its chain only make sense
# together, and its callers arrive plan by plan afterwards.
#
# last_entry: the youngest row of one chain, optionally of one kind. Its caller is the switch
#   of D-15, which asks for the last row of kind 'switch' to know which direction it is in,
#   and that arrives in plan 18-07. It is driven directly by
#   tests/unit/test_audit_store.py::test_last_entry_of_a_kind_skips_the_calls_between_two_
#   switches, and it leaves this list with the plan that calls it.
#
# sweep: gone from this list with plan 18-06, which is the plan that calls it. The recorder
#   asks should_sweep about the number append just handed back and pays for the sweep on every
#   five hundredth row (D-11), exactly as the entry announced it would.
# verify_chains and next_seq: gone from this list with plan 18-08, which is the plan that
#   calls them. exapp/audit_verify.py walks the findings and turns each one into the sentence
#   an administrator reads, and next_seq is the second half of "missing between these two
#   numbers" in that sentence. Both left the list with the plan their entry named, which is
#   what this list is for.
# used_bytes_after: what the sweep measured when it was done. The check command of plan 18-08
#   reads its counts through AuditStore.overview and not through a sweep report, because a
#   check may not delete anything to learn how much there is, so this field still has no
#   production reader. Its caller is the reading command of AUDIT-04 in phase 19, which
#   reports what an expiry took; it is asserted on in tests/unit/test_audit_store.py today and
#   leaves this list with that plan. The other fields of both classes carry names that are
#   read elsewhere in the module, which is why only this one stands here.
#
# read_entries: gone from this list with plan 19-06, which is the plan that calls it.
#   exapp/audit_read.py asks it for the rows of one chain and one window and turns them into
#   the lines of the read command of AUDIT-04, exactly as the entry of plan 19-04 announced it
#   would. It left the list with the plan its entry named, which is what this list is for.
_.last_entry
_.used_bytes_after

# --- The marker every recorded tool carries ---------------------------------------------
# __mcp_audited__ is set on the wrapper of server.graceful and read by
# tests/contract/test_audit_surface.py, which walks every registered tool and turns red on
# the first one that does not carry it (D-04). Vulture is pointed at src, scripts and this
# file, never at tests, so the attribute has no reader it can see. It is a marker on purpose
# and will never gain a production reader: an explicit name is what makes the gate honest,
# because fn.__code__.co_name == "wrapper" would pass for any decorator in the world.
_.__mcp_audited__

# --- The block list of audit/allowlist.py -----------------------------------------------
# PARAM_ALLOWLIST is gone from this list with plan 18-06, which is the plan that reads it:
# audit/record.py intersects the set argument names of a call with it before it writes a row.
#
# FORBIDDEN_PARAMS stays, and the entry of plan 18-02 promised otherwise, so the correction
# belongs here rather than in a quiet delete. The recorder never reads the block list: it
# reads the allowlist, and the block list is the rule that keeps a payload name out of that
# allowlist in the first place. Its one reader is therefore
# tests/contract/test_audit_surface.py, and vulture is pointed at src, scripts and this file,
# never at tests. So this name has no production reader by construction rather than by
# schedule, and it will not leave this list with a later plan of this phase.
FORBIDDEN_PARAMS

# --- The frozen reason set of errors.py -------------------------------------------------
# REASONS is gone from this list with plan 18-06, which is the plan that reads it:
# audit/record.py checks the reason of a refused call against the set before it writes it
# into a row, so anything that is not one of the six becomes the honest "unspecified"
# instead of free text in a column that exists to have none.

# --- The methods of the SDK provider protocol ------------------------------------------
# oauth/provider.py implements OAuthAuthorizationServerProvider. Every method below is
# called by the SDK handlers of /authorize, /token and /register, and by nothing in this
# repository: create_auth_routes takes the object and wires the calls itself, the same
# shape as verify_token above. All of them are driven directly by
# tests/unit/test_oauth_provider.py, which is what keeps them honest. load_access_token is
# absent from this list because it already stands in the store block above.
#
# revoke_token stays here although /revoke is served by our own FamilyRevocation now: the
# handler calls revoke_presented_token, which adds the ownership check, and revoke_token is
# the protocol method that any other SDK path would use. Both end in the same revocation.
_.get_client
_.register_client
_.authorize
_.load_authorization_code
_.exchange_authorization_code
_.load_refresh_token
_.exchange_refresh_token
_.revoke_token
_.exchange_identity_assertion

# --- The two methods of the cookie jar that refuses to be one ---------------------------
# nextcloud/http.NoCookieJar overrides both halves of http.cookiejar.CookieJar. They are
# called by urllib through httpx and by nothing in this repository, and their whole job is
# to do nothing: a shared client must not keep or send a Nextcloud session cookie, which is
# the identity mix up plan 03-08 measured. tests/unit/test_credentials_http.py drives both.
_.set_cookie
_.add_cookie_header
_.cookie

# --- The code primitive that BL-19 left to the tests ------------------------------------
# create_auth_code writes one authorization code and nothing else. Until BL-19 the consent
# screen called it and then deleted the flow, and that pair was the check then act which let
# two parallel approvals mint two codes for one consent. redeem_flow_for_code replaced the
# pair with a single compare and set and is now the only production path to a code.
#
# The primitive stays because the tests need a code without a flow: the rotation, provider
# and abuse suites assert what happens to an existing code (exchange, replay, revocation,
# ownership), and routing each of them through a flow would add setup that says nothing
# about the thing under test. tests/unit/test_oauth_store.py drives it directly.
_.create_auth_code

# --- The account source seam of plan 23-02 ----------------------------------------------
# identity_for: the one method of the ExchangeAccounts protocol in oauth/exchange_accounts.py.
#   Its caller is the EXCHANGE_CLAIM branch of ChainedVerifier.resolve_identity, which is
#   task 3 of the very same plan; the entry leaves this list with that task's commit.
_.identity_for

# --- The exchange checker, wired in by the chain of plan 22-02 ---------------------------
# _decode_payload: the one method of _PreparsedJWT in oauth/exchange.py. PyJWT documents it
# as the hook a subclass overrides to decode a payload differently, and PyJWT.decode is what
# calls it, so it has no caller in this repository by construction. The override is what
# keeps the payload of one token from being base64-decoded and JSON-parsed twice, and
# tests/unit/test_oauth_exchange.py counts the parses of exactly those bytes.
_._decode_payload
