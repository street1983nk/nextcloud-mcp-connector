English | [Deutsch](hardening.de.md) | [Français](hardening.fr.md)

# Running the connector on confidential data

Every boundary this server offers, on one page, in the order an administrator
should apply them. Each section names the mechanism, what it protects against,
and, where it matters, what it does **not** protect against. The detailed
documents are linked at the end of each section.

## 1. The boundary that counts: Nextcloud permissions

Every request runs with the rights of the signed-in user, against Nextcloud's
own APIs, so the assistant can never see more than the person who connected
it. There is no second permission model in this server that could drift. This
is the load-bearing wall: everything below narrows the surface further, but
nothing below replaces it.

Practical consequence: for an automation (n8n and the like), connect an
account that holds only the rights the job needs, not a personal account and
never an admin account.

## 2. Exclude what the assistant must never see: the kein-ki tag

Tag a folder or file with the collaborative tag `kein-ki` and the assistant no
longer sees it or anything below it, in every tool, search and context bundle.

- Verify the setup before trusting it:
  `php occ mcp_connector:exclusion:check --admin=<uid>`
- The most important limit: a tag **above the root of a share** does not
  protect the shared folder for the recipient. Tag the folder you share.
- All limits, with the findings they rest on: [exclusion.md](exclusion.md).

## 3. Narrow the file surface: NC_MCP_FILES_ROOT

With `NC_MCP_FILES_ROOT=/Documents/AI`, that directory becomes `/` for the
file tools and no file tool can reach its parent folders. Use it when the
assistant only needs one working area; everything else stops being reachable
through the file tools at all.

## 4. Close the outgoing channel: NC_MCP_TALK_SEND

This server holds private data, takes in untrusted content, and has exactly
one outgoing channel, `talk_send`. Those three together are the lethal
trifecta, and removing one ingredient is the strongest move available:
switching `talk_send` off for the whole instance (Settings, Administration,
Security) closes the channel while reading stays untouched. Mail is read-only
by design and adds no way out of its own.

If the assistant does not need to post into Talk, switch it off and this
whole class of exfiltration ends at the instance boundary.

## 5. What switching bundles off does NOT do

`NC_MCP_DISABLED_TOOLS` hides tools so that clients with small models or hard
tool limits see fewer of them. It is **not an access control**: `search`,
`fetch` and `prepare_context` still reach the content of a switched-off
bundle. The boundary is and stays section 1, 2 and 3. This is stated in the
README as well, and it is worth repeating because it is the single most
tempting misreading of this server's configuration.

## 6. Prompt injection: the honest remainder

A mail or a Talk message is written by somebody else, a document may be too,
and a language model does not reliably separate data from instructions. There
is no known complete defence. What this server does instead is bound the
damage:

- no tool deletes, moves, renames or changes shares or
  permissions; `files_upload` remains create-only. When
  `NC_MCP_FILES_UPDATE` is enabled, `files_update` can replace an
  existing UTF-8 text file only with a matching ETag; contract tests
  require conditional headers on file PUT routes,
- content is returned with its origin as structured fields, so the client can
  tell where text came from,
- the outgoing channel can be closed instance-wide (section 4).

What remains, with every countermeasure spelled out: [privacy.md](privacy.md).
On the client side, keep the assistant's write confirmations switched on if
the client offers them.

## 7. Switch the audit log on

Off by default, one switch in the admin settings of this app. With it on,
every tool call is written down with the account, the tool, the time, the
calling app and the outcome, and never a parameter value or any part of a
result. Entries are hash chained; `occ mcp_connector:audit:read` reads them
and `occ mcp_connector:audit:verify` names the first broken link if anything
was tampered with. On confidential data this is the difference between
"we think nothing happened" and "we can show what happened".

## 8. Local does not mean the model is local

Nothing is indexed, cached or copied by this server, and no content leaves
the machines you operate **except** to the assistant that asked. A cloud
assistant receives the excerpts its tools fetch. If that is not acceptable
for your data, run a local model; the connector cannot make a remote model
local.

## 9. Before production: try to break in

Run these once, as a second user and as the connected user, and keep the
results with your deployment notes:

1. `php occ mcp_connector:exclusion:check --admin=<uid>` reports no finding.
2. A `kein-ki`-tagged file is not reachable through `files_search`,
   `unified_search`, `search`, `fetch` or `prepare_context`.
3. A file shared **into** the account from a folder whose tag sits above the
   share root: confirm it is reachable, then tag the shared folder itself if
   it must not be (section 2).
4. A file the connected user cannot read in Nextcloud is not reachable
   through any tool.
5. With `NC_MCP_TALK_SEND` off, `talk_send` refuses instance-wide.

Section 2's share case is the one real deployments get wrong; test it with
your own folder structure, not just on paper.
