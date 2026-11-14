<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Conference demo runbook

**Scope:** one demo of this connector against a running Nextcloud, in four stations plus an
opener and a closer, and everything a second person needs to run it without knowing this
repository. Every claim below carries the command or the file it was checked with. Nothing
here is new machinery: the demo is a script around `scripts/oauth_flow_check.py`,
`scripts/acceptance_all_tools.py`, the connections page of the app and a real MCP client.

## Where this stands

The demo was walked end to end once, on 2026-08-20, and the run is written down step by
step with its measured durations in
`.planning/phases/06-h-rtung-eigennachweise-und-conference-reife/06-10-MEASUREMENTS.md`.
That file is the reason the times in this runbook are numbers and not hopes.

| What | Value | Checked with |
|------|-------|--------------|
| Nextcloud | 34.0.3 (`34.0.3.2`) | `occ status`, not the Docker tag |
| AppAPI | 34.0.0 | `occ app:list` |
| Connector | 0.1.2, image digest `sha256:3ba4a2ce1921...` | `occ app_api:app:list`, `docker image inspect` |
| Topology | `compose.exapp.yml`, project `nc-mcp-exapp`, HaRP, reachable at `http://127.0.0.1:8081` | `docker compose -p nc-mcp-exapp -f compose.exapp.yml ps` |
| MCP client | Claude Code 2.1.233 | `claude --version` |
| Demo account | `alice`, created by `scripts/bootstrap_exapp.sh` | `occ user:list` |

Three facts this demo rests on, each measured in its own plan of this phase and not
rehearsed here:

- The Nextcloud app store interface lists this ExApp on 34.0.3 and its install button reads
  `Deploy and enable`. Measured in `06-07-MEASUREMENTS.md`. On 34.0.2 and earlier the store
  interface showed no ExApp at all, which is an upstream bug that was fixed in 34.0.3.
- Claude Code identifies itself by the URL of its own client metadata document, with no
  registration call, and reaches a tool call with real content. Measured in
  `06-09-MEASUREMENTS.md`.
- The loopback port of that client changed in every one of three consecutive runs, which is
  why the server compares everything about a loopback return address except its port.
  Measured in `06-09-MEASUREMENTS.md`.

The instance also carries two older connections of the account `jane`, from the store
release proof of phase 5. They are not used on stage and nothing in this runbook touches
them: the connections page shows the connections of the account that is signed in, and that
account is `alice` here. Use a throwaway instance and a throwaway account for the demo, for
the plain reason that the screen is public while the demo runs.

## What is shown

Four stations, in this order, each one carrying one of the four claims this project makes.

| Station | Claim it carries |
|---------|------------------|
| An assistant connects | Authorization is the specification, not an app password pasted into a config file |
| The assistant reads real content | The assistant sees exactly what the signed in account sees, and no more |
| The account pauses and resumes access | The person whose data it is holds the switch, not the administrator |
| The account disconnects one app | Access ends at the moment of the click, and the app notices |

Two more steps frame them: an opener that walks the whole authorization flow in printed
steps, and a closer that calls every tool of the curated set once. The closer is where the
fourth claim of the talk becomes visible, the one about not being able to destroy anything:
the tool list has no delete, and the upload tool refuses a path that exists. It has no move
either as long as `NC_MCP_TASKS_UPDATE` stays at its default, off; since 0.8.0 that switch
adds `tasks_move`, which moves one task with its subtasks and only with a fresh ETag, and
nothing ever deletes a task.

## One time setup

The topology is three commands. `HP_SHARED_KEY` is the value that decides whether the setup
is a first run or a restart, and the two cases are not interchangeable: HaRP and the deploy
daemon registration have to carry the same key, so a fresh key on a restart locks the
already registered app out and every heartbeat answers 503.

**First run, no topology yet.** Generate the key:

```
cd <this repository>
export HP_SHARED_KEY="$(openssl rand -hex 32)"
docker compose -p nc-mcp-exapp -f compose.exapp.yml up -d --wait
bash scripts/bootstrap_exapp.sh
set -a && . ./.env.exapp && set +a
```

**Restart of a topology that was bootstrapped before.** Read the key back out of
`.env.exapp`, which is where the bootstrap wrote it, and do not generate a new one:

```
cd <this repository>
export HP_SHARED_KEY="$(sed -n 's/^HP_SHARED_KEY=//p' .env.exapp | tr -d '\r')"
docker compose -p nc-mcp-exapp -f compose.exapp.yml up -d --wait
set -a && . ./.env.exapp && set +a
```

If the topology is already up and nothing was restarted, the last line is the whole setup:
the environment of the shell that runs the scripts has to carry the contents of
`.env.exapp`.

**The client, once.** The server is added to a project local configuration and not to the
presenter's global server list, so the demo cannot disturb whatever else that client
already talks to:

