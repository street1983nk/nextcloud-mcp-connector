# Nextcloud in n8n AI workflows, over MCP

**Status:** measured end to end on a local HaRP topology
**Measured on:** 2026-09-04
**Scope:** connecting n8n to this connector, so that an n8n workflow reaches Nextcloud with
the identity of the person who signed in, instead of with one administrator credential
shared by everybody.

**Content hits included:** with
[Findling](https://apps.nextcloud.com/apps/findling) installed, `unified_search` returns
hits from inside documents (scans included) with the rights of the signed in user; the
answer's `note` says what was matched. Proof:
[tests/integration/test_content_hit_fidelity.py](../tests/integration/test_content_hit_fidelity.py).


Everything below was executed against **n8n 2.37.10**
(`n8nio/n8n@sha256:307d6065be25619aa24cfc63a7c2f04ca56d084a08c05c8e9f189a89f353b1ec`) and
**this connector 0.1.11** on **Nextcloud 34.0.3** with **AppAPI 34.0.0** behind
`ghcr.io/nextcloud/nextcloud-appapi-harp:release`, on the topology of
[exapp-install.md](./exapp-install.md). Where a claim is not measured, it says so in the
same sentence.

## 1. Why one MCP connection instead of one node per app

n8n already ships a Nextcloud node. It covers files, folders and users, it has no trigger,
and it knows nothing about Talk, Calendar, Contacts, Deck, Tables, Notes or Mail. It also
authenticates with one credential that belongs to whoever configured it, so every workflow
run reaches whatever that one account reaches.

This connector answers a different shape of the same problem:

| | Built in Nextcloud node | This connector over MCP |
|---|---|---|
| Coverage | Files, folders, users | 21 tools: files, search, calendar, contacts, notes, Deck, Tables, Talk, mail counters, a bundled context tool |
| Identity | One credential per node, shared by every run | One OAuth connection per person, every request runs under that account |
| Credential in n8n | Nextcloud user plus app password, stored in n8n | No password anywhere: the sign in happens on Nextcloud's own pages |
| Ending access | Delete the credential in n8n | Revoke in Nextcloud, Settings, Security, Devices and sessions, or on this app's connections page. Takes effect on the next request |
| Deletes | Node can delete files | No delete tool exists at all |

The trade is the honest other half: an OAuth connection is per person and needs one
interactive browser sign in, which a shared service credential does not. Section 6 says what
that costs in a headless setup.

## 2. Prerequisites

* Nextcloud with this connector installed as an ExApp, reachable from n8n over the network.
  See [exapp-install.md](./exapp-install.md).
* **n8n 1.119.0 or newer.** The MCP OAuth2 credential arrived with that release
  (n8n-io/n8n#21034). Measured here on 2.37.10.
* The MCP endpoint URL, with `/mcp` and **without a trailing slash**:
  `https://<nextcloud>/exapps/mcp_connector/mcp`. That string has to match the `resource`
  value of the protected resource document character for character.
* n8n has to know its own public address, because the OAuth return address is built from
  it. Set `N8N_EDITOR_BASE_URL` (and `WEBHOOK_URL`) to the address people actually type. The
  credential dialog shows the resulting return address at the top; the measured run used
  `http://localhost:5678/rest/oauth2-credential/callback`.
* **n8n must be able to reach the connector under exactly the address that is the issuer.**
  This bites in containers: a `NC_MCP_PUBLIC_URL` of `http://127.0.0.1:8081/...` is the
  n8n container itself, not the Nextcloud host. On a real installation the public https
  name solves it; the local measurement solved it with a loopback forwarder inside the n8n
  network namespace, see pitfall 5.

## 3. The two nodes, and which one you want

n8n has two MCP nodes and they are not interchangeable (measured on 2.37.10):

| Node | Type | Inputs and outputs | Use it for |
|---|---|---|---|
| **MCP Client** | `@n8n/n8n-nodes-langchain.mcpClient` | ordinary main in and out | Calling one named tool from an ordinary workflow. **No language model needed.** |
| **MCP Client Tool** | `@n8n/n8n-nodes-langchain.mcpClientTool` | no input, one `ai_tool` output | Handing the tools to an AI Agent node, which needs a chat model credential |

The distinction decides whether a scheduled, unattended workflow costs an LLM call. It does
not: the standalone **MCP Client** node calls `files_list` on a schedule with no model
attached, and that is what the observation workflow of section 7 does. The agent case is
section 5.

Both nodes take the same credential and the same transport. Use **HTTP Streamable**, not the
deprecated SSE option.

## 4. Step by step

### 4.1 The credential

**Credentials, Create credential, "MCP OAuth2 API".** The first field decides everything
after it: **Use Dynamic Client Registration**, on by default.

**Path A, registration on (the short way).** Leave the switch on, fill in **Server URL**
with the MCP endpoint, save, press **Connect**. n8n reads the discovery documents, registers
itself and opens the sign in. Measured, in the connector's log, in this order:

```
GET  200  /.well-known/oauth-protected-resource/mcp
GET  200  /.well-known/oauth-authorization-server
POST 201  /register
GET  302  /authorize?code_challenge=...&code_challenge_method=S256&client_id=...&resource=...&scope=nextcloud
POST 200  /authorize/decide
POST 200  /token
```

Two details of that run are worth keeping. n8n registers itself under the client name `n8n`,
so the Nextcloud sign in page names the connection `MCP Connector: n8n`. And it asks for
`scope=nextcloud` alone, taken from the protected resource document rather than from the
larger catalogue of the authorization server, exactly as Open WebUI does. It still receives a
refresh token, because this server records every registration with `offline_access` as well
(pitfall 7 of [oauth-setup.md](./oauth-setup.md)).

**Path B, registration off (a closed instance).** With `NC_MCP_OAUTH_DCR` off, the metadata
document carries no `registration_endpoint`, `POST /register` answers `404`, and n8n cannot
register itself. Switch **Use Dynamic Client Registration** off in the credential; the dialog
then asks for the client by hand:

| Field | Value used in the measured run |
|---|---|
| Grant Type | **PKCE**. Not "Authorization Code": this server accepts `S256` and nothing else, and the plain authorization code grant of n8n sends no `code_challenge` |
| Authorization URL | `https://<nextcloud>/exapps/mcp_connector/authorize` |
| Access Token URL | `https://<nextcloud>/exapps/mcp_connector/token` |
| Client ID | the id from the registration below |
| Client Secret | the secret from the registration below |
| Scope | `nextcloud offline_access` |
| Authentication | **Body**, to match `token_endpoint_auth_method: client_secret_post`. Header (Basic) is advertised too and works |
| Resource URL | `https://<nextcloud>/exapps/mcp_connector/mcp`, byte for byte the `resource` of the protected resource document |

**Where the client id comes from, honestly.** This server has no command and no admin form
that creates an OAuth client, so "register your clients by hand" means: register the one
client you want **while registration is still on**, write down what it answers, and then
switch registration off. A client that already exists keeps working afterwards, which was
measured (section 8, run 3). One command, run by the administrator:

```bash
curl -s -X POST https://<nextcloud>/exapps/mcp_connector/register \
  -H 'Content-Type: application/json' \
  -d '{"client_name":"n8n MCP Client",
       "redirect_uris":["https://n8n.example.com/rest/oauth2-credential/callback"],
       "grant_types":["authorization_code","refresh_token"],
       "response_types":["code"],
       "token_endpoint_auth_method":"client_secret_post",
       "scope":"nextcloud offline_access"}'
```

The answer carries `client_id` and `client_secret`. The `redirect_uris` entry has to be the
address the credential dialog shows at the top, character for character; only the port of a
loopback address is free (RFC 8252 7.3, pitfall 6 of [oauth-setup.md](./oauth-setup.md)).

If the instance also runs the allowlist mode, put the client id on the list before the first
sign in, otherwise the consent page answers "This app is not allowed".

### 4.2 The sign in

**Connect** opens a window with this connector's own pages, and the password page inside it
is Nextcloud's:

![The consent page this connector shows for an n8n connection](screenshots/n8n-consent.png)

Approving sends the browser back to n8n, which shows "Account connected". The connection then
appears in Nextcloud under Settings, Security, Devices and sessions, prefixed
`MCP Connector:`, and it can be ended there.

**This happens once per credential, in a browser, by hand.** Everything after it is
unattended. There is no way around it and the guide does not pretend otherwise: the whole
point of the connection is that a person authorised it for their own account.

### 4.3 The node

Add an **MCP Client** node:

* **Server Transport:** HTTP Streamable
* **MCP Endpoint URL:** `https://<nextcloud>/exapps/mcp_connector/mcp`
* **Authentication:** MCP OAuth2, then pick the credential
* **Tool:** switch the selector to **From List**. If the connection works, the list is the
  tool set of the connector, which was 21 entries in the measured run:

![The tool list of this connector inside the n8n MCP Client node](screenshots/n8n-tool-list.png)

A list that stays empty or reports an error is the first honest test of the credential, and
it is the fastest one: it is a `tools/list` over the same transport a tool call uses.

* **Input Mode:** JSON is the sturdier one for a fixed call, because the parameter mapper
  re-reads the tool schema on every change. `files_list` with `{"path": "/"}`:

![A successful files_list call from the n8n MCP Client node](screenshots/n8n-tool-call.png)

## 5. Two workflows

### 5.1 Unattended, no model: schedule to MCP Client

**Schedule Trigger** to **MCP Client**. Nothing else. This is the shape that answers "read
something from Nextcloud every hour and do something with it", and it costs no LLM token.
The node hands back the tool result as `content[0].text`, already parsed into JSON where the
tool answers JSON.

The observation workflow of section 7 is exactly this workflow, running hourly since
2026-09-04.

### 5.2 With an agent: AI Agent plus MCP Client Tool

For "answer a question over my Nextcloud", use an **AI Agent** node with a chat model and an
**MCP Client Tool** sub-node pointing at the same endpoint with the same credential.

Two settings matter more than they look:

* **Limit the tools.** The sub-node has an include and exclude list. 21 tool descriptions are
  context the model pays for on every turn, and an agent that only files meeting notes needs
  `notes_create` and `files_list`, not the Talk family.
* **`prepare_context` first.** This connector has one tool that bundles the usual "what is
  going on" question into a single round trip. An agent that would otherwise call four read
  tools should be told to call that one.

This section is written from the node definitions and from the tool set, **not** from a
measured agent run: the measurement of this guide used no language model. Treat the two
settings above as reasoning, and the section 4 numbers as evidence.

## 6. Stumbling blocks, named

**1. The sign in is interactive, and it is per person.** One credential is one Nextcloud
account. A team that wants one shared automation account has to create that account in
Nextcloud and sign in with it, and then the permission promise holds for that account and not
for the individuals, exactly as with MUCGPT in [client-setup.md](./client-setup.md).

**2. A dead refresh chain stops the workflow, and it looks like a 401.** The access token of
this server lives one hour, the refresh token rotates on every use and is valid for 30 days
of inactivity. So an hourly workflow refreshes about once an hour and stays alive
indefinitely; a workflow that pauses longer than the refresh window does not, and neither
does one whose connection an administrator revoked. The failure arrives as `401` on the next
tool call, and n8n reports it as a node error.

**Put an error workflow behind it.** In the workflow settings, "Error Workflow", point at a
workflow whose trigger is an **Error Trigger**. That workflow then runs on every failed
execution and is the place to send the alert. Without it, a broken connection is a silent
line in the execution list. This guide's own setup uses one.

**3. Registration off is a real mode, and it needs one registration first.** See section 4.1
path B. This is the one place where the server could be friendlier, and it is written down as
such rather than glossed over.

**4. Grant type "Authorization Code" fails against this server.** It sends no
`code_challenge`, and this server accepts `S256` only. Use **PKCE**.

**5. Container networking eats the issuer.** The address in the credential is not a hint, it
is the identity of the authorization server, and it has to resolve to the same server from
the browser **and** from the n8n process. A local development setup where Nextcloud is
published on `127.0.0.1:8081` therefore needs a forwarder inside the n8n container's network
namespace, because `127.0.0.1` inside a container is that container:

```bash
docker network connect <nextcloud-network> n8n
docker run -d --name n8n-loopback --network container:n8n --restart unless-stopped \
  alpine/socat TCP-LISTEN:8081,fork,reuseaddr,bind=127.0.0.1 TCP:<reverse-proxy-ip>:80
```

On an installation with a real https name none of this exists. It is written down because it
is the first thing that fails when somebody reproduces the measurement below.

**6. Removing the credential in n8n does not revoke anything.** Same as with the hosted
connectors: the authorization lives in Nextcloud. End it in Nextcloud.

**7. The tool set is 21 tools and the number is not held by this page.**
`tests/contract/test_tool_surface.py` holds it. A guide that promises a number is a guide that
goes stale.

## 7. Instant file events without a community node

The MCP connection is the action side. For the trigger side, Nextcloud's own bundled app
`webhook_listeners` posts internal events to an address of your choosing, and an n8n
**Webhook** node is such an address. No community node is involved.

Measured on 2026-09-04 against Nextcloud 34.0.3 with `webhook_listeners` 1.6.0.

Register the listener as an administrator:

```bash
curl -u admin:<password> -H 'OCS-APIRequest: true' -H 'Accept: application/json' \
  -X POST 'https://<nextcloud>/ocs/v2.php/apps/webhook_listeners/api/v1/webhooks' \
  --data-urlencode 'httpMethod=POST' \
  --data-urlencode 'uri=https://n8n.example.com/webhook/nextcloud-file-event' \
  --data-urlencode 'event=\OCP\Files\Events\Node\NodeCreatedEvent'
```

The payload that arrives, from the measured run, with a file created by `admin`:

```json
{"event": {"node": {"id": 512, "path": "..."},
           "class": "OCP\\Files\\Events\\Node\\NodeCreatedEvent"},
 "user": {"uid": "admin", "displayName": "admin"},
 "time": 1788520409,
 "authentication": []}
```

**Four things about this that the documentation does not say and the measurement does.**

*A JSON body is silently dropped.* Posting the registration with
`Content-Type: application/json` reached the controller with every argument `null` and
answered `996 Internal Server Error`; the Nextcloud log named the real cause,
`Argument #1 ($httpMethod) must be of type string, null given`. The same registration with
`--data-urlencode` answered `200`. Use form encoding.

*It is not instant.* The call is a **background job**, so it goes out with the next cron run
of Nextcloud, not with the request that caused the event. With system cron every five minutes
the latency is up to five minutes; with AJAX cron it is whenever somebody loads a page. That
is worth knowing before promising "instant" to anybody, and it is the honest answer to the
question the research left open.

*A target inside your own network is refused by default.* `Host "n8n" violates local access
rules` in the Nextcloud log means `allow_local_remote_servers` is off, which is the shipped
and correct state. Either reach n8n over its public name, or, on a machine you own, set
`occ config:system:set allow_local_remote_servers --value=true --type=boolean` and understand
what it opens.

*The POST carries no `Content-Type`.* The measured request arrived with `host`,
`user-agent: Nextcloud-Server-Crawler/34.0.3`, `accept-encoding` and `content-length`, and
nothing else, so the n8n Webhook node stored the body as binary and `$json.body` was empty.
One Code node after the webhook fixes it:

```javascript
const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
return [{ json: JSON.parse(buf.toString('utf8')) }];
```

The natural pairing is this trigger plus the MCP Client node: the webhook says which file
changed, and `files_read` on the same path reads it under the identity of the connected
account.

## 8. Evidence

Three runs, all on 2026-09-04, against the topology named at the top of this page. The
connector's log is `docker logs nc_app_mcp_connector`.

**Run 1, registration off, client registered by hand.** Credential with **Use Dynamic Client
Registration** off, grant type PKCE, client id and secret from a `POST /register` executed
while registration was still on. Result: consent once, `POST /token 200`, the tool list in the
node showed **21** tools, and `files_list` with `{"path":"/"}` answered with **9** entries of
the signed in account.

**Run 2, registration on.** A second credential with the switch left on and nothing but the
**Server URL** filled in. n8n read both discovery documents, registered itself
(`POST /register 201`, client name `n8n`, one redirect URI), asked for `scope=nextcloud`, and
completed with `POST /token 200`. The connection received a refresh token although it never
asked for `offline_access`.

**Run 3, the switch closes the door behind the client.** `oauth_dcr` set to `0` and the app
disabled and enabled once. The authorization server document then carried no
`registration_endpoint` and no `client_id_metadata_document_supported`, and `POST /register`
answered `404`. The credential of run 1 kept working: the same node, the same tool, the same
9 entries. So an administrator can hand out one client and then close registration, and that
is the supported shape of "register your clients by hand".

**What is not measured here, and is being measured now.** Refresh rotation over days. The
access token lives one hour and every refresh rotates the refresh token, so the claim "an
n8n workflow keeps running unattended" is a claim about a chain of rotations that has to be
watched rather than reasoned about. **An hourly workflow has been running since 2026-09-04
for exactly that purpose**, and this page will carry the result rather than a prediction. The
first refresh is expected on the first run after the initial hour.

Where the result is read, on the instance that runs it:

```bash
docker exec nc_app_mcp_connector python - <<'EOF'
import sqlite3, datetime
c = sqlite3.connect('/nc_app_mcp_connector_data/oauth.sqlite3')
for r in c.execute("""
  select a.nc_user, a.client_id, count(r.token_hash),
         sum(case when r.state='used' then 1 else 0 end),
         min(r.issued_at), max(r.issued_at)
  from authorizations a join refresh_tokens r on r.auth_id = a.auth_id
  where a.revoked_at is null group by a.auth_id"""):
    print(r)
EOF
```

The fourth column is the number of rotations of that connection. It was `0` at
2026-09-04T11:03Z for both n8n connections, and it is what has to grow by roughly one per hour
for the claim to hold. The other half of the answer is n8n's own execution list of the
observation workflow: every hourly run has to be green, and a red one has to name a `401`.

## Related

* What a user enters into other clients: [client-setup.md](./client-setup.md)
* The server side of OAuth, the three switches and the discovery paths:
  [oauth-setup.md](./oauth-setup.md)
* Installing the app as an ExApp: [exapp-install.md](./exapp-install.md)
* Nextcloud's own documentation of the webhook app:
  [Webhook Listeners](https://docs.nextcloud.com/server/stable/admin_manual/webhook_listeners/index.html)
* The n8n node this guide uses:
  [MCP Client Tool](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp/)

**Is a native n8n trigger node for Nextcloud worth building?** Section 7 is the answer this
project currently gives: the bundled webhook app plus a Webhook node covers file events today,
at the price of the cron latency. If that price is too high for what you are building, say so
in a GitHub discussion on this repository. That is the signal the decision hangs on.
