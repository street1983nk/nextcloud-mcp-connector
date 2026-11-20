## MCP Connector 0.9.0

### New

- `profile_fields_browse`: an optional read-only tool for the Nextcloud app Profile Fields, off by default.
- Levels `me`, `definitions`, `values` and `search`.
- If the app Profile Fields is missing, disabled or not enabled for any of the account's groups, the tool says so and explains how to fix it.

### Permissions

- Every account reads its own visible values with `me`.
- The field catalogue, the values of other accounts and the exact search use routes the Profile Fields app reserves for administrators; the app checks that itself.
- Only OCS GET requests with the permissions of the connected account; nothing is created, changed or deleted.
- A UID of `.` or `..` is refused before any request is sent.
- The audit log records `level`, `limit` and `offset` only.

### Admin note

- Switch "Allow reading Profile Fields" in Administration settings, Security, MCP Connector, or `NC_MCP_PROFILE_FIELDS_READ`.
- A change takes effect after you disable and enable the app again.
- 27 tools by default, 28 with this switch.

### Search note

- The search (`unified_search`, `search`, `prepare_context`) reaches the search provider of Profile Fields with or without the switch and follows the permissions of that app.

### Tested

- CI installs Profile Fields from the app store and proves the tool live through a real MCP client on Nextcloud 34: 27 tools without the switch, 28 with it, no foreign value for an account without administrator rights.
- Measured on Nextcloud 34 with Profile Fields 4.0.0. On Nextcloud 35 Profile Fields is only available as a nightly; there the tool reports that the app is missing.

### Changed

- Tool descriptions and error hints state preconditions and errors instead of assurances. Behaviour is unchanged; the guarantees stay in the README and the docs. Reported in issue #53 by Excauboi.
- The store description is short now and links to the README of its language for the details.

### Requirements

- Nextcloud 32 to 35 with AppAPI.
- The Profile Fields app for `profile_fields_browse`.
- Image `ghcr.io/street1983nk/mcp_connector:0.9.0` for linux/amd64 and linux/arm64.

### Credits

- Profile Fields support by Vitor Mattos (vitormattos) in #49.

Full list: CHANGELOG.md