```
mkdir -p ~/demo-ncmcp && cd ~/demo-ncmcp
claude mcp add --transport http ncmcp \
    http://127.0.0.1:8081/exapps/mcp_connector/mcp -s local
cat > mcp.json <<'JSON'
{"mcpServers":{"ncmcp":{"type":"http","url":"http://127.0.0.1:8081/exapps/mcp_connector/mcp"}}}
JSON
```

The `mcp.json` next to it is for the non interactive tool calls further down, which run with
`--strict-mcp-config` so that no other server of that machine can answer them.

Two addresses to have open in the browser before the talk starts, signed in as the demo
account:

```
http://127.0.0.1:8081/settings/apps                                  the app list
http://127.0.0.1:8081/exapps/mcp_connector/connections               the connections page
```

## The script (run of show)

Total 4:40 on stage. The machine time is called out separately per step, because it is the
part that cannot be talked faster, and because it is the number the recorded run measured.

### Step 0, the whole flow in printed steps (35 s on stage, 5 s machine)

**Say:** "Before anything visual, here is the entire authorization flow, one line per step,
against the running instance."

**Do:**

```
uv run --no-sync python scripts/oauth_flow_check.py \
    http://127.0.0.1:8081/exapps/mcp_connector
```

**Must be visible:** seven steps with their real status codes, in order, the `401` of the
MCP route first and the tool call last, then the closing line
`all steps answered as the specification and this deployment require`. Step 7 reports
`tools=20`, which is the number this server publishes, and step 5 below expects the same
number. The script ends the connection it created itself, so the
instance is where it was before.

### Step 1, an assistant connects (60 s on stage, 6 s machine)

**Say:** "This is a real assistant, and it has never seen this Nextcloud. Watch what it
does not ask me for: it never asks for a password, and I never paste a token."

**Do, in the demo directory:**

```
claude mcp login ncmcp
```

**Must be visible, in this order:**

1. The client opens the browser by itself. It sends no registration call: its `client_id`
   is the URL of its own metadata document.
2. The Nextcloud sign in page. Nextcloud authenticates the account, not this app.
3. The consent page of this app, with the line `Client ID host: claude.ai` and the note
   `Comes back to this computer` for the loopback return address.
4. After the approval, the terminal says
   `Authenticated with "ncmcp". Its tools are now available in Claude Code.`

**Watch out:** this command needs a real terminal. It checks whether its input is one and
stops with `stdin isn't a terminal` otherwise, which is only a problem for an automated run
and never on stage.

### Step 2, the assistant reads real content (40 s on stage, 30 s machine)

**Say:** "It is connected as me, and only as me."

**Do:**

```
claude -p "Call the ncmcp tool files_list for the path / and then print, verbatim, the JSON the tool returned. Do nothing else." \
    --strict-mcp-config --mcp-config mcp.json \
    --allowedTools "mcp__ncmcp__files_list"
```

**Must be visible:** the JSON of the tool, with the real entries of that account's files
home, not a tool description and not an empty list. On the demo fixture two of the entries
are the marker files the bootstrap creates, so a wrong account is obvious at a glance.

### Step 3, the account pauses and resumes access (60 s on stage, 25 s machine)

**Say:** "Now the part nobody else has. This is not the administrator's page. This is mine."

**Do, in the browser:** open the connections page, then press `Pause access`.

```
http://127.0.0.1:8081/exapps/mcp_connector/connections
```

**Must be visible on the page:** the callout `Access is paused` and the sentence
`MCP access is paused. Connected apps are refused, nothing is disconnected.` The connected
app is still listed, because nothing was disconnected.

**Do, in the terminal:** ask the client what it can still reach.

```
claude mcp list
```

**Must be visible:** the line for the server flips from `Connected`, with a check mark in front of it, to
`! Needs authentication`. On the wire the MCP route answered `403` with the body

```
{"error": "access_disabled", "error_description": "MCP access is switched off for this
Nextcloud account. The owner of the account can switch it back on on the connector's
connections page ..."}
```

so the refusal names its reason and does not pretend to be an empty result.

**Do, in the browser:** press `Turn access back on`, then run `claude mcp list` again.

**Must be visible:** the page states `MCP access is on. Connected apps can use your
Nextcloud.` and the client is back to `Connected` with its check mark, and to a `200` on the wire. Nothing was
reconnected and no token was reissued: it is the same connection, the same row on the page
and the same token.

**Why the probe here is `claude mcp list` and not the question from step 2.** Measured on
2026-08-20: after a `403` this client marks the server as unauthenticated in its own
bookkeeping, and a non interactive `claude -p` run then refuses to try at all, even after
access is switched back on. `claude mcp list` re-probes the server and recovers at once.
The connector recovers immediately either way, which the wire shows, but a demo must not
depend on a client's memory of a refusal. If a full question with content is wanted after
the resume, run `claude mcp list` first and then repeat the step 2 command in a fresh
interactive session.

