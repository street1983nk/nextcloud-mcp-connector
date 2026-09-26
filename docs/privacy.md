<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Privacy and data flow

**Scope:** what personal data this app stores, where it stores it, what it never
does, and the one data flow an operator has to account for before switching it on.
This is a technical description for administrators and data protection officers,
not a legal privacy statement for end users. The instance operator remains the
data controller and has to provide that statement themselves.

## The short version

This connector runs inside your own Nextcloud deployment. It sends no telemetry,
phones no home, and calls no third party of its own. Every tool call runs under
the identity of the signed in user, so an assistant never sees more than that user
sees in the web interface.

The one flow that leaves your control is the assistant itself: when a user connects
a hosted AI client such as Claude.ai or ChatGPT, the content the assistant reads
from Nextcloud is transmitted to that client's provider. The connector does not
send it on its own, but it is the door through which it leaves. See
[What leaves your control](#what-leaves-your-control).

## What the app stores

The app keeps two SQLite databases inside its own container. `oauth.sqlite3` holds
the OAuth 2.1 and credential state it needs to answer a request without a fresh sign
in every time. `audit.sqlite3` holds the audit log, the record of tool calls, and that
second file exists only if an administrator switched the record on, or switched it on
once before. Together the two hold these personal data:

| Data | Where | Form |
|------|-------|------|
| Nextcloud user id | `authorizations.nc_user`, `authorizations.nc_account_id`, `user_access.nc_user` | plain; `nc_user` is the login name the request runs as, `nc_account_id` the canonical account id that decides ownership and the pause switch |
| Nextcloud display name | `authorizations.nc_display_name` | plain; the name the instance had for the account when the connection was made, usually the person's own name. It is shown on the consent screen so the account is recognisable, and nothing is compared, owned or revoked by it. Empty when the instance sets no display name, and for connections made before this column existed |
| Nextcloud app password | `authorizations.app_password_enc` | encrypted at rest, AES-GCM with a fresh nonce per record, bound to its authorization id as additional authenticated data |
| OAuth authorization codes, refresh and access tokens | `auth_codes`, `refresh_tokens`, `access_tokens` | stored only as a hash, never in the clear |
| Client registrations | `clients` | the assistant apps and their redirect targets; the secret issued to a client is stored as a hash only, never in the clear |
| Access switch state | `user_access` | one row per paused account, a timestamp |
| Timestamps | across the tables | created, revoked, cleanup and expiry times |
| Nextcloud user id of a recorded call | `audit.sqlite3`, `entries.nc_user` | plain, and it is what the record is grouped by: one group of rows per account |
| Name of the called tool | `audit.sqlite3`, `entries.tool` | plain, the name of the tool the assistant asked for |
| Time of the call | `audit.sqlite3`, `entries.at` | Unix seconds, the moment the row was written |
| The assistant app that called | `audit.sqlite3`, `entries.client_id`, `entries.client_name`, `entries.auth_id` | the registered id of the client, its registered name cleaned and cut to 80 characters, and the id of the connection it used |
| The acting party of a delegated call | `audit.sqlite3`, `entries.actor` | for a call made with a token obtained through the token exchange path, the acting party of the identity provider's realm (the `azp` claim of that token), cleaned and cut the same way a registered client name is; empty for every other call; the word `unknown` in a row that records the log being switched or a gap being marked, because the administrator behind those cannot be determined |
| Outcome of the call | `audit.sqlite3`, `entries.outcome`, `entries.reason` | one of `ok`, `rejected`, `failed`, and where a call was refused a fixed identifier of the reason, never the sentence of an error |
| How long the call took | `audit.sqlite3`, `entries.duration_ms` | milliseconds |
| Names of the parameters | `audit.sqlite3`, `entries.params` | a sorted list of parameter names as JSON, never a value |
| For how many events one row stands | `audit.sqlite3`, `entries.removed` | a count; a marker says how many rows it replaces, a refused attempt how many attempts it stands for |
| What a recorded call never holds | `audit.sqlite3` | no network address, no user agent, no parameter value, no part of a result, no text of an error message |

### Refused sign in attempts of a connected identity provider

If the token exchange path is switched on, an assistant can present a token issued by your
own identity provider instead of one issued by this app. A token that does not meet the
rules is turned down before anything is looked up, so nothing of it belongs to an account of
this instance. Those attempts are recorded all the same, because an operator who cannot see
repeated rejections cannot tell a misconfigured client from somebody trying keys.

They are kept apart from the record of accounts: they stand in a chain of their own, named
`x:exchange`, with the row kind `refusal`, and `occ mcp_connector:audit:read --user=refusals`
is how an administrator reads them. `instance` and `refusals` are reserved words of the
`--user` option: the chain of an account that is really called by one of these names is read
by a call without `--user`.

Such a row holds four things and nothing else: the moment, the group of the rejection reason
(`exchange_malformed`, `exchange_key`, `exchange_issuer`, `exchange_claims`,
`exchange_account`, `exchange_failed`), the outcome `rejected`, and the number of attempts
that one row stands for.

It holds **no part of the token**: no token, no claim of one, no subject, no issuer, no
audience, no acting party, no key id, no network address. That is not a matter of taste. A
token that was turned down has not passed its signature check, so every value in it is text
somebody chose freely, and writing one into this file would let a stranger put their text in
front of whoever reads it.

One further property protects this file from the same stranger: at most one row is written
per rejection group per 5 minutes and per worker process, and the repetitions in between are
counted into the number that row carries. The path is reachable before anybody is signed in,
so without that brake the size of this file would be decided from outside.

The app does not store the content of your files, calendar, notes, deck cards or
contacts. It reads them per request, under the user's identity, and returns them in
the tool answer. Nothing of that content is written to the database.

The encryption key lives outside the database, in Nextcloud's own app configuration,
where the server stores it encrypted with its secret. A copy of the database file
alone therefore reveals no app password, and deleting the app data means deleting
both: see [Deletion and user control](#deletion-and-user-control).

## What the app never does

- No telemetry, no analytics, no usage tracking, no error reporting to a third party.
- No outbound request except to your own Nextcloud instance.
- No call to any AI provider, model host or external service from the connector
  itself. The assistant, not this app, talks to the model.
- No access beyond the signed in user's own permissions. A restricted user sees
  through the connector exactly what the web interface shows them, and no more.
- No sending of mail. Mail is read only in this app: there is no way to send a
  mail, to draft one, to move, flag or delete a message, and no attachment is
  downloaded. A contract test holds that sentence, see
  [The chain that mail closes](#the-chain-that-mail-closes).

## What leaves your control

The purpose of the connector is to let an AI assistant read from Nextcloud. Once a
user connects a hosted assistant, the data that assistant reads is transmitted to
the assistant's provider:

- Search results, file listings, calendar entries, notes, deck cards and contacts
  the assistant requests.
- With `prepare_context`, short excerpts of the top matching files, so the model
  has content and not only titles.

For hosted assistants such as Claude.ai or ChatGPT this is a transfer to a third
party, in most cases outside the EU. The connector transmits nothing on its own,
but an operator has to account for this flow:

- Have a legal basis for the transfer to the assistant's provider, for example a
  data processing agreement, and where applicable a transfer impact assessment for
  the third country.
- Tell your users that the content their assistant reads leaves Nextcloud for the
  assistant they chose, and let them decide which assistant to connect.
- A self hosted or EU based model (for example an assistant that speaks to a local
  or European LLM) keeps this flow inside your own control and is the way to avoid
  the third country transfer entirely.

### The chain that mail closes

Since mail can be read, this server has all three ingredients of one chain at the
same time, and an administrator deserves to read that sentence here rather than to
assemble it themselves:

1. **Private data.** Files, calendar entries, notes, contacts, Tables rows and now
   the mail of the signed in user, all of it readable through the read tools.
2. **Untrusted content.** A mail and a Talk message are written by somebody else.
   For a Talk message that somebody at least holds an account on this instance. For
   a mail they do not even need that: anybody with an internet connection can put
   text in front of the model, without ever being invited.
3. **An outgoing channel.** `talk_send`, the one tool of this server that puts a
   message directly in front of other people. It is the widest way out, not the only
   one: a create-only write can leave content in a shared container, and the
   countermeasures below treat the two separately.

Those three together are what Simon Willison calls the
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/):
access to private data, exposure to untrusted content, and the ability to
communicate outwards. This document uses his term instead of inventing one, because
the pattern is older than this app and an administrator may already know it by name.

**Why the three together are more than a list.** A language model does not reliably
separate data from instructions. A mail can carry a sentence addressed at the model
rather than at the reader, the model can follow it, and the answer can take the way
out. That class of attack is called prompt injection, and no known method prevents
it. The three ingredients are the condition under which a successful injection
becomes an exfiltration, and that is the difference between an annoyance and a data
protection incident.

**What this project puts against it**, each with the place it lives in:

- `talk_send` sits behind the administration switch `NC_MCP_TALK_SEND`. Set to off,
  no assistant can send a Talk message through this connector, for the whole
  instance, whatever an account is allowed to do in Talk itself. Reading
  conversations is not affected. That switch closes the one channel that can address
  other people directly; it does not close every conceivable way out, and the next
  bullet names the remainder rather than leaving it to be discovered.
- The create-only writes (`files_upload`, `deck_create_card`, `tables_create_row`)
  cannot address anyone, but a file, a card or a row can land in a folder, a board
  or a table that is shared with other people, and content written there is visible
  to everyone the container is shared with, activity notifications included. That is
  a narrower and less reliable way out than a message, and it is one. An operator
  who needs every path closed also reviews which folders, boards and tables the
  connected accounts share.
- **Mail is read only.** There is no way in this app to send a mail, to create a
  draft, to move, flag or delete a message, and the attachment route of the Mail app
  is never called. The new family adds reach into private data and untrusted
  content, and it deliberately adds no second way out.
- There are no destructive write paths at all. Nothing is deleted, overwritten,
  moved or re-shared, and the write tools that exist can only create.
- The assistant never sees more than the signed in user. Every request runs under
  that identity, so Nextcloud's own permissions decide what an injection could
  reach at most.
- The markers this server writes into its own answers are removed from foreign text
  before it is passed on, so a stranger cannot frame their own text as if this
  server had commented on it.

**And the honest remainder.** None of these makes prompt injection impossible. What
they do is keep the outgoing channel switchable and the write surface small. That is
also the difference between two kinds of sentence in this document. "Mail is read
only" is a statement about a capability. The promise underneath it is narrower and
checkable: there is no code path in this app that sends, drafts, moves, flags or
deletes a mail, and a contract test asserts it against the source of the two mail
modules on every run. An operator who wants the direct messaging channel closed sets
`NC_MCP_TALK_SEND` to off; one who needs every way out closed also reviews what the
connected accounts share, because a create-only write into a shared container
remains a path outwards that no switch of this app removes.

## Deletion and user control

- A user pauses or resumes their own access, and disconnects any connected
  assistant, on the connector's own `/connections` page. Disconnecting hands the
  app password back to Nextcloud, so the entry also disappears from the user's
  Devices and sessions in Nextcloud.
- A user can revoke access from the Nextcloud side at any time, under Settings,
  Security, Devices and sessions.
- Removing the app in the Nextcloud interface is not a deletion of its data, and on
  Nextcloud 34 that interface does not offer the app at all: measured on 34.0.2, no
  external app appears in the app list. The removal path that list used for an
  external app only disables it, so the container stops while the data volume stays,
  and so do the Nextcloud app passwords the app created for each connection, because
  no uninstall path of the server touches them. Emptying the instance is an explicit
  act of the administrator, and the order of the two commands is part of it:

  1. `occ mcp_connector:purge --force` hands every Nextcloud app password of this
     app back to Nextcloud, empties the seven tables of its OAuth database and
     deletes its encryption key.
  2. `occ app_api:app:unregister mcp_connector --rm-data` then removes the app
     together with its data volume.

  The second command must not run first. It deletes the volume, and with it the
  only record of which app password belongs to which connection, so those
  credentials would stay valid in Nextcloud with nothing left that knows about
  them. The administration runbook `uninstall.md` in this directory spells out both
  steps, how to check what is gone afterwards, and how to see what stays.

  **The audit log survives the purge.** `occ mcp_connector:purge --force` does not
  empty `audit.sqlite3`. That is a decision and not an oversight: a record that one
  command removes records nothing, because that command is the first thing anybody
  reaches for who wants an entry gone. The file therefore stays in the data volume
  after the purge, with every row it held. The second command is the one that takes
  it: `--rm-data` deletes the volume, and the record lies in it. `uninstall.md` has
  the check that reads the row count out of the volume, so what stays is a number an
  administrator can see rather than a sentence on this page.

## Retention

Tokens and codes carry their own expiry and are swept after it. A revoked or ended
authorization returns its app password to Nextcloud and is cleared. Beyond the active
connections a user has chosen to keep, `oauth.sqlite3` holds no personal data that
outlives them.

The audit log in `audit.sqlite3` is kept longer, and three things delete from it
without anybody asking for it:

1. **The retention window.** A row is kept for 180 days by default. The default is a
   default and not a promise for every instance: `NC_MCP_AUDIT_RETENTION_DAYS` moves
   it, up or down, and the number in force is the one this instance was deployed with.
2. **The upper bound.** The record stops growing at 100 MB. Above that size the oldest
   rows give way, so a record nobody looked at for a year cannot fill the volume of
   this app.
3. **The account.** An account removed in Nextcloud takes its own rows with it. Every
   row belongs to the account the call ran for, so this is one group of rows and not a
   search through the file. The app asks Nextcloud whether an account is still there
   after that account has been silent in the record for 30 days.

The first two of these three take the rows of the `x:exchange` chain exactly as they take the
rows of an account: refused attempts expire after the same window and give way to the same
upper bound. The third does not apply to them, because there is no account behind that chain
to ask Nextcloud about. Only one chain is spared by all three, and it is the one that records
what happened to the record itself.

In all three cases a marker stays where the rows were, and the marker says how many
rows are missing. That is why a later check of the record reports an explained gap
instead of a break: the rows are gone, the count of them is not, and the difference
between a deletion this app made and an entry somebody changed afterwards stays
readable.

Pausing access or disconnecting an assistant deletes nothing from the record. Both are
events of today and the record is about what happened, so the rows stay where they
are.
