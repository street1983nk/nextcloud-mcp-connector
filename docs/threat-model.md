<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Threat model

**Scope:** the connector as shipped, in both deployments (ExApp behind
AppAPI/HaRP, and `nc-mcp-oauth` standalone), against the attackers an
operator should actually expect. For every threat this page names the
mitigation **and the place that holds it**, a contract test, an occ command
or a documented switch, because a mitigation nothing checks is a sentence,
not a property. Where the answer is "this stays a risk", the page says so;
the residual risks stand in their own section at the end instead of being
spread out thin.

This page is the map. The deep dives it points into:
[privacy.md](privacy.md) for the data inventory and the lethal trifecta in
full, [exclusion.md](exclusion.md) for the `kein-ki` limits,
[hardening.md](hardening.md) for the order in which an operator applies the
boundaries, and SECURITY.md at the repository root for how to report what
this page missed.

## Assets

1. **User content in Nextcloud**: files, mail, calendar entries, notes, Deck
   cards, contacts, Tables rows, Talk history. The connector stores none of
   it; it reads per request and the asset stays where it was.
2. **Credentials**: per-connection Nextcloud app passwords (AES-GCM
   encrypted at rest, key held in Nextcloud's app configuration, outside the
   database file), OAuth refresh and access tokens and client secrets
   (stored as hashes only).
3. **The audit record**: once an operator switches it on, its integrity is
   itself worth attacking, because it is what an investigation will read.
4. **The instance's availability**: the connector must not be the cheapest
   way to fill a disk or hog the PHP workers.

## Trust boundaries

- **Assistant and MCP client ↔ connector.** Everything arriving here is
  untrusted, including well-formed OAuth requests: clients self-register
  (RFC 7591) and anyone can be one.
- **Connector ↔ Nextcloud.** The connector acts as the signed-in user and
  never holds rights of its own. Nextcloud's permission checks are the
  authorization decision; the connector deliberately has no second one.
- **Content authors ↔ the model.** A mail is written by somebody with no
  account on the instance, a Talk message by any co-user, a shared document
  by its collaborators. Whatever they wrote is handed to a language model
  that does not reliably separate data from instructions.
- **Identity provider ↔ connector** (token exchange path, off in the
  factory state): tokens presented here are untrusted until the signature,
  issuer, audience and claims have passed.

## Attackers, in rising order of position

| | Who | Position |
|---|-----|----------|
| A1 | An outsider who can send the user a mail | no account anywhere, puts text in front of the model through `mail_browse` |
| A2 | A co-user of the instance | can send Talk messages, share folders into the account, and set or unset collaborative tags |
| A3 | A malicious or compromised MCP client | holds a real OAuth grant a user once approved |
| A4 | The model itself, following injected instructions | holds whatever tools and rights the connection has |
| A5 | Whoever holds a stolen token or database copy | offline position, no live session |

**Out of scope, named instead of hidden:** root on the host (reads every
volume of every app, Nextcloud's own included), a compromised Nextcloud
server (the connector trusts its permission checks, there is no second
line behind them), and the assistant's provider (what the user's chosen
assistant reads legitimately leaves the instance; that is a data-protection
decision for the operator, see privacy.md, not a vulnerability).

## The threats and what stands against them

### Spoofing: who is calling?

- OAuth 2.1 with PKCE S256, audience-bound tokens, refresh rotation with
  reuse detection and immediate revocation. A replayed refresh token kills
  the chain it came from.
- Client secrets and all tokens are stored as hashes; a copy of
  `oauth.sqlite3` contains nothing replayable, and the app passwords in it
  are AES-GCM encrypted with a key that lives outside the file.
- In the standalone deployment no AppAPI header names the account, so the
  consent decision is confirmed by the OIDC single sign-on Nextcloud
  already trusts rather than by anything this app invents.
- Token exchange: a presented token is rejected before any lookup unless
  signature, issuer, audience and claims pass, and a rejected token
  contributes **no stored text**, because every value in an unverified
  token is text somebody chose freely (privacy.md spells this out).

### Tampering: can the record or the answers be bent?

- Every audit entry is hash chained to the one before it;
  `occ mcp_connector:audit:verify` walks the chains and names the first
  broken link. Deletions the app itself makes leave counted gap markers,
  so an explained gap and a manipulation stay distinguishable.
- Foreign values that end up in audit lines or output pass a printable
  filter with length limits, so a crafted actor name or client name cannot
  smuggle line breaks or direction-override characters in front of whoever
  reads the log.