### Step 4, the account disconnects one app (45 s on stage, 11 s machine)

**Say:** "And this is the end of it. One click, and it is over for that app."

**Do, in the browser:** press `Disconnect` in the row of the connected app, then confirm on
the page that follows.

**Must be visible on the page:** the confirmation page names the app and says
`{app} loses access to your Nextcloud immediately. Nothing in your Nextcloud is deleted or
changed.` After the confirmation the list says `Disconnected`, the row is gone, and the app
is named in the callout as the one that lost access.

**Do, in the terminal:** `claude mcp list` once more.

**Must be visible:** the server is `! Needs authentication` again. Three things happened on
the wire in that one probe, and they are worth naming if somebody asks: the MCP route
answered `401` with the `WWW-Authenticate` pointer to the protected resource document, the
client then re-read the two discovery documents, and its attempt to refresh answered `400`,
because the refresh token went with the connection. The assistant is not broken, it is
logged out, and it can connect again with step 1.

### Step 5, the whole set, and what is missing from it (40 s on stage, 5 s machine)

**Say:** "Twenty tools, and here is what is not among them."

**Do:**

```
set -a && . ./.env.exapp && set +a
NC_MCP_USER="$NC_MCP_TEST_USER" \
NC_MCP_APP_PASSWORD="$NC_MCP_TEST_APP_PASSWORD" \
    uv run --no-sync python scripts/acceptance_all_tools.py
```

**Must be visible:** the acceptance matrix, with `OK` or `SKIP` on every one of the twenty
tools it calls. On the bootstrap topology exactly two are `SKIP`, the writes that need an
object this server cannot create: `deck_create_card` wants a Deck stack, `tables_create_row`
a table with a text column. `talk_send` is not among them: `scripts/bootstrap_exapp.sh`
leaves alice a conversation she may write into, so the tool posts into it and answers `OK`,
and that run leaves a message behind. Read the names out: there is no delete and no share,
no way to edit or remove a message that was sent, and no move as long as
`NC_MCP_TASKS_UPDATE` is off (the default); with it on, `tasks_move` is the one tool that
moves something, a single task. The upload tool creates and
refuses a path that exists.

**Read the matrix, not the summary line.** The script expects exactly the number the
registry answers, twenty since plan 09-04, so a mismatch in that line is a real finding
again. It was not always so: the run measured on 2026-08-20 printed
`FAIL tools/list expected 15 tools, got 16` and exited `1`, because the expected count was
the one phase 1 wrote down while the registry had moved on. That quoted line stays as it was
recorded, date and all. Plan 08-04 closed the drift together with the Tables pair, and plan
09-04 raised the same number with the Talk pair. The current count lives in
`tests/contract/test_tool_surface.py`, never in a document.

**Say the transport out loud:** this step runs over the stdio transport with an app
password, which is the second supported way in and the one for clients that cannot sign in
by themselves. Steps 1 to 4 were the OAuth path. Claiming otherwise here would be the one
dishonest sentence in the demo.

## Pre demo checklist

Ten minutes before, in this order. The first three are the ones that cost time in this
project when they were skipped.

- [ ] **The version, from the instance and not from the tag.** A Docker tag says what was
      pulled once, `occ` says what is running:
      ```
      docker exec -u www-data nc-mcp-exapp-nc php occ status | head -3
      ```
      Expect `version: 34.0.3.2`. The store interface station of the talk is only true from
      34.0.3 on.
- [ ] **The container carries the image you think it does.** A rebuilt image that was never
      redeployed is invisible in every other check:
      ```
      docker inspect nc_app_mcp_connector --format '{{.Image}} {{.Config.Image}}'
      ```
      Expect the digest of the image you built, `sha256:3ba4a2ce1921...` for the recorded
      run.
- [ ] **The three OAuth switches are in their default state.** All three are absent from
      the configuration in the default state, which is dynamic registration on, client
      metadata documents on and no allowlist:
      ```
      docker exec -u www-data nc-mcp-exapp-nc php occ app_api:app:config:list mcp_connector
      docker exec nc_app_mcp_connector printenv | grep NC_MCP_OAUTH_ || echo "no override"
      ```
      Expect exactly `oauth_data_key` and `public_url`, and `no override`. A leftover
      `NC_MCP_OAUTH_DCR=0` from a control probe turns step 1 into a `400`.
- [ ] The app is enabled: `occ app_api:app:list` reports `mcp_connector (MCP Connector):
      0.1.2 [enabled]`.
- [ ] The client has no leftover connection: `claude mcp logout ncmcp` if in doubt, so that
      step 1 shows a real first connection and not a cached one.
- [ ] The demo account is signed in in the browser, and the connections page shows what you
      expect it to show before the talk starts.
