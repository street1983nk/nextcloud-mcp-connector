# Client setup

Three ways to connect an assistant to your Nextcloud with this server:

| Transport | Who it is for | Credentials |
|-----------|---------------|-------------|
| **stdio** | One person, one machine. Claude Desktop, Claude Code, Cursor and every other client that starts a local process. | App password from the environment |
| **Streamable HTTP** | A shared or remote deployment. One process can serve several people. | App password per request, in the `Authorization` header |
| **ExApp (AppAPI)** | An administrator installs the server into Nextcloud itself, and every user connects with their own identity. | OAuth 2.1 per user, or an app password per request; HaRP resolves either to the user |

All three speak the same 20 tools. The only difference is where the credentials come from and
where the identity is resolved.

The ExApp mode has its own installation guide in [exapp-install.md](exapp-install.md). Per
client, this page covers Claude Desktop, Claude Code, Claude.ai, ChatGPT, Cursor, Open WebUI
and MUCGPT; each section says what was measured and against which version.

## Before you start: get an app password

Never use your login password. In Nextcloud, open **Settings, Security, Devices and
sessions**, enter a name such as `mcp`, and press **Create new app password**. Nextcloud
shows the value once. It looks like `xxxxx-xxxxx-xxxxx-xxxxx-xxxxx`.

An app password can be revoked on that same page without touching your account, and it is
the only credential this server ever accepts. Two factor authentication stays intact,
because an app password bypasses the second factor by design and only for this one token.

## stdio

### Install

```bash
uv tool install nextcloud-mcp-connector
```

This puts the `nc-mcp` command on your PATH. Check it before you configure any client:

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

A working server prints nothing and waits on stdin. That silence is correct: stdio is a
pipe protocol, not a console application. Press Ctrl+C to stop it. If the command exits
immediately with an error instead, the message names the variable that is missing or the
URL that could not be reached.

### Claude Desktop

Edit `claude_desktop_config.json`:

* macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
* Windows: `%APPDATA%\Claude\claude_desktop_config.json`
* Linux: `~/.config/Claude/claude_desktop_config.json`

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

Restart Claude Desktop completely, not just the window. The 20 tools then appear in the
tools menu of a new conversation.

If `nc-mcp` is not found, the desktop app does not see your shell PATH. Use the absolute
path instead, for example `"command": "/home/alice/.local/bin/nc-mcp"`, or point at the
checkout with `"command": "uv"` and
`"args": ["run", "--directory", "/path/to/nextcloud-mcp-connector", "nc-mcp"]`.

### Claude Code

```bash
claude mcp add nextcloud \
  --env NC_MCP_URL=https://cloud.example.com \
  --env NC_MCP_USER=alice \
  --env NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx \
  -- nc-mcp
```

Verify with `claude mcp list`. The entry has to say `connected`.

### What stdio does not do

stdio has no request headers, so it has no place to put an `Authorization` value. The
security boundary of this mode is the process that starts the server: whoever can start
`nc-mcp` can use the credentials in its environment. That is the right model for your own
laptop and the wrong one for a shared machine. Use HTTP there.

## Streamable HTTP

### Start the server

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_ALLOWED_HOSTS=mcp.example.com
uv run uvicorn mcp_connector.entry_http:app --host 127.0.0.1 --port 8765
```

The MCP endpoint is `POST /mcp`. `GET /health` answers `{"status":"ok","version":"..."}`
without authentication and without the host check, which is what a reverse proxy or a
container health check should poll. It is a liveness probe and nothing else: a 200 there
does not mean a client can connect, see the 421 section below.

Note what is missing from that block: no `NC_MCP_USER` and no `NC_MCP_APP_PASSWORD`. In
this mode the server holds no Nextcloud account of its own. The target Nextcloud, however,
always comes from `NC_MCP_URL` and never from the request, because a client that could
choose the target could point this server and its credentials at a host of its choosing.

### Credentials per request (Basic passthrough)

Every request carries the user's own app password in an ordinary Basic header:

```
Authorization: Basic base64(alice:xxxxx-xxxxx-xxxxx-xxxxx-xxxxx)
```

The server forwards it to Nextcloud unchanged and lets Nextcloud decide. It stores nothing,
caches no credential and never treats the header as an identity claim of its own, so one
deployment can serve several people without a token store. Every client that lets you add a
header to a remote MCP server works with this. In Claude Code:

```bash
claude mcp add --transport http nextcloud https://mcp.example.com/mcp \
  --header "Authorization: Basic $(printf 'alice:xxxxx-xxxxx-xxxxx-xxxxx-xxxxx' | base64)"
```

Put the deployment behind TLS. Basic is base64, not encryption, and a proxy on the way sees
the password in plain text otherwise.

### Single user alternative: a static bearer

If exactly one person uses the deployment, a fixed token is simpler than a Basic header per
request:

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
export NC_MCP_STATIC_BEARER=a-long-random-string
export NC_MCP_PUBLIC_URL=https://mcp.example.com
export NC_MCP_ALLOWED_HOSTS=mcp.example.com
uv run uvicorn mcp_connector.entry_http:app --host 0.0.0.0 --port 8765
```

