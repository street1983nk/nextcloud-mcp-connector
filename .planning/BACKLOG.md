# Backlog

Ideas and tasks that are decided in principle but not yet assigned to a phase.
Review with /gsd:review-backlog before planning a new phase.

## BL-01: Findling synergy, a prominent banner on both sides (after the 1.0.0 release)

**Trigger:** Findling is released to the app store as 1.0.0. Note that there is no
separate v1.0: owner decisions D-08 and D-11 bundle full text, OCR and semantic
search into one store first release. That is deliberately the right moment for this
banner, because the semantic half is what makes the retrieval claim fully true. Not
before, and before Findling's phase 6 the claim would be the weaker one about a
lexical index with OCR.

**Blocked by:** BL-02 (the fidelity test has to pass before the claim goes anywhere)
and BL-15 (while every search answer says contents are not indexed, the banner
contradicts the product's own tool output).

**What:** Owner directive 2026-09-04, "prominently on both sides". A banner near the
top of README.md, README.de.md and README.fr.md, mirrored by the Findling side
(their BACKLOG BL-F01), plus the docs site and the n8n guide.

The wording is the point of this entry, so it is fixed here rather than left to the
day. Say **retrieval layer for your own RAG**, do NOT say "this is a RAG system".
RAG has three parts and neither product ships the generation: the model is always
the client (Claude, ChatGPT, MUCGPT, n8n). Whoever reads "RAG system" expects a
finished thing with a chat UI, chunking and a bundled model, and that gap between
expectation and delivery lands straight in the store reviews, where five honest
ones in 90 days are the strongest ranking lever there is.

Lead instead with the property that almost every turnkey RAG product gets wrong:
**per-user permission fidelity**. The usual build indexes everything into one vector
store under a service account and then leaks across users. Here the ACL prefilter
plus Findling's final PHP recheck, behind this connector's impersonation, means the
assistant sees exactly what that user may see and not one sentence more. That is
rare, it is measurable (BL-02 measures it), and it is the first question a data
protection officer asks.

Draft, to be translated for the other two READMEs:

    Findling + Nextcloud MCP Connector = the retrieval layer for your own RAG.
    Findling makes the content of your documents searchable, scans included, and
    1.0.0 adds semantic search. The connector hands those hits to any MCP client,
    with exactly the rights of the asking user. You bring the model, and no content
    leaves your server.

**Audience split, on purpose:** the acronym belongs in the READMEs, on the docs site
and in the n8n guide, where developers read and search for it. The store texts of
both apps keep their plain language ("Search the inside of your documents") and get
at most one closing sentence. A Nextcloud admin in a mid-sized company does not
search for RAG, and Nextcloud markets something RAG shaped first party with Assistant
and context_chat; a head-on comparison with a first-party feature does not help us.
The store text is gated by D-12 of the Findling side anyway.

**Store mechanics, checked 2026-09-04 against the pinned schema** (APPSTORE_SHA
`5c4373d7`, `nextcloudappstore/api/v1/release/info.xsd`):

- The schema has **no** field for this. Its elements are info, id, name, summary,
  description, version, licence, author, namespace, types, documentation, category,
  website, discussion, bugs, repository, screenshot, donation, dependencies and the
  technical registrations. There is no `related`, `works-with`, `recommend` or
  `suggest`. So it is prose inside `<description>`, there is no "related apps"
  widget, and **no automatic backlink appears on the other app's page**. Both sides
  carry their own sentence, which is why BL-F01 exists on the Findling side.
- `<description>` renders Markdown. Headings, links and bullet lists all work; this
  app's own store text already uses them and already links out to the n8n guide from
  a "Resources" section in all three languages. That section is the natural home for
  the Findling link, next to the prose sentence higher up.
- Room is generous: the three descriptions of this app are currently about 4400
  (en), 4900 (de) and 5200 (fr) characters. The Findling gate limits `name` and
  `summary` to 128 characters and does not limit the description at all. Forbidden
  in prose either way: em dash, en dash, emoji (gate), plus backticks and tables
  (project rule).

**Release ordering, and this is the trap:** the store text comes out of the
`info.xml` of the uploaded release. It cannot be edited afterwards, it travels with
a version. The n8n store text in this repo carries exactly that note, "kommt mit
0.1.12".

Therefore this connector needs **a release after Findling 1.0.0 is in the store**,
for no other reason than to carry the cross-link. 0.1.12 is release-ready and is to
be delivered after the ISV call on 14.09.2026, so if Findling lands later, a link in
0.1.12 would point at an app page that does not exist yet. Two ways out, to be
decided when the dates are known: let the cross-link wait for 0.1.13, or link to the
GitHub repository instead of the store page, which is valid at any time. Do not
silently ship a dead store link.

**Why:** Each product closes the other one's biggest gap. Findling without a client
is a search box; the connector without Findling tells every assistant that contents
are not indexed. Together they are the retrieval half of a local RAG, and the half
that is hard to buy: the permission-correct one.

## BL-02: Findling synergy, content-hit permission fidelity test (after Findling v1.0)

**STATUS 2026-09-07: IMPLEMENTED** (Findling 1.0.1 is in the store since today, the trigger
holds). tests/integration/test_content_hit_fidelity.py measures all four steps in one test;
scripts/install_findling.sh builds the state from the real store artifacts; the exapp CI job
installs Findling and runs the measurement on every push. Proven locally against a full HaRP
topology with Findling 1.0.1: alice's marker arrives as a content hit (excerpt carries it,
no title does), bob gets an empty answer from a provider that answered. Once this is merged
and green, BL-01 and BL-15 lose this blocker.