- [ ] Step 0 has been run once and printed its closing line. It is the cheapest full check
      of the chain that exists here.
- [ ] Screen sharing shows the browser and the terminal at once, because steps 3 and 4 are
      the two of them answering each other.

## What is deliberately not shown, and why

- **The install button is not pressed on stage.** What was measured on 34.0.3 is that the
  store interface lists this ExApp and that the install button of an ExApp reads
  `Deploy and enable`, measured on a neighbouring ExApp that was not installed, because
  this one is installed and therefore carries `Disable`. Removing it to press its own
  install button would have cost the demo substance for a statement the neighbouring row
  already made. The `Remove` entry exists too, in the action menu of the row, and only
  while the app is disabled, because AppAPI computes `canUnInstall = !active && removable`.
  All of it is in `06-07-MEASUREMENTS.md`. Pressing it live would also mean an image pull
  on a conference network, which is a bet, not a demo.
- **Nextcloud AIO is not covered.** The topology here is a plain container set with HaRP.
  Nothing about the AIO installation path has been measured by this project, so no
  sentence about it is said on stage.
- **The client metadata document proves control over a URL, not the identity of a
  program.** Whoever controls `claude.ai` can serve that document. That is the whole
  strength of the mechanism and its whole limit, and the consent page says as much by
  showing the host of the `client_id` instead of a self chosen display name. Do not claim
  that the connector recognises Claude Code. It recognises a document at an address.
- **Cursor is not the client on stage.** Cursor 3.2.16 registers against this instance with
  a `201` and then insists on a private use return address that was deliberately not
  registered, and the authorization is refused with a `400`. That is measured in
  `06-08-MEASUREMENTS.md`, it is a client side property, and it is the honest answer if
  somebody asks. Cursor works over the stdio transport with an app password.
- **No account of anybody else appears.** The connections page shows only the connections
  of the signed in account, the demo runs on a throwaway instance, and the two older
  connections of the other account on it are never opened.

## Recovery

A runbook without a fallback path is a script for the good day.

| It fails at | Most likely cause | Do this |
|-------------|-------------------|---------|
| Step 0, `/mcp` does not answer `401` | The container is not up or not enabled | `docker compose -p nc-mcp-exapp -f compose.exapp.yml ps`, then `occ app_api:app:list`; `occ app_api:app:enable mcp_connector` |
| Step 0, discovery answers the wrong address | `NC_MCP_PUBLIC_URL` is not the address the browser uses | `docker exec nc_app_mcp_connector printenv NC_MCP_PUBLIC_URL`; it has to be `http://127.0.0.1:8081/exapps/mcp_connector` |
| Step 1, `/authorize` answers `400` | A leftover switch from a control probe, see the checklist | Remove the override and redeploy, then repeat the checklist |
| Step 1, the client says the browser did not come back | Something else holds the loopback port it chose | Retry once. The client picks a new port per attempt, which is exactly why the server does not compare the port |
| Step 1, everything answers `503` | `HP_SHARED_KEY` drifted between HaRP and the daemon registration, the classic restart mistake | Bring the topology up again with the key from `.env.exapp`, see the setup section |
| Step 2, the tool answers an empty list | The wrong account is signed in | Check the account on the connections page, not in the terminal |
| Step 3, the page answers `403` or an error page | The browser session is not the account that holds the connection | Sign in again in the browser and reload the page |
| Step 3, the client stays refused after the resume | The client kept its own verdict from the `403`, see the note in that step | `claude mcp list` re-probes and recovers. Do not log in again, that would replace the connection the station is about |
| Step 5, a tool reports `FAIL` | Notes or Deck missing, or the Deck board is absent. The `tools/list` line is the known stale count, see the step | Skip the step and say so. The station is the tool list, and step 0 prints the count too |
| Anything, and the audience is waiting | | Go to step 3 with the connection from step 0 already in place, or narrate the recorded run from `06-10-MEASUREMENTS.md`. Never debug on stage |

**What to check afterwards.** Step 4 leaves the demo account without a connection, which is
the intended end state, and step 3 leaves the access switch on. Three commands say whether
the next run starts from where this one did:

```
docker exec -u www-data nc-mcp-exapp-nc php occ app_api:app:list
docker exec -u www-data nc-mcp-exapp-nc php occ app_api:app:config:list mcp_connector
curl -s http://127.0.0.1:8081/exapps/mcp_connector/connections -o /dev/null -w '%{http_code}\n'
```

Expect `0.1.2 [enabled]`, exactly the two keys `oauth_data_key` and `public_url`, and the
connections page reachable. The page of the demo account then reads `No connected apps`
while the switch above it says `MCP access is on`. The client keeps its server entry and
reports `! Needs authentication`, which is the correct state for a connection that was
ended on purpose; `claude mcp remove ncmcp -s local` takes the entry out as well.
