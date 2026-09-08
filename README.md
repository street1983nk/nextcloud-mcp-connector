**English** | [Deutsch](README.de.md) | [Français](README.fr.md)

# MCP Connector for Nextcloud

A curated MCP server that connects your Nextcloud (files, calendar, notes, deck, contacts, Tables,
Talk and Mail) to AI assistants such as Claude, Cursor, ChatGPT or your own agents.

**Findling + Nextcloud MCP Connector = the retrieval layer for your own RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) makes the content of your documents
searchable, scans included, and 1.0.0 adds semantic search. The connector hands those hits
to any MCP client, with exactly the rights of the asking user. You bring the model, and no
content leaves your server. Measured, not promised:
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py)
proves a content hit reaches its owner and never another account.


**This server can never delete, overwrite or re-share anything.**

That sentence is the design constraint, not a promise of good behaviour. The server does not
implement a single destructive call: no DELETE, no MOVE, no overwrite, no share modification. Write
tools are create-only, and a name collision is answered with a clear refusal instead of a silent
overwrite.

Two more properties follow from the same idea:

- **The assistant never sees more than you do.** Every request runs with your own Nextcloud
  credentials, so Nextcloud permissions apply unchanged.
- **A deliberately small tool set.** The 21 tools are curated so that this server fits next to
  your other MCP servers, even in clients with a hard tool limit.

License: AGPL-3.0-or-later. App id, package names and repository name are frozen, see
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Status

Version 0.1.12. The app is listed in the Nextcloud App Store and installable as a Nextcloud ExApp
through AppAPI. What is in place today, and where each of these claims is written down:

- All 21 tools of the v1 set are implemented, and the tool table below is no longer maintained
  by hand: a contract test reads the live tool registry and fails if a name or a permission
  level in the table disagrees with it.
- OAuth 2.1 sign in is verified end to end against the two hosted connectors it was built for,
  Claude.ai and ChatGPT, including dynamic client registration and refresh rotation. The walk
  and the measurements are in [docs/oauth-setup.md](docs/oauth-setup.md).
- Per user management: every account pauses or resumes its own MCP access and disconnects any
  single connected assistant on this app's own connections page, which Nextcloud links under
  Settings, Security, MCP Connector.
- `prepare_context` bundles a search, the coming week of events, the Talk conversations that are
  waiting and the unread mail counts into one call, so one question costs one round trip instead
  of several. Every source has its own time budget and its own `degraded` entry, so a slow one
  shortens the bundle and never the answer. Three caps keep the size predictable: at most three
  conversations, a chat preview cut at 200 bytes, and at most three mail accounts. Mail arrives
  as a counter, which is the point of it: the standard bundle carries no subject and no mail
  content at all.

Since 0.1.4: Tables and Talk. An assistant looks through the tables of the account and adds a
row to one of them by column titles, reads the conversations of the account and the history of
one of them, and sends one message into a conversation. Reading a conversation leaves no trace:
no read marker is moved, no notification is acknowledged and the online status stays as it was.
Talk is the one family in which an assistant can put something in front of other people, so an
administrator can switch the sending off for the whole instance, and a message that mentions
everybody, a whole group or a whole team at once is never sent.

Step by step setup for Claude Desktop, Claude Code and remote HTTP clients, including the three
errors that actually happen: **[docs/client-setup.md](docs/client-setup.md)**.

Automation platforms are clients too. n8n reaches all of these tools through its MCP Client
node, with one OAuth connection per person instead of one shared administrator credential, and
Nextcloud's own webhook app gives the trigger side without any community node:
**[docs/n8n-setup.md](docs/n8n-setup.md)**.

### OAuth 2.1

Installed as a Nextcloud ExApp, this server is also its own OAuth 2.1 authorization server, to
the MCP authorization specification: dynamic client registration, PKCE S256, audience bound
tokens, refresh rotation with reuse detection and immediate revocation. A client such as
Claude.ai or ChatGPT is given one URL, signs the user in on Nextcloud's own pages and never
sees a password or an app password. The connection appears under Settings, Security, Devices
and sessions and can be ended there.

