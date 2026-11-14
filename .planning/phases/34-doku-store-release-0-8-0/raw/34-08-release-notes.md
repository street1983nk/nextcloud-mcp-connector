## MCP Connector 0.8.0

### New

- `files_create_folder` in the `files` bundle: creates one folder, or with `parents=true` the missing parent folders as well, at most 10 new folders per call. Same boundaries as `files_upload` (`kein-ki` exclusion, `NC_MCP_FILES_ROOT` sandbox, Nextcloud decides permissions). Requested in #44.
- New bundle `tasks` with `tasks_search`, `tasks_read` and `tasks_create`, switchable off through `NC_MCP_DISABLED_TOOLS`. Requested in #32.
- `tasks_search` covers own and shared task lists, open tasks by default.
- `tasks_read` returns one task with its direct subtasks and its ETag.
- `tasks_create` is create-only and writes into a list others can see only when that list is named.
- `fetch` reads `task:` ids.

### Opt-in: changing existing tasks

- `tasks_complete`, `tasks_update` and `tasks_move` behind the admin switch `NC_MCP_TASKS_UPDATE` ("Allow changing existing tasks"), off by default.
- Each works only with the ETag from `tasks_read`; a stale ETag is refused.
- Recurring tasks are refused.

### Not included

- No deleting of tasks. No tool deletes anything.

### Fixed

- `unified_search` and `search` no longer show the name of the person who shared a task list in a task hit.

### Changed

- The switch `NC_MCP_FILES_UPDATE` carries one label everywhere: "Allow editing existing text files".

### Admin note

- On a running installation, change a switch with `occ app_api:app:config:set mcp_connector tasks_update --value on --update-only`, then disable and enable the app.

### Requirements

- Nextcloud 32 to 35 with AppAPI.
- Image `ghcr.io/street1983nk/mcp_connector:0.8.0` for linux/amd64 and linux/arm64.

Full list: CHANGELOG.md
