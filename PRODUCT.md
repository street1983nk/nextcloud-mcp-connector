# Product

<!-- impeccable:product-schema 1 -->

> Inferred from README.md, CLAUDE.md, .planning/PROJECT.md and the code (as of 2026-11-04). Statements with a source are stated that way in the repository. The inferred statements without a source were confirmed by the owner on 2026-11-04.

## Platform

web

## Users

- **People who connect an AI assistant to their own Nextcloud:** Claude, ChatGPT, Cursor, n8n or their own agent, acting as the signed-in user (source: README, info.xml summary).
- **Nextcloud admins** who install the ExApp from the App Store, decide which tool bundles and optional features (files_update, token exchange, audit log) are on, and answer to their organisation for what an assistant can see (source: README, PROJECT.md).
- v1 target group: developers and self-hosters; from phase 2 on German public authorities and companies with data protection requirements (sovereign workplace, openDesk) (source: PROJECT.md).
- the most important human moment in the product is the consent screen, where a user decides whether a client may act as them; most of the remaining usage happens inside the assistant, not in any UI of this app.

## Product Purpose

The most accessible and cleanest MCP connection for Nextcloud: installable with one click, spec-conformant OAuth instead of app passwords, and the assistant never sees more than the signed-in user; since v1.7 it can see less, because anything tagged `kein-ki` is invisible to it (core value, source: PROJECT.md).

success means a user connects an assistant in under a minute without ever handing it a password, and an admin can explain to a data protection officer exactly what the assistant can and cannot do.

## Positioning

- Curated and deliberately small tool set (23 tools across nine app families) instead of a tool flood, so it fits next to other MCP servers within client tool limits (source: README, PROJECT.md Out of Scope).
- Nothing destructive by construction, enforced by a contract test; mail strictly read-only (source: README).
- The connector is its own OAuth 2.1 authorization server (DCR, PKCE S256, CIMD, refresh rotation) (source: README).
- MCP-only on purpose, not a competing agent platform to Nextcloud Assistant or context_agent (source: PROJECT.md Out of Scope).
- Together with Findling, the retrieval layer for your own RAG; no content leaves the server (source: README).

## Operating Context

- Runs as a Nextcloud ExApp via AppAPI and HaRP, Nextcloud 32 to 35; also a standalone deployment with its own identity provider since 0.2.0 (source: CLAUDE.md, info.xml).
- Human-facing surfaces: the server-rendered OAuth pages (handoff, waiting, consent, result, errors, token exchange) and the per-user connections page under Settings, Security, MCP Connector; plus a Declarative Settings signpost that Nextcloud renders (source: `src/mcp_connector/exapp/ui/`, `exapp/settings_form.py`).
- Configuration is through deploy environment variables and `occ` commands, not a settings UI (source: README).

## Capabilities and Constraints

- Tools for files, calendar, notes, Deck, contacts, Tables, Talk, mail (read only) and unified search; `prepare_context` bundles several sources (source: README).
- No delete, no unconditional overwrite, no move, no share or permission change, no admin access (source: README).
- The connector's own HTML pages are deliberately not styled like Nextcloud (threat T-03-23 in `exapp/ui/layout.py`), so users can tell them apart from Nextcloud's own password prompt.
- The own pages ship English only in v1; German reference wording exists in a UI spec, not in code (source: `exapp/ui/strings.py`).
- Strict CSP on own pages: no script, no external asset, one nonce style block (source: `layout.py`).
- Code and README in English, project communication in German (source: CLAUDE.md).

## Brand Commitments

- Name "MCP Connector for Nextcloud" (wordmark in `strings.py`), app id `mcp_connector`.
- Copy rules: every error says what happened and what to do next, no OAuth error codes, no blame, no exclamation mark, no emoji, never "click here" (source: `strings.py`).
- Store texts are short fact lists; releases and store submissions only with owner approval (source: PROJECT.md).
- No em or en dashes in prose (source: CLAUDE.md).

## Evidence on Hand

- Contract and integration tests named in the README as proof: `tests/contract/test_no_destructive_calls.py`, `tests/integration/test_content_hit_fidelity.py`.
- Evidence documents under `docs/` (for example `docs/nc35-evidence.md`, `docs/exchange-evidence.md`, `docs/exclusion.md`).
- Do not fabricate: customer names, usage numbers, enterprise pricing or roadmap promises beyond what README and info.xml state. Enterprise internals stay out of the repo (owner decision D-07, source: PROJECT.md).

## Product Principles

Derived from core value and decisions:

1. Never more than the user: every request runs with exactly the signed-in user's rights.
2. Safe by construction, not by promise: destructive calls are impossible, and that is tested.
3. Curated over complete: every tool must earn its place in the client's tool budget.
4. Fail closed and say so: a check that cannot be answered withholds data and reports one degraded entry.
5. Visibly ours where trust is decided: the consent flow never imitates Nextcloud.

## Accessibility & Inclusion

target WCAG 2.1 AA (BITV relevant for the public-sector target group). Evidence in code: 44 px minimum targets, a 3 px focus ring that is never removed, icons always paired with text and hidden from screen readers, initial focus on the consent heading so a stray Enter cannot grant (source: `layout.py`, `icons.py`). Open: the own pages are light only and English only.
