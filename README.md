**English** | [Deutsch](README.de.md) | [Français](README.fr.md)

# MCP Connector for Nextcloud

A curated MCP server that connects your Nextcloud (files, calendar, notes, Deck, contacts,
Tables, Talk and Mail) to AI assistants such as Claude, Cursor, ChatGPT or your own agents.
Installed as a Nextcloud ExApp, it is its own OAuth 2.1 authorization server as well.

**Findling + Nextcloud MCP Connector = the retrieval layer for your own RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) makes the content of your documents
searchable, scans included. The connector hands those hits to any MCP client, with exactly
the rights of the asking user; measured in
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
You bring the model, and no content leaves your server.

## What it does

- 21 tools across nine app families: files, calendar, notes, Deck, contacts, Tables, Talk,
  Mail and cloud wide search
- OAuth 2.1 to the MCP authorization specification: dynamic client registration, PKCE S256,
  audience bound tokens, refresh rotation with reuse detection and immediate revocation.
  Claude.ai and ChatGPT are given one URL and never see a password or an app password
- Every request runs with the rights of the signed in user, so Nextcloud permissions apply
  unchanged and the assistant never sees more than you do
- Per user management: every account pauses or resumes its own access and disconnects a single
  assistant, on this app's connections page under Settings, Security, MCP Connector
- `prepare_context` bundles a search, the coming week of events, the waiting Talk conversations
  and the unread mail counts into one call, each source with its own time budget
- A deliberately small tool set, so this server fits next to your other MCP servers even in
  clients with a hard tool limit
- No cron, no indexing, no telemetry, no copy of your data, and no credential is ever logged

## What this server cannot do

- No deleting: no tool issues a DELETE against files, events, notes, cards or contacts
- No overwriting: writes are create-only, and `files_upload` refuses an existing path with a
  clear error instead of replacing it
- No moving and no renaming, no share changes and no permission changes
- Mail is strictly read only: no sending, no draft, no move, no flag, no delete, and no
  attachment download
- No admin access: the server acts as one user and inherits exactly that user's permissions
- No full text search inside file contents unless a search app such as Findling is installed

That is a design constraint and not a promise of good behaviour: a contract test reads the
modules and fails on the first destructive call,
[tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py).

## Tools

**read** means the tool only reads, **create-only** means it can create new objects but never
modifies or removes existing ones. The table is not maintained by hand: a contract test reads
the live registry and fails if a name or a level disagrees with it.

| Tool | Permission | What it does |
|------|------------|--------------|
| `files_search` | read | Files and folders by name via WebDAV search; contents are not indexed |
| `files_list` | read | The direct children of a folder, with size and modification time |
| `files_read` | read | The content of one file |
| `files_upload` | create-only | A new file; an existing path is refused, never overwritten |
| `calendar_list_events` | read | Events in an explicit time range, with an explicit time zone |
| `calendar_create_event` | create-only | A new event; existing events are never changed |
| `notes_search` | read | Notes by title and content, via the Nextcloud notes search provider |
| `notes_read` | read | One note |
| `notes_create` | create-only | A new note; existing notes are never changed |
| `deck_browse` | read | Deck boards, stacks and cards |
| `deck_create_card` | create-only | A new card in a stack; existing cards are never changed |
| `tables_browse` | read | Tables: the tables, the columns of one, or its rows |
| `tables_create_row` | create-only | A row addressed by column titles; existing rows are never changed |
| `talk_browse` | read | Talk conversations and the history of one; reading leaves no trace |
| `talk_send` | create-only | One message into a conversation; never edited or deleted, switchable off instance wide |
| `mail_browse` | read | Mail accounts, their mailboxes and message envelopes; strictly read only |
| `contacts_search` | read | Address book contacts |
| `unified_search` | read | The Nextcloud unified search across providers, permission aware |
| `prepare_context` | read | Files, notes, cards, the next week of events, waiting Talk conversations and unread mail counts in one call |
| `search` | read | OpenAI compatible search entry point, delegates to unified search |
| `fetch` | read | OpenAI compatible fetch, resolves an id to a file, note, card, event, mail, Talk message or table |