- The markers this server writes into its own answers are stripped from
  foreign text, so a stranger cannot frame their text as this server's
  commentary.
- Held by: `tests/contract/test_audit_surface.py` and the audit tests, plus
  `occ mcp_connector:audit:verify` at run time.

### Repudiation: can anyone deny what happened?

- With the audit log on, every tool call is recorded with account, tool,
  time, calling client and outcome, never a parameter value or result.
  `occ mcp_connector:purge` deliberately does **not** empty the record,
  because the first command a cover-up reaches for must not be the one
  that works.

### Information disclosure: can the assistant see too much?

- The load-bearing wall: every request runs as the signed-in user against
  Nextcloud's own APIs. The integration test
  `tests/integration/test_content_hit_fidelity.py` measures that search
  hits respect exactly those rights.
- `kein-ki` removes tagged content from every tool, with its limits
  measured and documented in exclusion.md, and
  `occ mcp_connector:exclusion:check` verifies a live setup.
- `NC_MCP_FILES_ROOT` pins the file tools into one directory; parents stop
  existing for them.
- A refused call is answered with a fixed reason identifier, never with
  the text of an upstream error or a claim of a foreign token;
  `tests/contract/test_no_claim_leak.py` holds that against the source.
- What is deliberately **not** a disclosure boundary:
  `NC_MCP_DISABLED_TOOLS` hides tools, and `search`, `fetch` and
  `prepare_context` still reach the content of a hidden bundle. The README
  and hardening.md both carry that sentence so nobody buys a boundary that
  was never sold.

### Denial of service: can this app be used to exhaust the instance?

- The pre-authentication refusal path of the token exchange writes at most
  one audit row per rejection group per 5 minutes per worker; without that
  brake the size of the record would be decided from outside.
- The audit record stops growing at 100 MB and rows expire after the
  retention window, so an unread record cannot fill the volume.
- Downloads and uploads move in bounded chunks, `prepare_context` gives
  each source its own time budget, and a stalling provider is reported
  under `degraded` instead of stalling the answer.

### Elevation of privilege: can a grant become more than it was?

- There is no admin surface: the connector acts as one user, and a
  connection made by a restricted account stays restricted.
- No tool deletes, moves, renames, re-shares or changes permissions.
  `files_upload` remains create-only. When `NC_MCP_FILES_UPDATE` is
  enabled, `files_update` can replace existing UTF-8 text files only
  with a matching ETag. Contract tests guard conditional file writes,
  and `tests/contract/test_tool_classes.py` keeps every tool classified.
- Mail is strictly read only, asserted the same way: the family that adds
  the widest untrusted input adds no capability in return.

### Prompt injection, the one that spans all of the above

A1 through A4 meet here: untrusted content carries an instruction, the
model follows it, and the question is only what the instruction can reach.
No known method prevents the injection itself. This project bounds
the blast radius instead: the user's own rights as ceiling, no tool
for deleting, moving, renaming or re-sharing files, optional `files_update`
replacements protected by a matching ETag, the one direct outgoing channel
(`talk_send`) switchable off instance-wide, mail with deliberately no outgoing
channel, and provenance returned as structured fields. The full chain,
including the honest remainder about writes into shared containers and
conditional replacements, is in privacy.md; the operator's checklist
against it is hardening.md.

## Residual risks, in plain sentences

1. **Prompt injection is reduced, not removed.** A model with a live grant
   can still misuse read tools and create-only writes within the user's
   rights. When `NC_MCP_FILES_UPDATE` is enabled, it can also request
   ETag-protected replacement of existing UTF-8 text files.
2. **Writes into shared containers can expose content.** Created files and
   conditionally replaced file content may be visible to other people with
   access. Review which folders, boards and tables the connected accounts
   share, and disable `NC_MCP_FILES_UPDATE` when replacements are not needed.
3. **A tag above a share root does not protect the recipient's view.**
   Measured, documented, and testable per instance, but it stays the
   deployment mistake this design permits.
4. **The host is trusted.** Disk encryption and backup policy are the
   operator's layer; this app cannot add one below itself.
5. **No independent audit has verified any of this yet.** The tests named
   above are the project's own. The scans that run on every push (CodeQL,
   pip-audit, OpenSSF Scorecard) are external tools but not an audit.
   SECURITY.md is the channel for whoever proves a sentence of this page
   wrong.