**Trigger:** same as BL-01.

**What:** Integration test in this repo, guarded by a skip when Findling is not
installed on the test instance: alice uploads a document whose UNIQUE marker exists
only in the CONTENT (not in the file name, e.g. text inside a PDF), then
(1) positive control: alice finds it over unified_search via the full ExApp chain,
(2) leak test: bob does not, (3) the hit is proven to be a content hit (file name
carries no marker). Extends the existing leak-test methodology from
tests/integration/test_permission_fidelity_exapp.py to content-level results and
proves Findling's PHP recheck holds behind our impersonation.

**Why:** The synergy claim ("assistant searches inside documents, permissions
intact") must be a measured fact before it goes into any README or pitch.

## BL-03: Findling synergy, demo video (optional, after BL-02)

**What:** Short promo (German working title "Frag deine Cloud"): assistant is asked
a question, unified_search hits the passage inside a scanned PDF (Findling),
files_read fetches it, answer with source. Both products on screen, on-prem framing.
Owner publishes.

**Decision note:** No direct connector-to-Findling tool. Everything goes through
the Nextcloud unified search, so Nextcloud stays the single permission boundary,
as both threat models require.

## BL-04: Local clients (loopback, private-use scheme) as OAuth clients

**STATUS 2026-08-20: DONE** (commit a80af0a, owner decision "Teilregistrierung"):
`register_client` drops the inadmissible entries of `redirect_uris` and registers the
allowed ones, so Cursor's three-way body is answered with 201 naming its two allowed
addresses, while a body of inadmissible addresses alone stays a 400 `invalid_redirect_uri`
and private-use schemes stay unregistrable (D-35 unchanged). Tests 6b26f46, docs 8da82b9.
Still open below: the loopback port question, which this change does not touch.

**Finding (03-RESEARCH.md):** Claude Code uses loopback redirects and CIMD and does
not fit the exact redirect matching of v1. In v1 Claude Code stays on the app
password path (AUTH-01, works today). Later: implement the loopback exception per
RFC 8252 section 7.3 (any port on 127.0.0.1) cleanly.

**Measured 2026-08-16 against staging (03-09-MEASUREMENTS.md, run 4):** The
assumption was wrong. Loopback is not the obstacle, D-35 allows it: a registration
with `http://127.0.0.1:49731/callback` alone is accepted with 201. Cursor fails on
something else. Cursor registers three redirect URIs at once:

```
cursor://anysphere.cursor-mcp/oauth/callback
https://www.cursor.com/agents/mcp/oauth/callback
http://localhost:8787/callback
```

The first is a private-use URI scheme. Our rule only knows https and loopback, and
it validates the whole field: one disallowed entry makes the entire registration
fail with 400 `invalid_redirect_uri`, even though two allowed addresses are present.
Counter-check: the same body without the first entry is accepted with 201. Cursor
prints our error message verbatim in its own log and does not connect.

**So these are two separate decisions, not one:**

1. **All-or-nothing on the `redirect_uris` field.** A server may also drop disallowed
   entries and register the rest. Then Cursor would get through, because it would
   have to pick one of the remaining addresses when authorizing anyway. Fail-closed
   is the stricter reading, and the one chosen today.
2. **Private-use URI schemes.** RFC 8252 names them in section 7.1 as one of the
   three allowed forms for native clients; D-35 deliberately allowed only 7.2 (https)
   and 7.3 (loopback), because a scheme on the desktop belongs to nobody
   exclusively and any other application can intercept it. That reasoning still
   stands. What is new is only the measured price: a whole client class stays out.

**Still open** is the original port question: Cursor uses a fixed port (8787), so
this run says nothing about whether a client with a changing loopback port fails at
our exact matching. Answering that needs a client that picks a fresh port per run
(Claude Code is the candidate).

## BL-05: Client ID Metadata Documents as the successor to DCR

**Trigger (plan 03-09):** The MCP authorization spec introduces Client ID Metadata
Documents (CIMD) and marks Dynamic Client Registration as superseded. Today this
server carries DCR exclusively; a client that identifies itself via CIMD (Claude
Code does) cannot sign in here.

**What would be needed:** Allow deriving the client identity additionally from a
metadata document named by the client, with the same controls as DCR today: check
redirect URIs, the allowlist mode (AUTH-07) applies here too, and a disabled DCR
must not be bypassed via CIMD. Fetching the document is an outbound request from the
instance and therefore needs its own review (SSRF, cache, size limit).

**Why not in v1:** AUTH-04 is satisfied with DCR, both hosted connectors connect.
CIMD is future-proofing, not a prerequisite.

## BL-06: Admin settings UI, one-click principle (owner directive 2026-08-17)

**Owner directive:** Everything should be simple, one click and you are in, and the
admin must still have the opportunity to make settings.

**Current state:** The user side largely fulfils the principle (paste the URL into
the client, sign in, done; switch and disconnect on /connections). The admin side is
pure env-var configuration (NC_MCP_OAUTH_DCR, NC_MCP_OAUTH_ALLOWLIST_ONLY,
NC_MCP_OAUTH_ALLOWED_CLIENTS, NC_MCP_ALLOWED_HOSTS, NC_MCP_PUBLIC_URL, ...). This
collides with one-click store installation (phase 5 SC 2): an admin installing from
the app store sets no env vars.

**What would be needed (phase 5):** An admin settings entry for the security-relevant
switches (at least DCR on/off and allowlist), with safe defaults from installation,
so the one-click path works without mandatory configuration and the security note
(public instances: allowlist ON or DCR OFF) is satisfiable via UI instead of only
via env. Research caveat: declarative settings are pull-only (04-RESEARCH); for admin
values the ExApp needs at runtime, the storage location (appconfig via AppAPI vs. own
store) has to be clarified.

**Why not in phase 4:** Phase 4 was the per-user slice; the admin switches hang on
store packaging (EXAPP-04/05).

## BL-07: Privacy doc and data-sharing disclosure (owner question 2026-08-17)

**STATUS 2026-08-17: doc part DONE** (docs/privacy.md pushed; data sharing described
as prose in info.xml <description>, because the store has no data-sharing field, see
05-store-research.md question 4). The only remaining item is to mirror the note into
the later client setup docs.

**Trigger:** Privacy review of the connector. The connector itself is
privacy-friendly (self-hosted, no telemetry, no calls except to its own Nextcloud,
app passwords encrypted at rest, tokens only as a hash, purpose limitation: the
assistant never sees more than the user does on the web). But there was no privacy
doc in docs/.

**The GDPR crux is behind the connector:** Once a user connects a hosted AI client
(Claude.ai, ChatGPT), the retrieved Nextcloud content (files, calendar, contacts, and
via prepare_context also file excerpts) flows to the LLM provider, usually a third
country (US). The connector transmits nothing on its own but is the door. Operators
need a legal basis for this (data processing agreement with the LLM provider, where
applicable consent, a transfer impact assessment for the third-country transfer). An
EU/self-hosted LLM (e.g. MUCGPT) defuses this.

**What would be needed (phase 5, also covers SC 1 data-sharing disclosure):**
1. docs/privacy.md (or datenschutz.md): which personal data the connector stores
   (nc_user, encrypted app password, token hashes, timestamps), where (SQLite in the
   ExApp container), encryption, deletion (disconnect/uninstall), data subject rights.
2. Data-sharing disclosure for the app store: state clearly that content goes to the
   AI client chosen by the user, with a third-country/LLM note and a recommendation
   to review the client's privacy terms.
3. info.xml description: the assurance "never sees more than the user" stays correct
   but must not suggest that no data flows to the client after the tool call.

**Why not in phase 4:** Phase 4 was the per-user slice; store disclosure and docs
belong to phase 5 (EXAPP-04/05, SC 1).

## BL-08: Anti-forgery values with a time window, or track as accepted risk (review 04, ME-02)

**STATUS 2026-08-20: DONE** (commit f65225c, owner decision "Zeitfenster 1h"):
`form_token` takes `FORM_TOKEN_WINDOW = 3600` into its derivation and the new
`form_token_valid` accepts the current and the previous window with `compare_digest`, so a
form open across a full hour still submits and one older than two windows gets the existing
quiet refusal; the `crypto.py` docstring now says what the value is and what it still is not
(no nonce, no consumption, replayable inside its window). Tests 2ae2e3e.

**Finding:** `form_token` is a pure function of data key, purpose and handle. The
value has no validity period, no nonce, no session binding and no consumption count:
for one account the switch value stays the same over the whole lifetime of the
installation. Whoever obtains it once can pause and resume that account's MCP access
indefinitely via cross-site POST, as long as the user is signed in to Nextcloud. The
only rotation point would be the data key, and rotating it makes every stored app
password unreadable, so it breaks all connections.

**What to decide (owner):** Take a time window into the derivation, as is common for
double-submit tokens (review proposal: `FORM_TOKEN_WINDOW = 3600`, accept the current
and previous window, both with `compare_digest`). This is a UX decision, not a pure
security decision: a form left open longer than two windows becomes invalid, and the
user gets the quiet refusal instead of their action. Alternative: track the matter as
an accepted risk with an id, instead of describing it in `crypto.py` as a full
protection.

**Not done in the review fix,** because the window width and the behavior of open tabs
are a product decision. ME-01 (purpose binding) is implemented and independent of it.

## BL-09: Pull the excerpt truncation marker out of the text (review 04, ME-03, D-57)

**STATUS 2026-08-20: DONE (interim)** (commit 9b3a46e, tests a0deb8e, owner decision
"Interim-Fix"): the marker stays in the text and can no longer come from a document. The
new `tools/marks.py` holds both sequences and one filter for them; `context._capped` runs
the filter before it measures and marks, and all four readers of `chatgpt.fetch` run it
before the file reader writes its own note back in. The response schema of
`prepare_context` and the ChatGPT contract of `fetch` are **unchanged**, which is the whole
point of the interim variant.

**The schema variant was deliberately not chosen.** A separate field
(`hit["excerpt_truncated"] = True`) is the clean answer and stays the one named above: it
is the only form a document cannot produce at all. It changes the response structure of
`prepare_context` and touches `chatgpt.fetch`, where the marker sits in the text on purpose
so a model that reads only `text` sees the difference. That is a schema decision (tool
budget, client compatibility) and it was not made here. The honest limit of what shipped is
in the module docstring of `marks.py`: only the exact sequences are removed, a document can
still write something that reads like a marker, and no filter over free text can prevent
that.

**Finding:** `context._capped` appends `EXCERPT_TRUNCATION` to the user text without a
separator, and `chatgpt.TRUNCATION_NOTE` runs into the same text stream. A document
containing the same character sequence can look to the model as if the server excerpt
ends there and a system message follows: the attacker decides on the framing of their
own text, which is exactly the boundary D-57 relies on. Conversely a document can
claim to be complete where it was truncated.

**What to decide (owner):** The clean way is a separate field
(`hit["excerpt_truncated"] = True`) that a document cannot produce. This changes the
response structure of `prepare_context` and, at `chatgpt.fetch`, touches the
ChatGPT-compatible contract, in which the marker deliberately sits in the text so a
model that only reads `text` sees the difference. Both together are a schema decision
(tool budget, client compatibility), not a local fix.

**Interim step, if the marker should stay in the text:** use a separator that
`_capped` filters out of the user text beforehand, and do not write
`chatgpt.TRUNCATION_NOTE` unchecked into the same stream.

## BL-10: Enforce the switch where an authorization is created too (review 04, ME-04)

**STATUS 2026-08-19: DONE** (plan 05-02, commits `1cbd714` test and `9d16fec` feat for the
page, `e24673c` test and `cf9f3db` feat for the three enforcement points): the switch is read
where an authorization is created, not only at `MCP_PATH`. The three points are the poll of
`/authorize` (before `create_authorization`), `connect._wait` (before the credential is shown)
and `/authorize/decide` (before the grant); each hands the Nextcloud app password back, so the
set of valid app passwords does not grow while the brake is pulled. A store that cannot answer
is never a "no" (fail closed). The refusal is the page `E9` (`PAUSED`) and never an
`access_denied` redirect, because that error means the user said no and this user said nothing.
The texts `SWITCH_OFF_STATE`, `CONNECTIONS_PAUSED_BODY` and `ACCESS_DISABLED_DESCRIPTION` stayed
as they were: they are true now. The consent screen itself was added to the same reading later,
as IN-06 of BL-13 below.

**Finding:** The gate hangs on `MCP_PATH` only. `/authorize`, `/authorize/decide` and
`POST /connect` are unthrottled, so a paused account can complete a full login flow,
and Nextcloud creates a real app password in the process that lands in the store. Only
the later tool call runs into R1. The UI says "MCP access is switched off for your
account", and the set of valid Nextcloud app passwords keeps growing despite the
pulled brake.

**What to decide (owner):** Either check the switch at exactly the point where an
authorization is created (before `create_authorization` in `consent.py` and before
`_start` in `connect.py`, the response being the same page that shows the switch), or
sharpen the texts (`SWITCH_OFF_STATE`, `CONNECTIONS_PAUSED_BODY`,
`ACCESS_DISABLED_DESCRIPTION`) and track the matter as a risk with an id. What must not
stay is the gap between promise and enforcement.

**Not done in the review fix,** because both ways touch the app password flow: the
check falls in the middle of the Login Flow v2 sequence, in which the poll answers
exactly once and an abort after the poll forces a return. That is a design decision,
not worth guessing.

## BL-11: Three smaller findings from the phase 4 review (LO-02, LO-03, LO-06)

**STATUS 2026-08-20: DONE** (all three, with their tests):

| Id | Fix | Commits |
|----|-----|---------|
| LO-02 | The schema script runs on the first open of a store object plus whenever the file is gone, instead of on every open. The `access_disabled` docstring now carries what was measured on 2026-08-20 (300 warm runs each): 1.77 ms per call before, 1.56 ms after, and a bare connection with the three pragmas and this one read is 1.51 ms of it, so what is left is the connection and not the script. The file that disappears at runtime is the named case: the `exists` check lays the schema down again, the rows are gone with the file and the process keeps answering. | 6790ef2, tests 0d96f91 |
| LO-03 | `purge_expired` removes a `user_access` row when the account has no authorization at all and the pause is older than the new `STALE_ACCESS_TTL` (90 days, the same season as `IDLE_CLIENT_TTL`). A revoked authorization still counts as a connection. The reused account id case and the price of the window (a pause without any connection is forgotten after 90 days) are named in `docs/faq.md`, administrator section. | 16d2fee, tests 2d992cc, docs 259721b |
| LO-06 | `chatgpt.fetch` takes an optional `max_bytes` and hands it to the file reader; `context._excerpt` passes `EXCERPT_READ_BYTES` (twice the excerpt ceiling, so a multi byte cut still fills it). The default is the old ceiling, the registered tool keeps its two parameters, and the excerpt is byte for byte the one a full read produced. | fd2c53c, tests 9751889 |

None of the three is a security defect, but each has a nameable price.

**LO-02, `access_disabled` costs more than the docstring says.** Measured 1.54 ms per
call (300 runs, warm), because `_connect` runs `mkdir`, three pragmas,
`executescript(SCHEMA)` with 13 statements and two `PRAGMA table_info` on every open.
This sits on every MCP request of an authenticated identity, and `/mcp` deliberately
carries no throttling. **To do:** run the schema only on the first open per process
(flag in `OAuthStore`, set after the first successful `_connect`) and fix the docstring
to what was measured. To clarify: behavior when the file disappears at runtime.

**LO-03, `user_access` rows are never cleaned up.** The table grows monotonically and
holds rows for accounts that no longer exist; on directory setups that reuse account
ids, a new account with the same name starts silently paused. Visible and fixable via
/connections, but surprising. **To do:** extend `purge_expired` to clean up accounts
with no authorization at all and an old `disabled_at`, or listen for a `deleteUser`
event from Nextcloud (if an ExApp can reach it), and name the edge case in `docs/`.

**LO-06, a 2 KB excerpt costs up to 512 KB of transfer per hit.** `context._excerpt`
calls `chatgpt_tools.fetch`, which reads up to `files.DEFAULT_MAX_BYTES` (512 KB) to
keep 2 KB of it: at `detail="full"` up to 1.5 MB of Nextcloud transfer per bundle
call, bounded in time by `EXCERPT_TIMEOUT`, in volume not at all. **To do:** pass a read
limit through `fetch` (e.g. `max_bytes=EXCERPT_MAX_BYTES * 2`). Changes nothing about
the result and saves the factor 250; but it touches the signature of `fetch`, which
belongs to the ChatGPT contract, so decide it together with BL-09.

## BL-12: MUCGPT integration, clarify the auth model (owner question 2026-08-18)

**Trigger:** Owner plans outreach to the MUCGPT team (it@M / City of Munich) once the
connector is online. Question: does MUCGPT need an adapted version?

**Research finding (verified against the repo it-at-m/mucgpt):**
- MUCGPT IS a full MCP client: mucgpt-core-service/app/agent/tools/mcp.py uses
  langchain_mcp_adapters + mcp.ClientSession, MCP servers are configurable via
  config.yaml (MCP: section), and there is an McpBearerAuthProvider. So NO forked or
  adapted connector version is needed, the protocol fits.
- BUT MUCGPT's MCP auth can only do static credentials: forward_auth_override (e.g.
  "Basic base64(email:app-password)"), custom headers, or forward_token (passes
  MUCGPT's own Keycloak OIDC token through). NO OAuth 2.1 discovery/DCR/browser login
  as Claude.ai/ChatGPT use.
- CRUX = identity, not protocol: with a static app password, ALL MUCGPT users run
  under ONE Nextcloud account, which collides with our core "every request under the
  user's identity". For real per-user separation, either MUCGPT would pass per-user
  credentials through (their work) OR we build an extension that accepts MUCGPT's OIDC
  token and exchanges it against Nextcloud (token exchange) = the possibly "requested
  adapted version".

**For phase 5 SC4 (MUCGPT setup doc, verified against the real client):**
- Document the out-of-the-box path: app password via forward_auth_override (service
  account or per user). Works with the credential-based path.
- Ask the auth question in first contact: is a team/service account enough, or do you
  need per-user permission fidelity (then token exchange as a feature)?
- Stress the privacy advantage: EU/self-hosted, NO third-country flow (unlike
  Claude.ai). MUCGPT itself has inference_location/data residency (issue #1116), which
  matches docs/privacy.md exactly.

**STATUS 2026-08-20: Owner hat die Mail an it@M gesendet, Antwort ausstehend.** The
verification below stays open until access to a running instance exists; nothing in this
repository moves it forward before that answer arrives.

**Verprobung offen (verification still open, plan 05-16):** The MUCGPT section of
`docs/client-setup.md` is the only client section on that page without a measurement
behind it; it is derived from the source of it-at-m/mucgpt (2026-08-18), not from a run.
05-VERIFICATION.md carries this as truth 4, UNCERTAIN.

- **Trigger:** access to a running MUCGPT instance together with its Keycloak, usually
  via the it@M contact of the outreach line. The contact is the owner's to make (outreach
  rule: drafts here, sending always by the owner). Nothing about this is automatable in
  this repository.
- **What to run:** the protocol at the end of the MUCGPT section in
  `docs/client-setup.md` ("Closing the gap: the protocol, three checks in the order they
  can fail"). The three check points are, in that order: (1) does the `Authorization`
  header arrive at all, (2) does the tool list come back, (3) does a tool call answer
  with content of the configured Nextcloud account, plus the counter check that a file
  the account may not see stays invisible. Each check names what to note.
- **Ask while you are there:** the identity question above (one `forward_auth_override`
  per source means all MUCGPT users share one Nextcloud account). Is a team or service
  account enough, or is per user fidelity needed? That answer decides whether token
  exchange becomes a feature.
- **Result:** a measurement file next to the other client proofs, then the gap paragraph
  in `docs/client-setup.md` is replaced by a dated line and this section is closed.

## BL-13: The advisory findings of the phase 5 review (IN-01 to IN-06, both passes)

**STATUS 2026-08-20: DONE** (all ten rows below, each with its tests). Two review passes used
the same ids for different findings: 05-REVIEW.md was rewritten as the re-review of the gap
closure (diff `eebcc4c..HEAD`), where IN-01 and IN-04 are the two that stayed open from the
first pass and IN-02, IN-03, IN-05 and IN-06 are new. The four findings of the first pass that
the re-review did not look at again (its remit was eleven changed files) were still open in the
code and are closed here as well, marked "first pass" below.

| Id | Fix | Commits |
|----|-----|---------|
| IN-01 | `purge._payload` no longer trusts the announced `Content-Length`: `_bounded_body` sums `request.stream()` and stops at `MAX_BODY_BYTES`, so a chunked request without a length is not read into memory. The measured price of the old shape is in the test: half a megabyte around a valid `force` flag purged the whole instance. The stream is left where it stopped, because draining it is the read this avoids; the header check stays as the cheaper first refusal. | `85d19dd` test, `4673479` fix |
| IN-02 | The rescue line of `entry_exapp.main` names both places an address can come from ("correct the deploy variable, or enter a usable address in the form, a stored value wins over the variable"). Since the CR-01 prevention refuses an unusable form value before the build, the case this branch really sees is a deploy variable, and the old wording sent the administrator to an empty field. | `3a73cab` test, `6c3f795` fix |
| IN-03 | `config_values._public_url` returns one spelling: scheme and host lowercased per RFC 3986, the path, the query and the port untouched, an IPv6 literal keeps its brackets. The value becomes the `issuer` and the `resource` prefix, and clients compare both character by character. | `4f8dd04` test, `65cae6c` fix |
| IN-04 | The dated evidence blocks keep `tools=15` and now say which run that is from; a contract test holds the rule that a page naming a count other than the current one has to point at `tests/contract/test_tool_surface.py`, which is where the number lives. `docs/spike-discovery.md` is covered too. | `eb0ba56` (fix and test) |
| IN-05 | The nine validators of the three shell scripts use `grep -E ... >/dev/null` (and `grep -Ez` where `-z` is needed) instead of `grep -Eq`/`-Eqz`, and the guard test matches the pattern `\| grep -...q` over line continuations instead of the literal `\| grep -q`. The comment states the rule for every pipe, not for occ pipes only. | `9f1deec` test, `9628ee8` fix |
| IN-06 | `provider.auth_routes` raises `IssuerRefused`, a `ToolError` with a name, and the rescue in `main` catches that type; every other build time failure is reported as itself and ends the start. | `9c4a3f0` test, `b0f808d` fix |
| IN-02 (first pass) | `connect_routes` calls `store.store_opener(env)` instead of carrying a word for word copy of it. The behaviour was pinned first: one store per application, one sweep, the same file. | `1d71073` test, `4f9d267` refactor |
| IN-03 (first pass) | The `doc_url` of the admin form points at the public FAQ while `config.public_url` still answers the default in code. Built from the loopback default it was a link into the administrator's own browser machine, on the very form that fixes that state. | `71062fc` test, `d5c7334` fix |
| IN-05 (first pass) | The `clients` row of `docs/privacy.md` says the issued secret is stored as a hash only, never in the clear, which is what `clients.client_secret_hash` holds. A test holds the row and the schema together. | `064f7c0` (fix and test) |
| IN-06 (first pass) | `consent._screen` reads the account switch in the `signed_in is not None` branch, so a screen reloaded after the account was paused answers with the paused page instead of offering approve and deny. A display check and not a fourth enforcement point: the GET changes nothing, and an unreadable switch is the same fail closed page the decision gives. | `7e8420f` test, `398d38a` fix |

None of the ten was a blocker: both passes classified them as info, the one critical (CR-01) and
the warnings (WR-01 to WR-03 of the first pass, WR-01 of the re-review) were closed in plans
05-11 and 05-15 and in commit `8c5954f`.

**The findings as they were written down, for the record:**

| Id | File | Finding | Proposed fix (from the review) |
|----|------|---------|--------------------------------|
| IN-01 | `src/mcp_connector/exapp/purge.py:356-379` | The body size limit of the purge handler only reads the announced `Content-Length`, so a chunked request (or a non numeric header) is read into memory unbounded; reachable only over the authenticated internal AppAPI path. | Read the stream with a limit (sum up `request.stream()` and stop at `MAX_BODY_BYTES`) instead of trusting the header. |
| IN-02 | `src/mcp_connector/entry_exapp.py:354-366` | The rescue line says "The stored value is kept, so it can be corrected where it was entered" and points at the admin form, whatever the source was; after the CR-01 hardening the branch really only sees an unusable `NC_MCP_PUBLIC_URL` from the deploy environment, where that form is empty. | Name both sources in the line, with the precedence rule between them. |
| IN-03 | `src/mcp_connector/exapp/config_values.py:258-302` | `_public_url` returns the value unchanged, so `HTTPS://Cloud.Example.COM` becomes the `issuer` verbatim while the documentation says clients compare it character by character. Scheme and host are case insensitive per RFC 3986, so lowercasing them is lossless. | Normalise scheme and host in `_public_url` and move the pinning test to the normalised expectation. |
| IN-04 | `docs/oauth-setup.md:287,547` vs `docs/client-setup.md:11,621` | The dated evidence blocks say `tools=15` while the rest of the documentation says 16 (`prepare_context` arrived in phase 4). Formally correct as a literal record of a run, but nothing explains the difference to a reader who counts. | A bracketed note at one of the 15 places, or refresh the evidence on the next run. |
| IN-05 | `scripts/bootstrap_exapp.sh:166,537,553,562,579` and `tests/unit/test_exapp_env_setup.py:1478-1491` | The rule "grep on an occ pipe never uses -q here" is enforced by a test that only sees the literal `\| grep -q`, while every validator pipes into `grep -Eq` or `grep -Eqz`. Harmless there (the writer is a `printf`), but rule and gate have drifted apart. | Sharpen the test to the pattern and move the validators to `grep -E ... >/dev/null`, or narrow the rule in the comment and document the exception. |
| IN-06 | `src/mcp_connector/entry_exapp.py:338-374` | The rescue catches every `ToolError` of `build_exapp_app`. True today, because `provider.auth_routes` is the only build time source, but a future second one would be logged as a public URL problem, would have the address dropped and would end in a confusing double message. | Mark the issuer refusal with its own exception type and narrow the rescue to it. |
| IN-02 (first pass) | `src/mcp_connector/oauth/connect.py:127-146` vs `src/mcp_connector/oauth/store.py:1275-1310` | `connect_routes` carries a word for word copy of the opener logic of `store.store_opener` (double checked locking, key first, `purge_expired` on first open), so a change to one side silently misses the other. | `store_provider = store_provider or store_opener(env)` at the top of `connect_routes`, then delete the local copy. |
| IN-03 (first pass) | `src/mcp_connector/exapp/admin_settings.py:80-89` | On a fresh store installation with no value set, `doc_url` of the admin form is built from the loopback default, so the form that fixes the state contains a dead link to `http://127.0.0.1:8765/connections`. No security issue, T-04-40 holds. | Leave `doc_url` out when `config.public_url(env) == config.DEFAULT_PUBLIC_URL`, or point it at the repository FAQ. |
| IN-05 (first pass) | `docs/privacy.md:38` | The row "Client registrations \| clients \| the assistant apps, their redirect targets and issued secrets" reads as if client secrets were stored in the clear; `clients.client_secret_hash` holds only a SHA-256 digest. Imprecise in the wrong direction for a document aimed at data protection officers. | "issued secrets (stored as a hash only, never in the clear)", or fold the row into the hash row of the tokens. |
| IN-06 (first pass) | `src/mcp_connector/oauth/consent.py:302-304` | `_screen` jumps straight to `_decision` when an authorization row already exists, without reading the account switch, so a consent screen reloaded after the account was paused in another tab still shows approve and deny. No grant is possible (enforcement point 3 answers the click with E9), so this is a UX inconsistency against the documented enforcement points. | Read `_access_disabled` in the `signed_in is not None` branch and answer with the `_refuse_paused` path, as after the poll. (Only the first half was taken: `_refuse_paused` revokes the app password and deletes the flow, and its docstring says it runs where no authorization row exists yet. This branch is a GET with a row present, so it answers the paused page and changes nothing.) |

## BL-14: Cursor still cannot sign in after the partial registration (measured 2026-08-20, CLIENT-04, CLOSED 2026-08-20)

**STATUS 2026-08-20: CLOSED** (owner decision of 2026-08-20, option 3 in the reading "make the
dropped part visible plus documentation"; carried out by plan 06-11). The four options below
stay word for word, because they are the record the decision was taken from.

**What was done:**

- The refusal page `E5` names the way that works, an app password from the Nextcloud security
  settings, and it still says nothing about which of the four checks in `oauth/consent.py`
  fell (T-03-24 unchanged). One test holds both halves of that.
- `docs/client-setup.md` now carries the reason behind D-35 that it did not carry, and
  `docs/oauth-setup.md` carries this decision instead of the open sentence it had.
- CLIENT-04 in `.planning/REQUIREMENTS.md` and success criterion 3 of phase 6 in
  `.planning/ROADMAP.md` say what was measured, marked as a requirement change made with
  owner approval, and CLIENT-04 is checked off.

**What was deliberately not done, with the reason for each:**

- Option 1, register the private-use scheme after all: not taken. D-35 is unchanged and so is
  the reason behind it, that on a desktop no application owns a scheme exclusively, so another
  program can claim it and receive the authorization code.
- Option 2, refuse the whole registration again: not taken. That was 0.1.1. It kept Cursor out
  one endpoint earlier and it additionally kept out clients that do offer an admissible
  address.
- The extra field in the registration answer, which is the part of the owner decision that
  asked whether RFC 7591 would allow naming the dropped addresses: not taken. RFC 7591 3.2.1
  asks the server to answer with the registered metadata and does not forbid extension fields,
  but the answer model of the SDK in use carries no extra field. Measured on 2026-08-20
  against `mcp 2.0.0`, without network, instance or container:

```
$ uv run --no-sync python -c "
from mcp.shared.auth import OAuthClientInformationFull as C
row = {'client_id': 'x', 'redirect_uris': ['https://a.example/cb']}
c = C.model_validate(row)
try:
    c.dropped_redirect_uris = ['cursor://anysphere.cursor-mcp/oauth/callback']
    print('SET OK')
except Exception as exc:
    print('SET REFUSED:', type(exc).__name__, exc)
extra = C.model_validate({**row, 'dropped_redirect_uris': ['x']}).model_dump_json()
print('EXTRA IN ANSWER:', 'dropped_redirect_uris' in extra)
print('SDK model_config:', C.model_config)
"
SET REFUSED: ValueError "OAuthClientInformationFull" object has no field "dropped_redirect_uris"
EXTRA IN ANSWER: False
SDK model_config: {'url_preserve_empty_path': True}
```

  So `OAuthClientInformationFull` refuses an undeclared attribute and `model_validate` drops an
  unknown key silently. The only way to such a field would be an intervention in the
  registration answer on the auth path itself, for a field that no measured client reads. That
  is not in this plan, and it is not left out silently either: this paragraph is the reason.

**The measurement this closure rests on:** `06-08-MEASUREMENTS.md`, sections 6 to 8, the
refusal at `/authorize` with its wording, the three counter checks and the client side reason.
**The implementation:** plan 06-11 of phase 6.

**What was measured (plan 06-08, `06-08-MEASUREMENTS.md`):** against Cursor 3.2.16 and
connector 0.1.2, `POST /register` with Cursor's three URI body is answered `201` and the
record carries the two admissible addresses, exactly as the partial registration of a80af0a
intends. Cursor then sends `redirect_uri=cursor://anysphere.cursor-mcp/oauth/callback` to
`/authorize` and is answered `400` with the refusal page. No code, no token, no tool call.
Counter checks with the same client id: the registered `http://localhost:8787/callback` and
the same address on a different port both reach the consent page, so it is neither the
instance, nor the loopback port rule, nor the partial registration.

**The client side reason:** Cursor keeps its own three addresses after the `201` instead of
reading the registered ones out of the answer, so it cannot notice that one of them will be
refused. RFC 7591 3.2.1 asks the server to answer with the registered metadata, and this
server does.

**The decision that is open, and it is a decision and not a repair:**

1. Register the private-use scheme after all. Contradicts D-35 and its reason: on a desktop
   no application owns a scheme exclusively, so another program can claim it and receive the
   code.
2. Refuse the whole registration again. That was 0.1.1, and it kept Cursor out as well, only
   one endpoint earlier. It also keeps out clients that would have used an admissible
   address.
3. Make the dropped address impossible to miss for a client that does not compare, for
   example by answering the registration in a way that fails loudly, or by refusing the
   later `/authorize` with a message the client surfaces. Needs a look at what Cursor
   actually shows its user.
4. Leave it and keep pointing Cursor users at the app password path, which is what
   `docs/client-setup.md` says today.

**Why it is not urgent:** the app password path works for Cursor and is documented, the
server behaves as specified, and no other measured client is affected (Claude.ai, Claude
Desktop, Claude Code, ChatGPT and Open WebUI all publish admissible addresses). CLIENT-04
stays unchecked in REQUIREMENTS.md because its wording asks for a completed sign in.

## BL-15: The search note becomes false the day Findling ships (blocker for BL-01)

**Found:** 2026-09-04, while the owner asked whether the combination can be
advertised as a RAG system. Verified against the code and against STATE.md.

**What is wrong:** `src/mcp_connector/tools/search.py:47` carries

    SEARCH_NOTE = "matched on names and metadata; file contents are not indexed"

unconditionally in every `unified_search` answer. STATE.md records that under
phase 01: the note "steht in jeder Suchantwort, nicht nur bei null Treffern
(Pitfall 5, gegen NC 34 verifiziert)". The same claim sits a second time in
`_TERM_HINT` at `search.py:49-52`, "words that only appear inside a document are
not indexed", and that one is worse, because a client reads the tool description
before it ever calls the tool.

`unified_search` reads the provider list at runtime (D-08). The moment Findling is
installed it therefore returns real content hits, including text out of scanned
PDFs, while telling the model in the same payload that contents are not indexed.
The comment above the constant calls it "one sentence against a whole class of
wrong model statements (pitfall 5)". After Findling that very sentence causes one,
just in the other direction: an assistant that believes the note will distrust
correct hits or not use them at all.

**Not affected:** `src/mcp_connector/tools/files.py:43` keeps its own note.
`files_search` goes through WebDAV search, which does not consult the search
providers, so "matched on names only" stays true there. Do not "fix" it along the
way.

**Shape of the fix:** make both texts depend on what the provider list actually
offers, which `unified_search` already holds at runtime, instead of stating a
property of the instance as a constant. Cheapest honest version: keep the note when
no content provider answered and replace it when one did, so the sentence describes
the answer in hand rather than the installation in general. A test belongs with it,
because the whole value of the note is that a model can trust it.

**Why it blocks BL-01:** a banner that promises the retrieval layer for a RAG, on a
product whose own tool output says contents are not indexed, contradicts itself at
the only place a machine reads. Fix this first, then claim it.

## BL-16: Free exclusion tag `kein-ki`, fail-closed in every tool answer (before the ISV story is told again)

**Found:** 2026-09-04, while the owner asked whether exclusion tags and folder
exclusion exist in the paid tier. The ISV call dossier
(Desktop/ISV-Call-Dossier-2026-09-14.md) listed the tag in the "live" row of the
roadmap table, but the code has no trace of it: no tag check in the response
layer, nothing in `src/`, nothing in this backlog until now. The dossier row is
corrected to "planned" the same day; this entry is the plan.

**What:** a collaborative system tag named `kein-ki`. A file or folder carrying
it never appears in any tool answer: not in `unified_search`, not in file
listings, not in `prepare_context`, not as content. Subtree semantics: a tag on
a folder covers everything below it. Fail-closed: when the tag lookup cannot be
answered (systemtags app off, OCS error, timeout), the affected entries are
withheld, never shown; the degradation is named in the answer the same way the
other families do it.

**Where it sits in the open-core split:** free, deliberately. The dossier's rule
is that security boundaries are never paid (ACL recheck, OAuth, read-only gate,
this tag). Paid Connector Enterprise gets the governance on top: instance-wide
exclusions (tags/folders/group folders/groups), allow-mode instead of
block-mode, the blocked-access proof in the audit log, four-eyes approval for
policy changes. The free tag is what makes the enterprise pitch honest: the
mechanism exists for everyone, the paid tier is central control and evidence.

**Open question carried from the concept brief:** whether a simple folder
exclusion (an admin-set list, no policies) also belongs in the free core. Owner
leaned "useful" on 2026-09-04. The subtree semantics of the tag already cover
the single-folder case, so the answer may be "the tag on a folder IS the free
folder exclusion"; decide in the discuss of the phase that builds this.

**Why not now:** 0.1.12 is release-ready and waits for the ISV call of
2026-09-14; this is a feature, not a fix, and it changes tool answers, so it
belongs in a planned phase with its own tests (all paths: tagged file, tagged
parent, tag lookup failing, systemtags disabled).

**Cost note for the phase that takes it:** every tool family that returns file
paths needs the check, so the lookup must be batched (one OCS/DAV round trip
per answer, not per file) or the latency budget of D-xx-style answer times is
gone. Measure before fixing the design.