`search` and `fetch` exist because the ChatGPT connector profile requires exactly these two
names and schemas. They are thin wrappers over the tools above, not a second implementation.

An answer of `unified_search`, with both honest cases in it: a hit whose id the read tools
resolve, and a provider whose entries stay a URL instead of an invented id. A provider that
fails or stalls is named under `degraded`, so a partial answer is visibly partial. Notes,
Deck, Tables, Talk and Mail are optional apps; the tool list stays the same everywhere and a
missing app is answered in one sentence, never with an empty result.

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}]}
```

## Security

This server holds **private data**, it takes in **untrusted content** (a mail or a Talk message
is written by somebody else, and for a mail that somebody needs no account on your instance),
and it has an **outgoing channel**, `talk_send`. Those three together are what Simon Willison
calls the [lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), and a
language model does not reliably separate data from instructions. So `talk_send` sits behind
the administration switch `NC_MCP_TALK_SEND`, which closes the outgoing channel for the whole
instance while reading stays untouched, and Mail adds reach with deliberately no way out of its
own. Neither makes prompt injection impossible. The long form, with every countermeasure and
the honest remainder, is in [docs/privacy.md](docs/privacy.md). The switches sit under
Settings, Administration, Security:

![Admin settings of the MCP Connector](docs/screenshots/admin-settings.png)

## Installation

Listed in the Nextcloud App Store as
[MCP Connector](https://apps.nextcloud.com/apps/mcp_connector) and installed as an ExApp:
enable AppAPI, register a deploy daemon, then deploy and enable the app. Nextcloud 32 to 34.
On 34.0.3 the apps management interface does this for you, on earlier versions occ is the
reliable path. The walkthrough with the exact commands and the pitfalls that actually happen:
[docs/exapp-install.md](docs/exapp-install.md).

[![MCP Connector in the Nextcloud App Store](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

## Clients

Claude.ai and ChatGPT connect over OAuth with one URL. Claude Desktop, Claude Code, Cursor and
other local clients run the same server over stdio, with a Nextcloud app password:

```bash
uv tool install nextcloud-mcp-connector

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

The same server speaks Streamable HTTP for remote clients, on `POST /mcp`, where
`NC_MCP_ALLOWED_HOSTS` is required in practice. Setup step by step, every environment variable
and the three errors that actually happen: [docs/client-setup.md](docs/client-setup.md). OAuth
for administrators: [docs/oauth-setup.md](docs/oauth-setup.md). Automation platforms are
clients too, with one OAuth connection per person: [docs/n8n-setup.md](docs/n8n-setup.md).

![Connections page with two connected assistants](docs/screenshots/connections-page.png)

## Privacy

Every call goes to your Nextcloud and returns: nothing runs in the background, no result is
cached, no index is kept. In the HTTP modes the credentials travel per request and are never
stored. Questions users ask: [docs/faq.md](docs/faq.md).

## Enterprise

The audit log is part of this app and not of an add-on. With it on, every tool call is written
down with the account it ran for, the tool, the time, the calling app and the outcome, and
never a parameter value or any part of a result. It is off by default, an administrator
switches it on in the admin settings of this app, and the entries are read with
`occ mcp_connector:audit:read`. Every entry is hash chained to the one before it, and
`occ mcp_connector:audit:verify` walks the chains and names the first place one of them is
broken.

Planned, but not available yet, are group policies and sign in through the identity provider
your organisation already runs.

Request a quote: admin@infranode.dev

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` starts nothing and needs nothing. `uv run pytest -m matrix` starts the HTTP
server as a subprocess, `uv run pytest -m integration` needs the local test Nextcloud from
`compose.test.yml`.

App id, package names and repository name are frozen, see
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Licence

AGPL-3.0-or-later, see [LICENSE](LICENSE). Donations: [PayPal](https://www.paypal.com/paypalme/KhaledCherifDev)
and [Stripe](https://buy.stripe.com/3cI14n2ke6AbdTPfG22VG00).