Clients then send `Authorization: Bearer a-long-random-string`. The bearer authenticates
the caller of this server; it does not select a Nextcloud user. The account comes from the
environment, exactly as in stdio mode. The two HTTP modes are mutually exclusive, and
starting the server with both configured is an error rather than a silent preference.

### Host allow list

`NC_MCP_ALLOWED_HOSTS` is a comma separated list of the `Host` headers this server accepts.
It is not the bind address. `--host 0.0.0.0` lets the socket listen everywhere and still
allows nobody in, because the allow list is checked separately.

Each bare name is expanded into two entries, `example.com` and `example.com:*`, because a
client that was given a port puts the port into the `Host` header. A name that already
carries a port or a wildcard is taken exactly as written.

Two entries are always in the list, with or without the variable, because they are the
addresses this deployment answers to rather than a permission somebody granted: the host of
`NC_MCP_PUBLIC_URL` and, in the ExApp mode, the host of the `NEXTCLOUD_URL` the deploy
daemon sets. That is what makes a Nextcloud AIO installation with a custom domain work
without any configuration (issue #4); before it, every `/mcp` request there answered 421.

Apart from those two, only `127.0.0.1`, `localhost` and `[::1]` are accepted without the
variable, and an explicit `NC_MCP_ALLOWED_HOSTS` replaces those three rather than extending
them.

Behind a reverse proxy that rewrites `Host` itself, and only there, the check can be turned
off with `NC_MCP_DISABLE_DNS_REBINDING_PROTECTION=true`.

## ExApp mode (installed through AppAPI)

The third way to run this server is as a Nextcloud ExApp, installed by an administrator
through AppAPI. It sits beside stdio and the standalone HTTP mode above: same code, same 20
tools, a different place the identity comes from. Installing it is a separate document,
[exapp-install.md](exapp-install.md); this section is about connecting a client to an
instance where it is already installed.

The client endpoint is:

```
https://<nextcloud>/exapps/mcp_connector/mcp
```

That is the public Nextcloud URL with the ExApp prefix, not a port of its own. AppAPI reaches
every ExApp under `/exapps/<appid>`, and the reverse proxy in front of Nextcloud forwards it.

There are two ways to authenticate against it, and both are supported. The simpler one is a
Nextcloud username and an app password, sent as an ordinary Basic header, exactly as in the HTTP
passthrough above:

```
Authorization: Basic base64(alice:xxxxx-xxxxx-xxxxx-xxxxx-xxxxx)
```

The difference is where that header is read. It goes to HaRP, the AppAPI proxy, which resolves
it to a Nextcloud user and hands the ExApp the resolved identity as signed AppAPI headers. The
server never receives the app password as a Nextcloud credential of its own; it receives who
the user is, and every Nextcloud request then runs under that user's own permissions. This is
why the permission promise holds through the whole chain and not only in our client layer.

The other way is OAuth 2.1, and it is the one to prefer where the client can speak it: the
client registers itself, each user signs in on Nextcloud's own page, and no app password is
copied anywhere. The endpoint is the same one, so the only difference in the client
configuration is the header. See the OAuth section further down and, for the server side,
[oauth-setup.md](./oauth-setup.md). The app password stays supported for every client that
cannot do OAuth, which is what the rest of this section and the MUCGPT section below are
about.

In Claude Code, the same command as the HTTP mode points at the ExApp endpoint:

```bash
claude mcp add --transport http nextcloud https://cloud.example.com/exapps/mcp_connector/mcp \
  --header "Authorization: Basic $(printf 'alice:xxxxx-xxxxx-xxxxx-xxxxx-xxxxx' | base64)"
```

### Three things that are specific to this mode

1. **The PHP proxy path is not the way in.** AppAPI also exposes an ExApp under
   `/apps/app_api/proxy/mcp_connector/...`, and it answers. It is still not the recommended
   endpoint: its streaming and header behaviour differ from the direct `/exapps/` route, which
   is the one measured and relied on here. The measurement of both paths is in
   [spike-discovery.md](spike-discovery.md); use `/exapps/mcp_connector/mcp`.
2. **No `/exapps/` rule, no connection.** The reverse proxy in front of Nextcloud has to route
   `/exapps/*` to HaRP. Without that rule the installation never even completes its heartbeat,
   let alone serves `/mcp`, and the failure looks like a Nextcloud problem rather than a proxy
   one. The bundled Caddy of Nextcloud All-in-One ships this rule, and `deploy/Caddyfile`
   rebuilds it for the local topology.
3. **Discovery lives at a pointer, not at the canonical path.** The RFC 9728 metadata an
   OAuth client looks for is reachable unauthenticated over the ExApp, but the canonical
   `/.well-known/oauth-protected-resource/...` root path is answered by Nextcloud with a 404, so
   a client has to follow the `resource_metadata` pointer from the `WWW-Authenticate` header
   instead. The fallback, a reverse proxy rule that serves the metadata at the canonical path,
   is written out in [spike-discovery.md](spike-discovery.md).

## Browser onboarding (no app password to copy by hand)

An assistant app that cannot speak OAuth still needs a credential, and the section at the top
of this page asks you to create one in the Nextcloud settings yourself. The onboarding page
does that part for you. Open it in a browser:

```
https://<nextcloud>/exapps/mcp_connector/connect
```

What happens there, in four steps:

1. The page explains what it does and offers one button, "Continue to Nextcloud sign in".
2. Pressing it opens the Nextcloud sign in page in a new window. This is Nextcloud's own
   page on your own instance, with your own login and your own second factor. Approve the
   connection there, then come back to the connector page.
3. That page waits for the result. It refreshes itself every few seconds and carries a
   "Check now" button for browsers where automatic refresh is switched off.
4. When the sign in is complete, the page shows your user name and one credential for your
   assistant app.

Enter both into your client exactly like the app password in the sections above: user name
and credential as Basic credentials against `https://<nextcloud>/exapps/mcp_connector/mcp`.

**The credential is shown once.** Nothing of it is stored on this server, so there is no page
that can show it again. If you miss it, lose it, or close the window too early, open
`/connect` again and run the sign in a second time. The old attempt runs out on its own after
twenty minutes, and an unused credential can be removed in the Nextcloud settings.

### How to tell a real page from a fake one

This server never asks for your Nextcloud password. Not on the onboarding page, not on the
waiting page, not on the result page. None of them has an input field at all. A page that
looks like this one and asks you to type your Nextcloud password is not from this server:
close it, and tell your administrator.

The credential you get is an ordinary Nextcloud app password that belongs to you. It appears
in **Settings, Security, Devices and sessions** under the name of this connector, together
with every other connection of your account, and you can end it there at any time without
touching your password or your second factor.

### Which way is meant for which client

* **OAuth** is the way for Claude.ai and ChatGPT, which register themselves and run the whole
  authorization in the client. Nothing is copied by hand there; see the next section.
* **Browser onboarding** is the way for every other client: it produces the credential the
  Basic header of the sections above needs, without you creating an app password by hand.
* **The app password sections above stay valid** for stdio, for the standalone HTTP mode and
  for the ExApp mode. The onboarding only replaces the manual step of creating one.

## OAuth clients (Claude.ai, ChatGPT)

A client that speaks the MCP authorization specification needs one thing from you: the URL
of the connector. Enter it exactly like this, with `/mcp` and **without a trailing slash**:

```
https://<nextcloud>/exapps/mcp_connector/mcp
```

The trailing slash is not cosmetic. That string has to match the `resource` value of the
protected resource document character for character, and a URL that ends in a slash is a
different resource. A client that is given the wrong form fails before the first tool call.

What happens after you enter it:

1. The client calls the URL, gets a `401` and reads the address of the metadata out of it.
2. It registers itself, with no client id and no secret you have to create.
3. It opens a browser window. What you see there is **Nextcloud's own sign in page** on your
   own instance, with your own login and your own second factor. This connector never asks
   for your password and has no input field for one.
4. After the sign in you get one page from the connector that names the client, your account
   and what the connection may do, with an "Approve access" and a "Deny access" button.
5. Approving sends the browser back to the client, which is connected from then on.

The connection appears under **Settings, Security, Devices and sessions** with the name of
the client, prefixed by `MCP Connector:`. Ending it there ends it immediately, and so does
the client's own disconnect button.

### Claude.ai, step by step

Measured on 2026-08-16 against a public instance.

1. Connectors have moved out of Settings into **Customize**. Two ways in: Customize,
   Connectors, "Add", "Add custom connector"; or, in the composer, the attachment menu,
   "Add connector".
2. The form asks for a name, the "Remote MCP Server URL", and optionally an OAuth client id
   and secret. **Leave both OAuth fields empty**, the client registers itself.
3. Nextcloud's sign in page appears with its own security warning and names the client
   "MCP Connector: Claude". Then comes this connector's own consent page, which shows an
   "Unverified client" note (correct, the client registered itself), the app name, the
   return address and the client id.
4. After "Approve access" the browser returns to claude.ai and the connector is connected.
   The tools show up grouped into read only and write, both set to ask for approval.

**On a Team or Enterprise account the button does not exist.** Only owners may add custom
connectors there, so an account whose role is "user" never sees it. Use a personal account;
the free plan allows one custom connector, which is enough.

**Removing the connector in Claude.ai does not revoke access.** If you add the same URL
again afterwards, the old authorization is still there and the client goes straight back to
work without asking you anything. To really end it, revoke the connection in Nextcloud
(Settings, Security, Devices and sessions, or this app's connections page).

### ChatGPT, step by step

1. Custom MCP servers need **developer mode**: Settings, "Security and sign in",
   "Developer mode". It carries an "increased risk" badge.
2. The plugins page then shows "Create app", which opens the connector form: name,
   description, server URL, authentication (OAuth is the default) and a mandatory
   "I understand and want to continue" checkbox.
3. The rest is the same as above: Nextcloud's sign in page, then this connector's consent
   page, then back to ChatGPT.

ChatGPT mints its return address per connector, in the shape
`https://chatgpt.com/connector/oauth/<token>`. That matters only if your administrator runs
the allowlist mode, because the address cannot be known before the connector exists.

**If a connection has to be repeated**, tell the existing connector to connect again rather
than deleting and recreating it; a re-run picks up the changed server side without losing
the entry.

### Open WebUI, step by step

Measured on 2026-08-19 against Open WebUI 0.11.0
(`ghcr.io/open-webui/open-webui:main`, digest
`sha256:6a773e5c3a246b65cbe74ce942b294292c0e5f81c138f703d111bc162f7d7c3d`) and this connector
installed as an ExApp. Both halves were run: the requests server side, and the two screens in a
browser, with two accounts.

Open WebUI speaks the MCP authorization specification since 0.6.31, and that changes what this
section has to say about it: it is not a proxy case any more. It registers itself, so there is
no client id to create; it authenticates every user of your instance separately, so one
connection is not shared; and it registers exactly **one** return address, which is why the
`cursor://` problem of the next section does not apply here. Nothing is copied by hand and no
app password is involved.

**Before you start**

* An **administrator** account in Open WebUI. Only an administrator may add a tool server; the
  sign in that follows is done by each user for themselves.
* The connector URL, `https://<nextcloud>/exapps/mcp_connector/mcp`.
* Open WebUI reachable under an address this server accepts as a return target. That is the one
  thing that can go wrong before anything else does, see stumbling block 3 below.

**The steps**

1. In the admin settings, open **Tool Servers** and press **Add Connection**.
2. **Connection Type:** pick **MCP** with the transport **Streamable HTTP**. Not OpenAPI: an
   OpenAPI connection asks the address for an `openapi.json`, and this server does not serve
   one, it speaks MCP.
3. **URL:** `https://<nextcloud>/exapps/mcp_connector/mcp`, with `/mcp` and **without a
   trailing slash**, for the reason given at the start of this section: the string has to match
   the `resource` value of the protected resource document character for character.
4. **Auth:** **OAuth 2.1**. Not **OAuth 2.1 (Static)**, which is the variant for a server where
   an administrator pastes a client id and a secret; this server hands both out itself. Leave
   the key field empty.
5. **Save.** Open WebUI now registers itself. Expected result, in this server's log, in this
   order:

   ```
   POST /mcp                                        401 Unauthorized
   GET  /.well-known/oauth-protected-resource/mcp   200 OK
   GET  /.well-known/oauth-authorization-server     200 OK
   POST /register                                   201 Created
   ```

   The first line is not an error. Open WebUI sends an unauthenticated `initialize` on purpose
   and reads the address of the metadata out of the `WWW-Authenticate` header of the 401. The
   registration that arrives carries the client name `Open WebUI`, exactly one return address
   (`http://localhost:3030/oauth/clients/mcp:<server id>/callback` in the measured run), the
   grant types `authorization_code` and `refresh_token`, and the scope `nextcloud`, which Open
   WebUI takes from `scopes_supported` of the protected resource document rather than from the
   larger catalogue of the authorization server. This server records the registration with
   `nextcloud offline_access`, and that added scope is what later produces a refresh token.
6. **Set the access of the connection.** A new connection is **Private** by default, which
   means only the administrator who created it sees it. Set it to **Public**, or grant the
   groups that may use it. This is stumbling block 7 below and it is the one that makes a
   working connection look like a missing one for everybody else.
7. The connector now appears in the tool list as one entry named after the connection. Each
   user opens it once and starts the sign in (**Authenticate**). What happens then, measured in
   a browser: a short page of this connector ("Sign in to continue"), then Nextcloud's own sign
   in page, then Nextcloud's own "Grant access" page which names the account it is about, then
   this connector's consent page. That page shows "You are signed in as \<account\>", the app
   name `Open WebUI`, the address it sends you back to, an "Unverified client" note, and what
   the connection may do. After **Approve access** the browser returns to Open WebUI without an
   error, the tool dialog says the server is connected, and the composer shows one available
   tool.
8. **Check that it worked.** After the approval, this server's log shows
   `POST /token 200 OK`, and a tool call from Open WebUI appears as `POST /mcp 200 OK`. In the
   measured run Open WebUI listed all 16 tools, and with two accounts connected at once each of
   them saw exactly its own Nextcloud: the account that had signed in as the owner of a private
   file found it, the account that had signed in as somebody the file was never shared with did
   not, while both found the folder that had been shared read only between them.

**Eight things that go wrong, and what each one looks like**

1. **The connection type is OpenAPI instead of MCP.** Then Open WebUI asks for an
   `openapi.json` and reports a broken tool server, although the address is right. The type is
   not a label, it selects a different protocol.
2. **`WEBUI_SECRET_KEY` is not pinned.** Open WebUI derives the keys that encrypt the stored
   client registration and the stored OAuth tokens from it
   (`OAUTH_CLIENT_INFO_ENCRYPTION_KEY` and `OAUTH_SESSION_TOKEN_ENCRYPTION_KEY` default to it).
   In 0.11.0 the process refuses to start without it and the shipped `start.sh` generates one
   into `.webui_secret_key` in the working directory instead, which is **not** inside the data
   volume. So a container started without the variable and without that file preserved comes up
   with a new key, and every connection of every user has to be authorized again. Set it:

   ```bash
   docker run -e WEBUI_SECRET_KEY="$(openssl rand -hex 32)" ...
   ```
3. **Open WebUI is reached over `http` on anything but a loopback address.** This is the one
   that looks like a fault of this server and is not. The return address Open WebUI registers is
   built from its own address, so an instance at `http://192.168.1.50:3000` or
   `http://openwebui.lan` asks to register an `http` address that is not loopback, and this
   server refuses with `400`:

   ```json
   {"error":"invalid_redirect_uri",
    "error_description":"redirect_uris must use https, except loopback addresses of native clients"}
   ```

   In Open WebUI the same refusal reads:

   ```
   Failed to register OAuth client: Dynamic client registration failed:
   {"error":"invalid_redirect_uri","error_description":"redirect_uris must use https, except
   loopback addresses of native clients"}
   ```

   The rule is deliberate and it is not going to be relaxed: `https` is accepted on any host,
   and `http` only on `127.0.0.1`, `localhost` and `::1`, which is the exemption the OAuth 2.1
   security guidance grants a native client for its own callback. A return address that travels
   over plain `http` across a network carries an authorization code across that network.
   The fix belongs to whoever runs Open WebUI, not to this server: put it behind TLS, or reach
   it on `localhost`.
4. **`WEBUI_URL` does not match the address people use.** The return address is built from
   Open WebUI's configured own URL, falling back to the address of the incoming request. If the
   configured value is wrong, the registration is refused for the wrong reason or the browser
   comes back to an address nobody can open. Set it to the address your users type.
5. **The connector is a tool group, not an always on tool.** After the authorization it appears
   as one selectable entry (measured: `server:mcp:nextcloud`), and a chat has to switch it on or
   a model has to be granted it. A chat that was never given the tool answers from the model
   alone, which looks like a broken connection and is a switch that is off.
6. **Only an administrator can add the server, and every user signs in separately.** The tool
   server list is an administrator screen, while the sign in and the token belong to each
   account: Open WebUI stores one OAuth session per user and per server, and an account that has
   not signed in gets no token, therefore no `Authorization` header, therefore a `401` from
   this server. That is the intended behaviour, not a missing bulk setting. It is also the
   reason the permission promise of this connector survives a shared Open WebUI: every request
   carries the identity of the person who signed in.
7. **The connection is Private, so nobody else sees it.** This is the most likely reason a
   correctly configured server is invisible. The access of a tool server connection defaults to
   **Private**, and a user then finds no entry to authenticate against at all, which reads like
   the server was never added. Open the connection, set **Access** to **Public** or name the
   groups, and the entry appears for those accounts. Measured: with the default, an account of
   role `user` saw nothing; after the change, the same account saw the entry and completed its
   own sign in.
8. **A Nextcloud session already open in the same browser silently decides the account.** The
   sign in is Nextcloud's own, so a browser that is already signed in to Nextcloud skips the
   password page and goes straight to the "Grant access" page of that session's account. The
   consent page then honestly says which account it is, and it is easy to press past. If you
   want to connect a different account than the one the browser is signed in to, sign out of
   Nextcloud first, or use a private window. This is not specific to Open WebUI, it applies to
   every client whose sign in runs in a browser you are already using; it is worth knowing here
   because an administrator testing the setup is usually signed in as the administrator.

### Claude Code over OAuth: refused until 0.1.2, connects since, without registering at all

Claude Code needs no button and no app password for this way. One command, and the OAuth
sign in is a second one:

```bash
claude mcp add --transport http nextcloud https://<nextcloud>/exapps/mcp_connector/mcp
claude mcp login nextcloud
```

Up to and including 0.1.2 this could not work, and the section that used to stand here said
so: Claude Code does not register itself at all. Its client id **is** the https address of a
small JSON document it publishes, and a server that only knows dynamic registration has
nothing to look up. The document, unchanged when it was read on 2026-08-20:

```json
{"client_id":"https://claude.ai/oauth/claude-code-client-metadata","client_name":"Claude Code",
 "redirect_uris":["http://localhost/callback","http://127.0.0.1/callback"],
 "grant_types":["authorization_code","refresh_token"],"response_types":["code"],
 "token_endpoint_auth_method":"none"}
```

**Measured against Claude Code 2.1.233 on 2026-08-20, and it connects and calls a tool.**
Four full runs against a Nextcloud 34.0.3 instance: the discovery chain, the authorization
request with the metadata document address as the client id, the consent screen with
`claude.ai` shown as the host of that id, the code exchange, and `files_list` answering with
the real content of the signed in account. `claude mcp logout` ends the connection over
`/revoke`, twice, once per token.

Two things about it are worth knowing before anybody configures anything.

**The callback port changes on every run.** The document publishes two return addresses
without a port, and the client arrives with one. Not with the documented default 3118, and
not with the same port twice:

```
run 1  16:06:38Z   redirect_uri=http://localhost:45157/callback
run 2  16:08:44Z   redirect_uri=http://localhost:47608/callback
run 3  16:09:11Z   redirect_uri=http://localhost:41977/callback
run 4  16:09:27Z   redirect_uri=http://localhost:34567/callback   (MCP_OAUTH_CALLBACK_PORT=34567)
```

That is the reason the port of a loopback address is no longer compared here, and **nothing
else about the address rule moved**: scheme, host, path and query are still compared
character for character, and D-35 still admits `https` anywhere and `http` on loopback only.
The rule and its residual risk are in
[oauth-setup.md](./oauth-setup.md), pitfall 6. If you would rather pin the port, set
`MCP_OAUTH_CALLBACK_PORT` in the client's environment; run 4 above is that case.

**`claude mcp login` needs a terminal.** Without one it prints the authorization URL and
then stops with `stdin isn't a terminal`. That is a property of the client and not of this
server, and it only matters if you were going to script the sign in.

The raw numbers, including the refusals that show the boundary still holds, are in
[06-09-MEASUREMENTS.md](../.planning/phases/06-h-rtung-eigennachweise-und-conference-reife/06-09-MEASUREMENTS.md).

### Cursor and other clients with a `cursor://` style callback: registration goes through, sign in does not

Cursor is configured by writing `~/.cursor/mcp.json`, no button involved:

```json
{ "mcpServers": { "nextcloud": { "url": "https://<nextcloud>/exapps/mcp_connector/mcp" } } }
```

Up to and including 0.1.1 it would not connect. Cursor's log said
`redirect_uris must use https, except loopback addresses of native clients`, and that
sentence is this server's: Cursor registers a private-use URI scheme
(`cursor://anysphere.cursor-mcp/oauth/callback`) alongside two acceptable addresses, and
this server refused a registration that contained an address it does not admit.

**Since 0.1.2 the inadmissible address is dropped and the registration goes through** with
the two acceptable ones. The rule itself is unchanged: the private-use address is not
registered, so this server never sends anybody there. A client that offers nothing but
inadmissible addresses is still refused with the same sentence.

**Why that address is not registered.** RFC 8252 lists private-use schemes as one of three
legitimate forms for a native client, but on a desktop no application
owns a scheme exclusively, so another program can claim it and receive the authorization
code. That is the reason behind the rule (D-35), and it is unchanged.

**Measured against Cursor 3.2.16 on 2026-08-20, and it still does not connect.** Writing
the file is enough for discovery and registration, seconds later and without a click, and
the registration is answered `201` with two addresses in the record. The sign in is where
it stops: Cursor takes the first of its own three addresses, and that is the one that was
dropped.

```
POST 201  /register     redirect_uris in the record: www.cursor.com and localhost:8787
GET  400  /authorize    redirect_uri=cursor://anysphere.cursor-mcp/oauth/callback
```

The browser gets the error page "This app cannot be sent back safely" and no redirect, so
nothing is shared and no password page is ever shown. That page names the way out itself, in
words and not as a link: for assistant apps that cannot use this sign in at all, the way in
is an app password from the Nextcloud security settings, which is the path described at the
top of this page. The reason is on the client side and
it is worth knowing before anybody looks for a server bug: Cursor keeps its own three
addresses after the `201` instead of reading the registered ones back out of the answer, so
it cannot tell that one of them will be refused. Two counter checks with the same client id
say the rest: the registered `http://localhost:8787/callback` reaches the consent page, and
so does the same address on a different port, which is the port rule of RFC 8252 7.3 at
work. The raw numbers are in
[06-08-MEASUREMENTS.md](../.planning/phases/06-h-rtung-eigennachweise-und-conference-reife/06-08-MEASUREMENTS.md).

**So for Cursor, use the app password way above.** What changed with 0.1.2 is where the
attempt fails, not that it succeeds: the registration is no longer refused, and a client of
this shape that does offer an admissible address at sign in is now let through. Cursor is
not yet such a client.

### MUCGPT

MUCGPT is a real MCP client, so no adapted build of this connector is needed: it speaks
Streamable HTTP and it reads MCP servers out of its own `config.yaml`. What it cannot do is
OAuth. It knows no discovery, no dynamic client registration and no browser sign in, so the
credential has to be configured, and there is exactly one place it can go.

**A gap, named up front:** this section is not verified against a running MUCGPT instance.
Everything below is derived from the source of `it-at-m/mucgpt` as of 2026-08-18, not from a run,
because there is no access to such an instance here. That is a real gap and not a formality: it
is the only client section on this page
without a measurement behind it. What a proof would need is small and named, so it can be closed
in one sitting by anybody who has the access: an instance with its Keycloak, one account on it,
and a `config.yaml` carrying the MCP source below. The three things to check are that the
`Authorization` header arrives at all, that the tool list comes back, and that a tool call
answers with content of the configured Nextcloud account. They are written out as a protocol at
the end of this section, in the order in which they can fail and with what to note for each.

**What works**

The MCP source in `config.yaml`, with the two keys that are not optional:

```yaml
MCP:
  - name: nextcloud
    transport: streamable_http
    url: https://<nextcloud>/exapps/mcp_connector/mcp
    forward_token: true
    forward_auth_override: "Basic <base64 of user:app-password>"
```

`forward_token: true` and `forward_auth_override` belong together, and MUCGPT enforces exactly
that pairing: its own validator refuses a configuration with the override and without the
forward, with `forward_auth_override requires forward_token=true`.

**An `Authorization` entry under `headers` is silently dropped.** This is worth spelling out
because it is the configuration a reader would try first, and it fails without a useful message:
when MUCGPT copies the `headers` block of a source, it filters out the key `authorization` on
purpose. So a header set there never arrives, the request reaches this server without a
credential, and the answer is a `401` that looks like a broken server. The warning sign is
MUCGPT's own log line listing the header names configured for the source: `Authorization` is not
among them. The two keys above are the only way in.

**The price, and it is not a detail**

`forward_auth_override` is one single value per MCP source, not one per person. Whatever account
is in that base64 string, every MUCGPT user of that source runs as that account. So this path is
a **team or service account**, and it has to be treated as one:

* Give it its own Nextcloud account and its own app password, not a person's. Name it so that
  the entry under Settings, Security, Devices and sessions is recognisable.
* Give that account access to exactly what the group may see, and nothing else. The permission
  promise of this connector still holds, but it holds for the service account: this server never
  sees more than that account may see, and it also never sees less, so it cannot tell two MUCGPT
  users apart.
* Say so to your users. A shared account is a legitimate setup and a bad surprise.

Real per user fidelity needs one of two things, and neither is a fix we can ship on our side
alone: either MUCGPT forwards a credential per person, or its own per user OIDC token is
exchanged for a Nextcloud identity, which needs a trust anchor (which issuer may do this) and an
identity mapping (the same accounts on both sides, so SSO or LDAP). That is a feature and not a
repair, and it is not part of v1.

**Closing the gap: the protocol, three checks in the order they can fail**

Nothing on this page is harder to close than this gap, and nothing is smaller: the run below fits
into one sitting. It is written so that the result has the same shape as the proof behind the
other client sections of this page. The model is the Open WebUI run recorded in
`.planning/phases/05-hardening-und-store-einreichung/05-07-MEASUREMENTS.md`: a table of the
topology first, then one numbered check per step, each with the literal line that was observed
and a counter check where one is possible.

What you need before you start:

* A running MUCGPT instance together with the Keycloak it authenticates against, and one account
  on it. Neither of the two lives in this repository, which is the whole reason this check cannot
  be automated here.
* This connector reachable from that instance over https, and the address of its `/mcp` endpoint,
  for example `https://<nextcloud>/exapps/mcp_connector/mcp`.
* A Nextcloud account for the source with an app password of its own, not a person's account (see
  "The price" above), and the two `config.yaml` keys from this section: `forward_token: true`
  together with `forward_auth_override`.
* Access to the log of this connector's container (`docker logs nc_app_mcp_connector`), because
  two of the three checks are answered there and not in MUCGPT.

Note the topology before the first request, in the shape of the table in the measurement file
named above: MUCGPT version and image digest, the version of this connector, the value of
`NC_MCP_PUBLIC_URL`, and the date and time of the run. Without those four values the result
proves nothing a year from now.

1. **Does the `Authorization` header arrive at all?** Start MUCGPT with the source configured and
   let it connect once. Note two things: the header names MUCGPT logs for that source, where
   `Authorization` has to appear (the silent drop described above is the trap), and the status of
   the first `POST /mcp` line in this connector's log. A `401` means the credential never arrived,
   and the cause is almost always a `headers` block instead of the two keys. A `200` means it
   arrived and was accepted.
2. **Does the tool list come back?** Ask MUCGPT for the tools of that source. Note the number of
   tools it lists, 16 at the time of that run, and whether the names match the ones this page
   lists. The current number is held by `tests/contract/test_tool_surface.py` and never by this
   page. A source that authenticates and lists nothing points at the transport, not at the
   credential.
3. **Does a tool call answer with content of the configured account?** Ask for something that
   needs exactly one tool, for example the files in the root of that Nextcloud. Note the tool that
   was called, the `POST /mcp 200` line in the log, and one detail of the answer that can only
   come from that account, such as a folder that exists there and nowhere else. Then the counter
   check that carries the weight: ask for a file the configured account may not see, and note that
   the answer is empty or refused. That is the difference between "a call went through" and "the
   permission promise holds".

While you are there, ask the question BL-12 leaves open, because whoever has the access is the
only person who can answer it: `forward_auth_override` is one value per source, so every MUCGPT
user of that source runs under one Nextcloud account, and that is the single place where this
project's core promise (every request under the identity of the person asking) does not hold. Is
a team or service account enough for that deployment, or does it need per user fidelity? The
answer decides whether the token exchange sketched above is a feature worth building or a thing
nobody asked for.

Write the result into a measurement file next to the others and replace the gap paragraph at the
top of this section with a dated line. Until that has happened, the paragraph stands as it is.

**The one advantage over a hosted assistant**

MUCGPT is self hosted or EU based, so the flow of content to the assistant's provider that
[privacy.md](privacy.md) asks an operator to account for does not leave for a third country
here. That is the section "What leaves your control" of that document, and MUCGPT is the case it
names as the way to avoid the transfer.

### If the client cannot find the authorization server

Symptom: the client reports "could not discover authorization server", "authorization
server metadata not found" or simply refuses to connect, although opening
`https://<nextcloud>/exapps/mcp_connector/.well-known/oauth-protected-resource/mcp` in a
browser shows a JSON document.

Cause: the client only tries the canonical path on the domain root, and that path belongs
to Nextcloud, which answers 404 there. Two reverse proxy rules map it back onto this app;
they are in the Install section of [oauth-setup.md](./oauth-setup.md), for Caddy and for
nginx, and they are the administrator's part.

Claude.ai turned out **not** to be in this group: measured with both rules switched off, it
falls back to the path below the app's own prefix and connects anyway. Keep the rules for
clients that give up earlier.

**Claude Code is not in this group either.** It never asks the domain root: it follows the
`resource_metadata` pointer of the 401 and reads both documents below the app's own prefix.
It is a separate case for another reason, its client id metadata document, and that case is
measured in its own section above.

## Three things that will go wrong

### 1. `421 Misdirected Request`

Symptom: the client cannot connect at all, and the server answers `POST /mcp` with a 421
before any MCP message. `GET /health` keeps answering 200, which is the confusing part:
`/health` is a plain route and is deliberately not behind the host check, so a healthy
probe says nothing about whether a client can connect.

Cause: the `Host` header of the request is not in the allow list. This check runs in the
transport layer, before any code of this server, so there is no friendly error message.

Fix: set `NC_MCP_ALLOWED_HOSTS` to the name the client actually uses, including the port if
the client was given one. In the ExApp mode this is rarely needed any more: the host of
`NEXTCLOUD_URL` and the host of the public address of this app are in the list already
(issue #4), so a 421 there means the proxy sends a third name. Reproduce and verify against
the MCP endpoint, never against `/health`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Host: mcp.example.com' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  http://127.0.0.1:8765/mcp
```

`421` means the name is missing from the allow list. `200` means it is accepted.

### 2. `Session terminated` or a client that reconnects in a loop

Symptom: an older client connects, works for one call and then reports a terminated
session, or reconnects on every message.

Cause: this server is stateless by design, and it keeps no session between requests. That
is what makes a restart survivable, and it is what some clients built against the 2025 spec
do not expect. It is also the exact bug behind `nextcloud/context_agent#227`.

Fix: update the client, or use stdio. Do not work around it by adding session state to the
server: a session store would break the restart guarantee for everyone. If the client is
based on the MCP SDK 1.x, note that both protocol generations are served from the same
endpoint, so an up to date SDK 1.x client works too.

### 3. `429 Too Many Requests` after a wrong app password

Symptom: you fixed the password, and the server still answers with an error. A minute later
it works again.

Cause: Nextcloud counts failed logins per source IP and throttles that IP with an
increasing delay. A remote MCP server is a single IP for all of its users, so a handful of
wrong attempts can slow down everybody behind it.

Fix: wait, then retry with the correct app password. Create a fresh one instead of guessing.
On a server you control, an administrator can list and clear the entries with
`occ security:bruteforce:attempts` and `occ security:bruteforce:reset <ip>`. Do not disable
the protection on a production instance.

## Checking that it works

Ask the assistant for something that needs exactly one tool, for example "list the files in
the root of my Nextcloud". A correct answer means credentials, transport and permissions are
all in place. If the assistant answers with a plausible but invented list, the tool was not
called at all: check the tool list in the client first.

Remember what the tools cannot do. Nothing here deletes, overwrites, moves or re-shares
anything, and `files_search` matches names, not the text inside documents. See the
"What this server cannot do" section of the [README](../README.md).