Since 0.1.3: an assistant can also identify itself
by the address of a metadata document it publishes itself, instead of registering here first.
That is the way the current MCP specification prefers, and it is the way Claude Code connects.
Both ways run next to each other, and an administrator can switch either of them off.

What an administrator has to set, what a user enters, and the measurements behind both:
**[docs/oauth-setup.md](docs/oauth-setup.md)**.

## Get it from the Nextcloud App Store

The app is listed as **MCP Connector**:
**[apps.nextcloud.com/apps/mcp_connector](https://apps.nextcloud.com/apps/mcp_connector)**

[![MCP Connector in the Nextcloud App Store](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

It installs as a Nextcloud ExApp: enable AppAPI, register a deploy daemon, then deploy and
enable the app. On **Nextcloud 34.0.3** the apps management interface does this for you: the
app list shows the ExApp with its deploy daemon, the install button of an ExApp reads "Deploy
and enable", and "Remove" sits in the row actions of a disabled ExApp (measured on 34.0.3.2
on 2026-08-20). On 34.0.2 and earlier the interface lists no ExApp at all, and occ is the
reliable path on every version. The complete walkthrough, including the exact occ commands and
the pitfalls that actually happen, is in
**[docs/exapp-install.md](docs/exapp-install.md)**.

After the install, the app registers its settings under Settings, Administration, Security:

![Admin settings of the MCP Connector](docs/screenshots/admin-settings.png)

Every account manages its own connections on the app's connections page, which Nextcloud links
under Settings, Security, MCP Connector:

![Connections page with two connected assistants](docs/screenshots/connections-page.png)

## FAQ

**My administrator installed this app. Can I switch it off for myself?**

Yes, and you do not need your administrator for it. Nothing runs in the background: the
connector only ever acts on a request from an assistant you connected yourself, and there is no
cron, no indexing and no telemetry. Your own account has a switch on this app's connections
page, which Nextcloud links under Settings, Security, MCP Connector, and every connected
assistant can be disconnected on its own, which hands its Nextcloud app password back to
Nextcloud.

The full answer, including the boundary between what this app controls and what the provider of
your assistant decides: **[docs/faq.md](docs/faq.md)**.

## Quickstart (stdio)

You need a Nextcloud app password, not your login password. Create one in Nextcloud under
Settings, Security, Devices and sessions.

```bash
uv tool install nextcloud-mcp-connector   # or: uv run nc-mcp inside a checkout

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

Client configuration, for example for Claude Desktop or Cursor:

```json
{
  "mcpServers": {
    "nextcloud": {
      "command": "nc-mcp",
      "env": {
        "NC_MCP_URL": "https://cloud.example.com",
        "NC_MCP_USER": "alice",
        "NC_MCP_APP_PASSWORD": "xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
      }
    }
  }
}
```

## HTTP mode

The same server also speaks Streamable HTTP for remote clients:

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_ALLOWED_HOSTS=mcp.example.com
uv run uvicorn mcp_connector.entry_http:app --host 127.0.0.1 --port 8765
```

The MCP endpoint is `POST /mcp`, and `GET /health` answers `{"status":"ok","version":"..."}`
without authentication. One endpoint serves both protocol generations: clients on the current
spec and clients built on MCP SDK 1.x are routed by the protocol version of their request, and a
restart cannot interrupt a conversation because the server keeps no session state.

Credentials are not read from the environment in this mode. They travel per request in the
`Authorization` header (Basic, user and app password) and are forwarded unchanged to Nextcloud,
which authenticates them. The server never treats the header as an identity claim of its own, and
it stores nothing, so one deployment can serve several users without a credential store.

For single user deployments a static bearer token is available instead: set
`NC_MCP_STATIC_BEARER`, and the Nextcloud account is taken from the environment like in stdio
mode. The two HTTP modes are mutually exclusive.

`NC_MCP_ALLOWED_HOSTS` is not optional in practice. Without it, the transport layer only accepts
`Host: localhost` and `Host: 127.0.0.1` and answers every other request with `421 Misdirected
Request` before any MCP code runs. Note that this is the `Host` header of incoming requests, not
the bind address: `--host 0.0.0.0` allows nobody in.

## Environment variables

| Variable | Mode | Required | Purpose |
|----------|------|----------|---------|
| `NC_MCP_URL` | all | yes | Base URL of your Nextcloud, including a subpath if you use one |
| `NC_MCP_USER` | stdio, static bearer | yes | Nextcloud user id |
| `NC_MCP_APP_PASSWORD` | stdio, static bearer | yes | App password from Settings, Security, Devices and sessions |
| `NC_MCP_ALLOWED_HOSTS` | HTTP | yes in practice | Comma separated `Host` header allow list of this server; a port wildcard is added per name |
| `NC_MCP_STATIC_BEARER` | HTTP | no | Static bearer token for single user deployments; without it, clients authenticate per request |
| `NC_MCP_DISABLE_DNS_REBINDING_PROTECTION` | HTTP | no | Set to `true` only behind a proxy that controls the `Host` header |
| `NC_MCP_PUBLIC_URL` | static bearer, ExApp | yes for OAuth | Public URL of this server. In the ExApp mode it is the issuer of the authorization server and the resource of the protected resource document, so OAuth does not work without it |
| `NC_MCP_OAUTH_DCR` | ExApp | no | Dynamic client registration, on unless switched off |
| `NC_MCP_OAUTH_CIMD` | ExApp | no | A client may identify itself by the address of a metadata document it publishes itself, on unless switched off; switching self registration off closes this way with it |
| `NC_MCP_OAUTH_ALLOWLIST_ONLY` | ExApp | no | Only listed clients may authorize; an empty list then closes the door for everyone |
| `NC_MCP_OAUTH_ALLOWED_CLIENTS` | ExApp | no | Comma separated client ids or redirect URIs, read only when the allowlist is on |
| `NC_MCP_TALK_SEND` | all | no | The outgoing Talk channel of this app, on unless it is set to off. With it off no assistant can send a Talk message through this connector, whatever an account is allowed to do in Talk itself; reading conversations and their history is not affected. In the ExApp mode the administration form writes it |

No credential is ever logged, in any mode.

## Tools

Permission levels: **read** means the tool only reads, **create-only** means the tool can create
new objects but can never modify or remove existing ones.

| Tool | Permission | What it does |
|------|------------|--------------|
| `files_search` | read | Search files and folders by name via WebDAV search; contents are not indexed |
| `files_list` | read | List the direct children of a folder, with sizes and modification times |
| `files_read` | read | Read the content of a single file |
| `files_upload` | create-only | Upload a new file; an existing path is refused, never overwritten |
| `calendar_list_events` | read | List events in an explicit time range, with an explicit time zone |
| `calendar_create_event` | create-only | Create a new event; existing events are never changed |
| `notes_search` | read | Find notes by title and content via the Nextcloud notes search provider |
| `notes_read` | read | Read a single note |
| `notes_create` | create-only | Create a new note; existing notes are never changed |
| `deck_browse` | read | Browse Deck boards, stacks and cards |
| `deck_create_card` | create-only | Create a new card in a stack; existing cards are never changed |
| `tables_browse` | read | Browse Tables: the tables, the columns of one table, or its rows |
| `tables_create_row` | create-only | Add a row addressed by column titles; existing rows are never changed |
| `talk_browse` | read | Browse Talk: the conversations of this account, or the history of one of them |
| `talk_send` | create-only | Send one message into a conversation; a message is never edited or deleted, and an administrator can switch sending off for the whole instance |
| `mail_browse` | read | Browse Mail: the accounts of this user, the mailboxes of one, or the message envelopes of one; strictly read only, there is no way to send, draft, move, flag or delete a mail |
| `contacts_search` | read | Search address book contacts |
| `unified_search` | read | Query the Nextcloud unified search across providers, permission aware |
| `prepare_context` | read | Bundle matching files, notes and cards with the next week of events, the waiting Talk conversations and the unread mail counts for one question |
| `search` | read | OpenAI compatible search entry point, delegates to unified search |
| `fetch` | read | OpenAI compatible fetch entry point, resolves an id to a file, note, card, event, mail, Talk message or table |

`search` and `fetch` exist because the ChatGPT connector profile requires exactly these two names
and schemas. They are thin wrappers over the tools above, not a second implementation.

### Files: what the search actually matches

`files_search` uses WebDAV search, which matches **names**, not file contents. A word that only
appears inside a document produces no hit, and that is the behaviour of the protocol, not a defect
of this server. Every search answer therefore carries the same note:

```json
{"query":"budget","folder":"/","count":1,"items":[{"path":"/Docs/budget-2026.md","name":"budget-2026.md","kind":"file","size":2048,"content_type":"text/markdown","modified":"Thu, 14 Aug 2026 10:00:00 GMT","id":"file:4711"}],"note":"matched on names only; contents are not indexed"}
```

Full text search would need a separately installed Nextcloud app, so the honest answer is the note
above rather than a silent empty result.

`files_list` returns the direct children of a folder, folders first and then names. The folder
itself is never part of its own listing, and a path that points at a file gets an explanation
instead of an empty list.

### Long lists: cursor handles instead of sessions

A list that had to stop early says so and hands out a handle:

```json
{"items": ["..."], "truncated": true, "next": "eyJmIjoiLyIsIm8iOjI1LCJxIjoiYnVkZ2V0In0"}
```

Pass that value back as the `cursor` parameter to continue. The handle is base64url of compact
JSON and holds the whole position, so the server keeps no session: a handle still works after the
server was restarted, and it works against a different process of the same server. It is not
signed on purpose, because it carries no secret and no permission. The credentials come from the
auth channel on every single call, so an edited handle can only page through the caller's own data
differently. A handle from another query is refused instead of quietly returning the wrong page.

### Calendar times

CalDAV is the one place where a small time mistake produces a confidently wrong answer, so the
calendar tools are explicit about it:

- `start` and `end` are required and must carry a zone, for example `2026-09-01T00:00:00+02:00`
  or `2026-09-01T00:00:00Z`. A value without a zone is refused instead of guessed.
- Recurring events are expanded by Nextcloud itself, so every instance comes back as an absolute
  time. The optional `timezone` parameter (an IANA name such as `Europe/Berlin`) changes only how
  the answer is written, never which events it contains.
- All day events are dates without a time and are marked with `all_day`. Their end date is
  exclusive, as RFC 5545 defines it: an event on 24 October ends on 25 October.
- `calendar_create_event` reads the created event back once and reports the times the server
  stored, not the ones it was asked for.

### Contacts

`contacts_search` is read only, and it stays that way in this version: there is no CardDAV write
path at all.

- The search term is matched by Nextcloud itself against the full name and the mail addresses of a
  card, case and accent insensitive. A phone number is returned but not searched for.
- Every address book of the account is asked at the same time. One that fails is named under
  `degraded`, so a partial answer is visibly partial.
- The two collections Nextcloud generates for every account are left out: the account directory of
  the instance (`z-server-generated--system`, shown as "Accounts") and the "recently contacted"
  list. Neither is an address book the user keeps, and a name search should not hand out the
  directory of a whole organisation as a side effect.
- An account without an address book of its own gets an error that names
  `occ dav:create-addressbook <user> contacts`, never an empty result: "no address book" and "no
  matching contact" are different answers.

### Deck

Deck is one browse tool with a level, not one tool per level:

```json
{"level":"cards","count":2,"results":[{"id":"card:2:11:101","title":"Deck-Client bauen","stack":"To Do","url":"https://cloud.example.org/index.php/apps/deck/card/101"}]}
```

- `deck_browse(level="boards")` lists the boards with `can_edit`, `level="stacks"` needs a
  `board_id` and reports how many cards a stack holds, `level="cards"` returns the cards
  themselves. An invalid level is rejected by the schema, and a missing `board_id` names the
  parameter instead of guessing one.
- `level="cards"` costs exactly **one** HTTP request per board, because Nextcloud already sends
  the cards inside the stacks answer. A test counts the requests, against the mock and against a
  real instance.
- A card id is the canonical long form `card:<board>:<stack>:<card>`, which addresses the card
  through the public Deck API without a lookup.
- `deck_create_card` only creates. There is no update, no delete and no board or stack creation
  anywhere in the Deck code path. A title longer than 255 characters or a due date that is not
  ISO-8601 is refused before the request, and an account whose Nextcloud forbids board creation is
  checked against the board's own permissions, so a read-only board is explained instead of
  answered with a 403.

### Mail

Mail is one browse tool with three levels and one strict property: it reads, and there is no
second thing it can do.

- `mail_browse(level="accounts")` lists the mail accounts of the signed in user with their
  address, `level="mailboxes"` needs an `account_id` and lists the mailboxes of that account
  with their unread count and their IMAP role, and `level="messages"` needs a `mailbox_id` and
  returns the message envelopes, newest first. Neither id is ever guessed: there is no default
  account and no "first mailbox", because a right looking answer about somebody else's mail is
  the most expensive mistake this family can make. A window is 20 envelopes unless a larger one
  is asked for, at most 50, and a list that had to stop hands back a `next` handle like every
  other long list of this server.
- **The full text of one message** travels through the existing `fetch`, with the id
  `mail:<databaseId>` that every envelope carries, and not through a second tool. The body is
  always converted to text, whether the message was written in HTML or not, and it is cut at
  32 KiB with a marker that promises no continuation, because a mail has no offset to continue
  from. Beside the text, and deliberately never inside it, `metadata` carries what Nextcloud
  itself knows about the sender: `sender_trusted`, `dkim`, `signature`, `encrypted`,
  `phishing_warning` and `phishing_checks`. `dkim` of `unchecked` means "no verdict was
  computed", not "the signature is invalid", and the same word covers a mail that carries no
  signature at all: neither of them is a verified sender, and both lead to the same next step.
- **The filter grammar**, exactly as it is tested. Conditions are written `type:value` and
  separated by spaces:

  | Type | Takes | Example |
  |------|-------|---------|
  | `is:` | `unread`, `read`, `starred`, `answered`, `important` | `is:unread` |
  | `not:` | the same five values | `not:answered` |
  | `from:` | an address or a part of one | `from:billing@example.org` |
  | `subject:` | a word of the subject | `subject:invoice` |
  | `tags:` | the **numeric** tag id, never the IMAP label | `tags:1` |
  | `start:` | **Unix seconds** | `start:1756000000` |
  | `end:` | **Unix seconds** | `end:1756600000` |

  Two rules of the Mail app's own parser are part of the grammar, because a caller cannot guess
  them. The filter is split on **spaces**, so a value that contains one has to be percent
  encoded: `subject:invoice%20May` is the only spelling that filters on both words, and
  `subject:invoice May` filters on `invoice` and drops `May` without saying so. And every token
  is split at its **first** colon with the rest falling away, so a colon inside a value has to be
  written `%3A`. `start:` and `end:` are compared against an integer column, so they take Unix
  seconds and nothing else: `start:2026-08-01` filters every message away instead of failing, and
  `start:2026-08-01T10:00:00Z` would be cut at its first colon on top of that, which is why an
  ISO timestamp is refused here.

  A type this connector does not know is **refused**, not dropped. The Mail app drops it in
  silence and answers with the unfiltered list, so `is:ungelesen` would come back looking like a
  correct filter result and a model has no way to see the difference. An error costs one round
  trip, a right looking wrong answer costs the conversation.
- **What is deliberately missing.** There is no `body:` filter: it is the one condition that
  leaves the database and searches over IMAP, so it costs a round trip to the mail server of the
  user per call. Attachments are never downloaded. And there is no write path of any kind, see
  the next section.

### Cloud wide search

`unified_search` asks every search provider the instance offers, at the same time:

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","subline":"in Dokumente","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}],"note":"matched on names and metadata; file contents are not indexed","degraded":[{"provider":"search-deck-card-board","reason":"The provider did not answer within 15 seconds."}]}
```

- The provider list comes from Nextcloud on every call and is never hardcoded, because it follows
  the installed apps. An app enabled a minute ago is searchable without a restart.
- Every provider gets its own timeout. One that fails or stalls is named under `degraded` with a
  reason, so a partial answer is always visibly partial, never a silently shorter list.
- Permissions are Nextcloud's job: each provider runs as the authenticated user, and this server
  keeps no index and caches no result.
- Hits from Files, Notes and Deck carry an id the read tools understand. Everything else gets a
  `url:` id and `resolvable: false`, because an invented id would resolve to the wrong object.
  Deck's provider only reports a card id, so its short `card:<cardId>` form is marked the same way.
- `providers` narrows the fan-out to a comma separated subset, for example `files,notes`. A name
  the instance does not know is reported under `degraded` instead of silently ignored.
- `limit` is per provider and is capped again by Nextcloud itself. If a provider paginates, its
  cursor comes back under `cursors`.

### ChatGPT connector profile

`search` and `fetch` are the two names the OpenAI connector looks for. Their parameters are
`query` and `id`, their field names are fixed, and both are the only tools of this server that
ship an output schema, because ChatGPT reads the payload as structured content:

```json
{"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","text":"in Dokumente"}]}
```

```json
{"id":"file:4711","title":"Budget 2026.md","text":"# Budget 2026 ...","url":"https://cloud.example.org/index.php/f/4711","metadata":{"kind":"file","path":"/Dokumente/Budget 2026.md","content_type":"text/markdown"}}
```

- `search` adds no second search. It calls `unified_search` and renames the fields, so both tools
  answer the same question the same way.
- Every hit carries a non-empty, absolute URL on the configured instance. ChatGPT creates citation
  metadata only while `url` is a non-empty string, so an empty one would silently drop the source.
- `fetch` resolves the seven id kinds the read tools understand: `file:<fileid>` (looked up by a
  single WebDAV search on `oc:fileid`), `note:<id>`, `card:<board>:<stack>:<card>` including the
  short `card:<cardId>` form from the Deck search provider, `event:<calendar>:<object>`,
  `mail:<databaseId>` (the full text of one message, cut at 32 KiB with the cut marked),
  `message:<token>:<messageId>` (one single Talk message, read over the same context route that
  leaves no trace; the message has to be readable in that conversation, otherwise the answer is a
  refusal and never a neighbouring message) and `table:<tableId>` (the title, the row count and
  the first rows of a table; a view is not a table, so a view stays a URL).
- A hit from Mail stays a `url:` id even though the full text route exists, and that is a
  measurement rather than an omission: a Mail search entry carries a deep link with an RFC
  message id, and resolving that to the `databaseId` this route needs is untested. An id that is
  right most of the time is an answer about somebody else's mail the rest of the time.
- A `url:` id is answered honestly: this server never requests a URL that came out of a search
  entry, and it says so instead of inventing content. An unknown prefix is refused with the list of
  the valid ones, because resolving a chat message as a note is worse than an error.
- A long file is cut at the same limit as `files_read`. The cut is marked inside `text` and again
  in `metadata`, with the offset to continue from.

### Optional apps

Notes, Deck, Tables, Talk and Mail are optional Nextcloud apps, ten tools in total. The tool list is
the same everywhere: it never depends on which apps an instance has, so it stays cacheable and
predictable for every client. If an app is missing, the tool says so in one sentence and names an
alternative, for example "The Notes app is not installed on this Nextcloud.", "The Tables app is not
enabled on this Nextcloud.", "The Talk app is not available on this Nextcloud." or "The Mail app is
not available on this Nextcloud." Calendars and contacts need no app at all: CalDAV and CardDAV are
part of the Nextcloud core.

Mail is detected differently from the other four, and the reason is not ours: the Mail app
publishes no capabilities entry, so there is nothing in the capabilities document to look for.
This server therefore asks the navigation of the signed in user, which lists the apps that account
may actually open. That costs one additional request per cache window, and only on a Mail call.

## What this server cannot do

- **No deleting.** No tool issues a DELETE against files, events, notes, cards or contacts.
- **No overwriting.** Writes are create-only. `files_upload` refuses an existing target path with a
  clear error instead of replacing it, and the create tools never touch an existing object.
- **No moving or renaming.** MOVE and COPY are not implemented.
- **No share changes.** The server neither creates, modifies nor removes shares, and it never
  changes permissions.
- **No admin access.** The server acts as one user with an app password and inherits exactly that
  user's permissions.
- **No full text search inside file contents** unless the Nextcloud Full text search app is
  installed and configured. Without it, file search matches names and metadata.
- **No background jobs, no sync, no local copy of your data.** Every call goes to your Nextcloud
  and returns.
- **No sending mail.** No tool sends a mail, creates a draft, moves a message, sets or clears a
  flag or deletes anything, and the attachment route of the Mail app is never called. What holds
  that sentence is a contract test: it reads the two mail modules of this server and asserts that
  not one writing call exists in them, against a list of the routes the Mail app offers for
  exactly those actions.

### The chain this server has, and the switch that breaks it

Reading mail completes a combination worth naming rather than describing. This server has access
to **private data** (files, calendar, notes, contacts, Tables and now mail), it takes in
**untrusted content** (a mail and a Talk message are written by somebody else, and for a mail that
somebody needs no account on your instance at all), and it has an **outgoing channel**: `talk_send`,
the one tool that puts a message directly in front of other people, and behind it the create-only
writes, which can leave a file, a card or a row in a container that is shared with others. Those
three together are what Simon Willison calls the
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), and a language model
does not reliably separate data from instructions, so a mail can carry a sentence meant for the
model and the answer can take the way out.

Two things stand against it here. `talk_send` sits behind the administration switch
`NC_MCP_TALK_SEND`, which closes the direct messaging channel for the whole instance while reading
stays untouched; the create-only writes stay open, so an operator who needs every path closed also
reviews which folders, boards and tables the connected accounts share. And **mail is read only**:
this family adds reach, and deliberately no way out of its own. Neither makes prompt injection
impossible. The long form, with every countermeasure and the honest remainder, is in
[docs/privacy.md](docs/privacy.md), section "The chain that mail closes".

## Known limitations

Things that are not defects but will surprise you once. Each of them is a deliberate trade, and
each one is visible in the answer the tool gives rather than hidden behind an empty result.

| Limitation | What you see | What to do |
|------------|--------------|------------|
| **Search matches names, not contents** | Every search answer carries `"note":"matched on names only; contents are not indexed"` | Install and configure the Nextcloud Full text search app, or search by file name |
| **An account created with `occ user:add` has no calendar** | `calendar_list_events` returns an error that names the missing calendar | `occ dav:create-calendar <user> personal`, or log in to Nextcloud once through the web UI, which creates it |
| **The same is true for the address book** | `contacts_search` names the way out instead of returning nothing | `occ dav:create-addressbook <user> contacts` |
| **Notes, Deck, Tables, Talk and Mail are optional apps** | The tools stay in `tools/list` everywhere and answer "The Notes app is not installed on this Nextcloud.", "The Tables app is not enabled on this Nextcloud.", "The Talk app is not available on this Nextcloud." or "The Mail app is not available on this Nextcloud." | Install the app, or ignore those ten tools |
| **Two mails sent in the same second can fall across a page boundary** | The paging of the Mail app compares the send time strictly, so of two messages carrying the same second the second one is missing from the next page, for good | Ask for a larger `limit`, which makes the boundary rarer. The limit belongs to the app, and this server does not correct it quietly: a correction of our own would be a second truth about the order, and two callers with the same window would see different lists |
| **No full text search inside mail bodies** | There is no `body:` filter, and the grammar refuses it like any other unknown type | Use the search of the Mail app itself. `body:` exists there, but it leaves the database and searches over IMAP, which costs a round trip to the user's mail server per call |
| **A mailbox that has never been synchronised, and a mail server that cannot be reached** | Both answer as an error whose sentence points at the account in the Mail app, not at Nextcloud | Open the account in the Mail app once and let it synchronise, or fix the account there. Neither case is a Nextcloud problem, and neither is answered with an empty list |
| **Nothing can be deleted or overwritten** | `files_upload` refuses an existing path with a conflict, and there is no update or delete tool at all | Pick another name. This is the design constraint, not a missing feature |
| **No session, so no server side paging state** | A long list hands back a `next` handle you pass in again | Nothing. The handle survives a restart, which is the point |
| **Calendars need an explicit time window with a zone** | A `start` or `end` without a zone is refused | Send `2026-09-01T00:00:00+02:00` or `...Z`. A guessed zone is a confidently wrong answer |
| **One IP for many users triggers the brute force guard** | `429` after a wrong app password, for everyone behind the same deployment | Wait and use a correct app password; see the troubleshooting section in the client setup |
| **Not every assistant app can finish an OAuth sign in** | An app that asks to be returned to an address of its own scheme, Cursor for example, is refused at the sign in, and the page names the way in that does work | Use an app password on the same `/exapps/mcp_connector/mcp` endpoint; the ExApp mode accepts either, see [docs/client-setup.md](docs/client-setup.md) |

Phase 2 made the server installable as a Nextcloud ExApp through AppAPI, with every request
running under the calling user's own identity. Three documents record it and the two spikes it
depended on:

- [docs/exapp-install.md](docs/exapp-install.md): installing the app as an ExApp on the HaRP
  topology, the evidence, the known pitfalls, and the Nextcloud AIO handoff to phase 5.
- [docs/spike-discovery.md](docs/spike-discovery.md): the discovery decision for the phase 3
  OAuth topology, with the measured matrix and the reverse proxy fallback.
- [docs/spike-dav.md](docs/spike-dav.md): the DAV impersonation result, which is that all six
  API families run under one impersonation mode, so there is no per family provider split.

## Enterprise

The audit log is part of this app and not of an add-on. With it on, every tool call is written
down with the account it ran for, the tool, the time, the calling app and the outcome, and never
a parameter value or any part of a result. It is off by default, an administrator switches it on
in the admin settings of this app, and the entries are read with
`occ mcp_connector:audit:read`. Every entry is hash chained to the one before it, and
`occ mcp_connector:audit:verify` walks the chains and names the first place one of them is
broken.

Two things are planned as a commercial add-on: group policies, and sign in through the identity
provider your organisation already runs. Happy to support your organisation with evaluation and
deployment: admin@infranode.dev

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` starts nothing and needs nothing. The two heavier layers are opt-in:

- `uv run pytest -m matrix` starts the HTTP server as a subprocess and checks that a current
  client and a client on MCP SDK 1.29 are both served from the same endpoint, and that the
  conversation survives a restart. It needs no Nextcloud.
- `uv run pytest -m integration` needs the local test Nextcloud from `compose.test.yml`.

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE).
