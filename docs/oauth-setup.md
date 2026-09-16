# OAuth 2.1 setup

**Status:** proven on a local HaRP topology
**Measured on:** 2026-08-16
**Scope:** turning on the OAuth 2.1 half of this app, so that an assistant such as Claude.ai
or ChatGPT connects through a browser sign in instead of a pasted app password. The
credential based ways stay as they are and are described in
[client-setup.md](./client-setup.md).

Everything in the Evidence section was executed against **Nextcloud 34.0.2** with
**AppAPI 34.0.0** and `ghcr.io/nextcloud/nextcloud-appapi-harp:release`, on the topology of
[exapp-install.md](./exapp-install.md). The outputs are copied verbatim from that run.

## Topology

An OAuth connection touches four components, and each of them answers a different part of
the flow. This is the way of one request, from the assistant to Nextcloud and back:

| Step | Who answers | What happens |
|------|-------------|--------------|
| 1. The first tool call | the ExApp | No token, so the MCP route answers `401` with `WWW-Authenticate` and a `resource_metadata` pointer. That answer is the whole discovery: everything after it is built from it. |
| 2. The protected resource document | the ExApp | `GET <public url>/.well-known/oauth-protected-resource/mcp`. It names the resource and the authorization server. |
| 3. The authorization server document | the ExApp | Three paths lead there, and only one of them works everywhere. See "The three discovery paths" below. |
| 4. Registration | the ExApp | `POST <public url>/register`. Claude.ai and ChatGPT register themselves; there is no client id an administrator has to create. |
| 5. The authorization request | the ExApp, then Nextcloud | `GET <public url>/authorize` opens a Nextcloud Login Flow v2 and sends the browser to the consent screen of this app. The user signs in **on Nextcloud's own pages**, second factor included. This app never sees a password. |
| 6. The consent screen | the ExApp | Who is asking, what they get, and two buttons. Approving produces a single use authorization code and sends the browser back to the client. |
| 7. The code exchange | the ExApp | `POST <public url>/token`. No Nextcloud call happens on this path, which is why it answers in milliseconds. |
| 8. Every later tool call | the ExApp, then Nextcloud | The bearer is checked against this app's own store, and the tool call runs against Nextcloud as the user who signed in. |
| 9. Ending the connection | the ExApp, then Nextcloud | `POST <public url>/revoke`, or the user removes the entry under Settings, Security, Devices and sessions. |

Two components sit in front of all of this and are not optional. The reverse proxy of the
installation routes `/exapps/*` to HaRP, and HaRP strips the `/exapps/mcp_connector` prefix
before the container sees a request. Both matter for the discovery paths below.

### The three discovery paths

A client that has read the protected resource document has to find the authorization server
document. There is no pointer for that step, only three constructed paths, and a client
tries them in this order:

| # | Path | Who owns it | Answers |
|---|------|-------------|---------|
| 1 | `<nextcloud>/.well-known/oauth-authorization-server/exapps/mcp_connector` | Nextcloud | `404`, unless a reverse proxy rule maps it back (Install, below) |
| 2 | `<nextcloud>/.well-known/openid-configuration/exapps/mcp_connector` | Nextcloud | `404`. There is no rule for this one, because a client that tries it also tries path 3. |
| 3 | `<nextcloud>/exapps/mcp_connector/.well-known/openid-configuration` | this app | `200`, always, with no administrator action |

Path 3 survives a stripped prefix, which is why it is the one that works out of the box.
Paths 1 and 2 land on the domain root, where Nextcloud's own well-known controller matches
a single path segment only. The two rules in the Install section exist for clients that try
the canonical path and stop.

## Install

### 1. The public URL, and it is not optional

`NC_MCP_PUBLIC_URL` is the address this app is reachable under from the outside, without a
trailing slash:

```
https://cloud.example.com/exapps/mcp_connector
```

The authorization server calls itself by this value. It is the `issuer` of the metadata
document, the `resource` of the protected resource document and the target of the
`resource_metadata` pointer in every `401`. Left unset, all three name the documented
default `http://127.0.0.1:8765`, no client can reach it, and the connection fails at the
first step with "could not discover authorization server".

The deploy daemon injects a variable into the ExApp container only if the manifest declares
it. `appinfo/info.xml` declares this one and every switch below; an installation sets the
value at registration time:

```
occ app_api:app:register mcp_connector \
  --env "NC_MCP_PUBLIC_URL=https://cloud.example.com/exapps/mcp_connector"
```

For the local topology of `scripts/bootstrap_exapp.sh` the value is set automatically and
can be overridden with `NC_EXAPP_PUBLIC_URL`.

An installation from the app store has no way to pass a variable, which is what section 3
below is for: the same address can be entered in Nextcloud itself, and what is entered there
wins over this variable.

### 2. The three switches of AUTH-07

All three are optional, and the shipped state is the plug and play one:

| Variable | Default | What it does |
|----------|---------|--------------|
| `NC_MCP_OAUTH_DCR` | on | Dynamic client registration (RFC 7591). Claude.ai and ChatGPT need it to connect without an administrator. Switched off, `/register` refuses and the discovery document stops advertising the endpoint. |
| `NC_MCP_OAUTH_ALLOWLIST_ONLY` | off | Only clients named below may authorize. **An empty list with this switch on closes the door for everyone**, which is deliberate: an administrator who armed the switch and named nobody meant to close it. |
| `NC_MCP_OAUTH_ALLOWED_CLIENTS` | empty | Comma separated client ids **or redirect URIs**. Only read when the allowlist is on. A redirect URI is the entry an administrator can write down in advance, because a self registered client's id is random. |

A value that is neither on nor off keeps the default and says so in the log, instead of
guessing.

There is a fourth switch, `NC_MCP_OAUTH_CIMD`, for the second way a client can identify
itself. It is documented in "Client ID Metadata Documents" below, together with the way
itself and with what the two switches do to each other. It is a field of the administration
form as well, from release 0.1.3 on.

### 3. Administrator settings in Nextcloud

Since version 0.1.1 the values above can also be set inside Nextcloud, without any deploy
variable. A store installation needs this: with a single Docker daemon, Nextcloud 34 enables
an ExApp without asking for deploy options, so `--env` never happens and every declared
variable arrives empty.

The form sits in **Administration settings, Security, MCP Connector** and carries six
fields:

| Field | Config key | What it sets |
|-------|------------|--------------|
| Public address of this connector | `public_url` | `NC_MCP_PUBLIC_URL` |
| Allow apps to register themselves | `oauth_dcr` | `NC_MCP_OAUTH_DCR` |
| Let apps identify themselves by their own document | `oauth_cimd` | `NC_MCP_OAUTH_CIMD` |
| Only allow the clients listed below | `oauth_allowlist_only` | `NC_MCP_OAUTH_ALLOWLIST_ONLY` |
| Allowed clients | `oauth_allowed_clients` | `NC_MCP_OAUTH_ALLOWED_CLIENTS` |
| Let assistant apps send Talk messages | `talk_send` | `NC_MCP_TALK_SEND` |

**Not every field of this form is about OAuth.** The last one is not: it decides whether
`talk_send` may post a message into a Talk conversation at all, for every account of this
instance and regardless of what an account is allowed to do in Talk itself. It is on unless
it is switched off, reading conversations and their history is never affected by it, and like
the other five it takes effect after this app has been disabled and enabled again.

**The last field is new and takes effect with 0.1.4**, together with the Talk family it
belongs to. The field above it arrived with 0.1.3: in 0.1.2 the form carries four fields and
`NC_MCP_OAUTH_CIMD` can only be set as a deploy variable, which a store installation never
receives, so on such an installation that switch could not be set at all. The document way
itself is not in 0.1.2 either, so nothing was reachable and unswitchable in a released
version.

The config key of a field is the id of the field itself, without a prefix: AppAPI stores a
declarative settings value under that id, and the app reads the same keys back over the
ExApp configuration channel.

**Precedence: the value stored in Nextcloud wins, then the `NC_MCP_*` variable of the deploy
environment, then the default in code.** A field left empty, or filled with something this
app cannot use, is not a value at all: the variable and then the default keep working, and
the reason is written into the container log without repeating what was entered. An address
with a fragment, with credentials in it, without a scheme or with an impossible port is
refused for that reason, because it would become the `issuer` of the metadata document.

**The address has to use `https`, unless it points at loopback** (`localhost`, `127.0.0.1` or
`[::1]`, which is what a local development setup uses). RFC 8414 requires it for the issuer of
an authorization server, and a value that the authorization server cannot use as its issuer is
dropped when the container starts. The app then keeps running with the documented default and
says so on its connections page, instead of restarting forever with an admin form that
Nextcloud no longer serves. The value you entered stays in the form, so you can correct it
there.

**A change takes effect after the app is disabled and enabled again:**

```
occ app_api:app:disable mcp_connector
occ app_api:app:enable mcp_connector
```

The values are read exactly once, when the container starts. That is deliberate: reading
them per request would cost a Nextcloud round trip on every single request, and caching them
in the process would be state that outlives a request. The reactivation is the price, and it
is the only step of this form that is not obvious.

**One cycle is enough, and it is measured.** The cycle above stops and starts the same
container, and the start after it reads those values, so a change needs exactly one
disable and enable, never two. That was measured against Nextcloud 34.0.2 with AppAPI 34.0.0
behind HaRP, together with the log line described next, instead of being assumed.

**What the container log says on the very first start.** Before Nextcloud has this app on
`enabled`, the read of these values answers `401`, and the container says so in one
information line. That is the expected answer and not a failure of the installation: AppAPI
accepts the app secret and then refuses the call because the app is not activated yet, and
`enable` happens after `init`, so every first start after an installation sits inside that
window. There can be no stored value at that moment either, because the app did not exist
before. The app keeps serving with the deploy environment, and the values are read again on
the next start. If the same line appears on a start that followed an `enable`, it means
something else and is worth looking at: the app secret inside the container is then not the
one Nextcloud stored for this app.

One consequence worth knowing on an installation that has always used `--env`: as soon as
the form is saved for the first time, Nextcloud stores a concrete value for both checkboxes,
and from then on those two beat the variables. Clear the fields if the deploy environment
should stay in charge.

**On a public instance, decide about self registration before the first client connects.**
The shipped state allows any app to register itself, which is what lets Claude.ai and
ChatGPT connect without an administrator. Either switch "Only allow the clients listed
below" on and name the clients, or switch self registration off. Both switches are in the
same form, and the sentence stands at the field as well.

**An installation without a public address keeps running on purpose.** It does not stop with
an error at startup any more, because a container that stops never becomes `enabled`, so the
form above would never be registered and there would be no place to enter the address. The
container writes one error line naming this form, and the connections page of every user
says the same thing until the address is set.

### 4. The two reverse proxy rules for the canonical root paths

These are **optional**, and that is measured, not assumed: with both rules switched off,
Claude.ai still connects, because it falls back to path 3 of the discovery table (see "Are
the two reverse proxy rules required?" in the section on hosted connectors). A
specification compliant client reads the `resource_metadata` pointer out of the `401` and
finds everything from there. Add the rules if a client reports that it cannot find the
authorization server, and add them before a first public launch, because they cost nothing
and remove a whole class of support requests.

Caddy:

```caddyfile
route /.well-known/oauth-protected-resource/exapps/mcp_connector/mcp {
	rewrite * /exapps/mcp_connector/.well-known/oauth-protected-resource/mcp
	reverse_proxy appapi-harp:8780
}

route /.well-known/oauth-authorization-server/exapps/mcp_connector {
	rewrite * /exapps/mcp_connector/.well-known/oauth-authorization-server
	reverse_proxy appapi-harp:8780
}
```

nginx:

```nginx
location = /.well-known/oauth-protected-resource/exapps/mcp_connector/mcp {
    proxy_pass http://harp:8780/exapps/mcp_connector/.well-known/oauth-protected-resource/mcp;
    proxy_read_timeout 1800s;
}

location = /.well-known/oauth-authorization-server/exapps/mcp_connector {
    proxy_pass http://harp:8780/exapps/mcp_connector/.well-known/oauth-authorization-server;
    proxy_read_timeout 1800s;
}
```

Both use an exact match, `route /path` in Caddy and `location =` in nginx, so they rewrite
these two strings and nothing else. No Nextcloud path outside them changes behaviour, and
both rules have to stand before the general `/exapps/*` rule, because the first match wins.

### 5. What the user enters

The URL of the connector, exactly, with `/mcp` and without a trailing slash:

```
https://cloud.example.com/exapps/mcp_connector/mcp
```

That string has to match the `resource` of the protected resource document character for
character. A trailing slash is a different resource and the connection fails before the
first tool call.

### 6. What the hosted connectors actually send

Measured against the staging instance on **2026-08-16**, one live connection per client,
read out of the access log and out of the authorization request. This table replaces the
values the research had taken from community sources; where they differ, the measurement
wins.

| | Claude.ai | ChatGPT |
|---|---|---|
| Where the button is | Settings, Connectors, "Add custom connector" | Settings, Security and sign in, "Developer mode", then the plugins page shows "Create app" |
| Redirect URI | `https://claude.ai/api/mcp/auth_callback`, one fixed address | **`https://chatgpt.com/connector/oauth/<token>`, minted per connector.** Measured: `https://chatgpt.com/connector/oauth/GxdvJstdJeOS` |
| `scope` at `/authorize` | `nextcloud` | `offline_access nextcloud`, both entries of `scopes_supported` |
| `resource` (RFC 8707) | sent | sent |
| PKCE | `S256` | `S256` |
| Discovery documents it reads | the protected resource document and the authorization server document | the same two, **plus `<public url>/.well-known/openid-configuration`** |

Two consequences for an administrator. **The ChatGPT redirect URI cannot be put on an
allowlist in advance**: it does not exist until the connector is created in ChatGPT, so
with `NC_MCP_OAUTH_ALLOWLIST_ONLY` on, the address has to be read out of the first refused
attempt (it is in the registration request) and added afterwards. Claude.ai has one fixed
address and can be listed before the first connection. **And a connector may ask for both
advertised scopes**, which is why a registration of this server is recorded with both, see
pitfall 7.

## Client ID Metadata Documents: accepted since 0.1.3, next to registration

In the repository since **2026-08-20** and released with **0.1.3**, so an installation running
0.1.2 or older behaves the way the sections above describe and nothing else.

**Measured live on 2026-08-20 against Claude Code 2.1.233**, on a Nextcloud 34.0.3 instance
running this build: the client identifies itself with the document address alone, no row is
ever registered by a `/register` call, the consent screen names `claude.ai` as the host of
that client id, the code exchange answers `200`, and `files_list` comes back with the real
content of the signed in account. The written row carries an empty secret and the two
portless return addresses of the document, with a freshness window of five minutes taken
from the `Cache-Control` of the answer.

The three controls were measured on the same instance in the same session, each with the
outbound socket counted rather than blocked:

- **Registration off closes this way with it.** With `NC_MCP_OAUTH_DCR=0` the document
  address is answered `400 Automatic registration is off`, `/register` is `404`, the metadata
  document no longer advertises either way, and **no packet left the instance**: zero sockets
  to port 443 over twelve seconds, against four socket states in the identical run with the
  switch on.
- **This switch alone does not touch registration.** With `NC_MCP_OAUTH_CIMD=0` the document
  address is refused and no request goes out, while `/register` still answers `201` and the
  client it mints reaches the consent screen. **What the refused client sees is the page
  `This link has expired`**, the same page an unknown or long gone registration gets. That is
  the honest limit of a rule this app keeps on purpose: the error page is chosen from the
  administrator's own configuration alone, never from anything the request says about itself,
  because a page that told a caller which check fired would answer whoever is guessing client
  ids. Registration is open in this configuration, so the page cannot name it as the reason
  either. A client of this shape can still connect the other way, by registering itself; a
  user who reads that page and expected the document way should ask the administrator about
  this switch.
- **The allowlist applies to this way exactly as it applies to registration.** Armed with an
  empty list it refuses the document address and a registered, unlisted client with the same
  page, `This app is not allowed`; with the document address on the list that client passes
  and the unlisted one still does not.

Every claim of that session is repeated here with the command that produced it, rather than
with a pointer at a neighbouring file: the notes of a release are removed once the release is
out, and a proof that leans on them stops being a proof.

**Measured live on 2026-08-25 again, against Claude Code 2.1.233**, on the same Nextcloud
34.0.3 topology and this time against the 0.1.9 candidate, which answered as `mcp_connector
0.1.9 [enabled]` from the image `127.0.0.1:5000/mcp_connector:0.1.9` with the manifest digest
`sha256:1183f8455c5f2ab420ee3d4b7eb8e0b2c207610c08dcd12b943ae78920759c47`. The client chose
this way on its own: the container log carries one `GET /authorize` whose `client_id` is the
percent encoded address `https://claude.ai/oauth/claude-code-client-metadata` and not a random
identifier, and `docker logs <container> | grep -c 'POST /register'` answers `0` over the whole
life of that container. The consent screen named `claude.ai` as the host of that client id,
`POST /token` answered `200`, and `files_list` on `/` came back with the real content of the
signed in account, the two marker files of the permission fixture included. The row written in
the client table carries an empty secret and the two portless return addresses of the document,
with a freshness window of `300` seconds taken from the `Cache-Control` of the answer, and the
same fetch executed inside the running container reports `HTTP 200, 317 bytes, lifetime 300s`.
This run is newer than the two review fixes that moved the refetch off the hot paths and that
ask the allowlist before the fetch, which the 2026-08-20 run above predates.

- **The switch was measured again on that candidate, and put back.** With
  `NC_MCP_OAUTH_CIMD=0`, set through the administration form and applied by disabling and
  enabling the app once, `GET /authorize` with the document address answered `400` in `0.065`
  seconds with the page `This link has expired`, the authorization server document stopped
  carrying the field while the registration endpoint stayed, and the counter inside the
  container saw **zero** sockets to port 443 over twelve seconds, against **five** socket
  states of the same remote address in the identical run with the switch on. The counter reads
  `/proc/net/tcp` and `/proc/net/tcp6` in a loop, about 1700 polls a second, and it is the
  same code in both runs. The configuration value was deleted afterwards and the document
  advertises the field again.

A client of this kind does not register here at all. Its client id **is** the https address
of a small JSON document it publishes itself, this server reads that document once and takes
the client information out of it. That is the way the MCP specification 2026-07-28 prefers,
and it is the way Claude Code identifies itself:

```
https://claude.ai/oauth/claude-code-client-metadata
```

**It is an addition and not a replacement.** Dynamic registration is untouched, both ways
run next to each other, and the hosted connectors of the table above stay on registration:
Claude.ai and ChatGPT register themselves and neither of them publishes such a document.
Everything a registration goes through, a document goes through as well, in the same code
and not in a copy of it: only `https` return addresses and loopback ones (D-35), an
inadmissible address dropped and the admissible ones kept, the allowlist asked in the same
four places, and no shared secret, because a client of this kind is public by definition of
the draft.

### The switch, and what the two switches do to each other

| Variable | Default | What it does |
|----------|---------|--------------|
| `NC_MCP_OAUTH_CIMD` | on | A client may identify itself by the address of its own published document. Switched off, such a client is refused before any outbound request happens, and the authorization server document stops advertising the capability. |

**Switching registration off switches this off with it.** `NC_MCP_OAUTH_DCR=0` closes both
ways, because a closed door that can be walked around through the other spelling is not a
closed door. The other direction does not hold: `NC_MCP_OAUTH_CIMD=0` leaves registration
exactly as it was. Both switches are fields of the administration form of section 3 as
well, the second one from release 0.1.3 on, and the same precedence applies there.

### The allowlist is more useful with this way than with registration

With registration the client id is a random identifier the server mints when the client
first appears, so an administrator cannot write it down in advance and has to fall back to
the redirect URI. With a document the client id is a stable, published URL, which means a
closed instance can name the clients it wants before any of them has ever connected:

```
NC_MCP_OAUTH_ALLOWLIST_ONLY=1
NC_MCP_OAUTH_ALLOWED_CLIENTS=https://claude.ai/oauth/claude-code-client-metadata
```

An unlisted client of this kind is refused with the same page an unlisted registration gets.
**Nothing is written for it**: since the allowlist is asked before the fetch, an unlisted
document address never becomes a row at all, so there is no stored refusal to survive a
restart, and no unauthenticated caller of `/authorize` can make this server fetch a URL of
their choosing in the hardest configuration it has. A registration that an administrator
blocked afterwards is the other case, and that block is stored and does survive a restart.

### What the fetch of a document is allowed to do

The client id decides where this process connects to, which is the one place in this app
where a request chooses the target of an outbound request of ours. The boundaries are fixed
in code, none of them is a setting, and every one of them is a refusal rather than a
fallback:

- `https` only, a path is required, no fragment, no user info, no `.` or `..` segment in the
  path
- the target must be a public address: private, loopback, link local, reserved, multicast
  and unspecified addresses are refused, **also after the name has been resolved**, and a
  name that resolves to one good and one refused address is refused entirely
- the request goes to the resolved address with the original name in the `Host` header and
  in the TLS handshake, so a second resolution cannot move the target after the check
- 5120 bytes, the recommendation of the draft, enforced while reading and not after it
- 5 seconds to connect and 5 seconds to read
- redirects are not followed: a `3xx` is a refusal, because a redirect is a second target
  that nobody checked
- the answer is kept for as long as its own cache header asks for, between five minutes and
  one hour; **failures are never kept**, which the draft forbids in those words, and the
  flooding of this route is handled by the throttle of `/authorize` instead

**Where the reading is renewed, and where it is not.** Only `/authorize` reads a document
again. It is the one path with a person and a browser waiting on it, so it is the one path
that may wait on a foreign host at all. `/token`, `/revoke` and every tool call use the
identity as it was read and stored, whether its window has passed or not, and they never make
an outbound request of their own. Three consequences, and they are a trade this app makes on
purpose rather than an oversight:

- A connection that works keeps working while the host of the document is unreachable. An
  outage at `claude.ai` does not end a running session, and it can never sit inside a tool
  call or a token exchange.
- A document that was **withdrawn or changed** does not reach a session that already exists.
  The identity was bound once, byte for byte, and the next `/authorize` of that client is what
  reads the new version. So a document is not a revocation channel.
- **Ending access is a revocation, not a document edit.** A user disconnects the app on the
  connections page of this connector, or an administrator removes the client; both take effect
  at once, on the very next request. An administrator who wants such a client out of an
  instance for good switches it off or removes it from the allow list, which is asked on every
  request as well.

Every policy question is asked on every request either way: a blocked client, an emptied allow
list and a switch an administrator closed reach `/token`, `/revoke` and every tool call
immediately. It is the identity behind an unchanged client id that can be one reading old, and
never the permission to use it.

### What the consent screen says about such a client, and what it does not

The specification asks for two displays, and this app does both. The consent screen names
the **host of the client id** as an entry of its own next to the id itself, and it carries a
second warning when every return address of the client is on the computer the user is
sitting at.

The second one exists because of a limit the specification states itself: "Client ID
Metadata Documents cannot prevent `localhost` URL impersonation by themselves." A document
proves who controls the URL it is published at. It does not prove which program on a user's
machine is listening on a loopback port, and any program on that machine can name a foreign
client id. So the screen says what is known and what is not, and it does not call such a
client confirmed by anybody. No image out of a document is ever shown either, because a logo
address of a foreign domain would make the user's browser call whoever wrote the document.

## Evidence

All commands were run on **2026-08-16** against Nextcloud 34.0.2 and AppAPI 34.0.0. The
runnable form of the whole table is:

```
set -a && . ./.env.exapp && set +a
uv run --no-sync python scripts/oauth_flow_check.py \
    http://127.0.0.1:8081/exapps/mcp_connector --measure
```

### 1. The flow, step by step

```
[step 1] POST /mcp -> 401 | cache_control=no-store | www_authenticate=Bearer error="invalid_token", error_description="Authentication required", scope="nextcloud", resource_metadata="http://127.0.0.1:8081/exapps/mcp_connector/.well-known/oauth-protected-resource/mcp"
[step 2] GET harp:/.well-known/oauth-protected-resource/mcp -> 200 | content_type=application/json | cache_control=no-store
[step 2] GET harp:/.well-known/openid-configuration -> 200 | content_type=application/json | cache_control=no-store
[step 2] GET harp:/.well-known/oauth-authorization-server -> 200 | content_type=application/json | cache_control=no-store
[step 2] GET php-proxy:/.well-known/oauth-protected-resource/mcp -> 200 | content_type=application/json | cache_control=no-store
[step 2] GET php-proxy:/.well-known/openid-configuration -> 200 | content_type=application/json | cache_control=no-store
[step 2] GET php-proxy:/.well-known/oauth-authorization-server -> 200 | content_type=application/json | cache_control=no-store
[step 2] both proxy paths serve all three documents byte for byte the same
[step 3] GET root:/.well-known/oauth-protected-resource/exapps/mcp_connector/mcp -> 200 | content_type=application/json | rewrite=active
[step 3] GET root:/.well-known/oauth-authorization-server/exapps/mcp_connector -> 200 | content_type=application/json | rewrite=active
[step 4] POST /register -> 201 | cache_control=no-store | client_id=cf25d0ac-030...
[step 5] GET /authorize -> 302
[step 5] GET /authorize/consent -> 200 | cache_control=no-store | signed_in=True
[step 5] POST /authorize/decide -> 400 | identity=none
[step 5] POST /authorize/decide -> 200 | identity=the session cookie of the sign in | code=present | state=matches | iss=http://127.0.0.1:8081/exapps/mcp_connector
[step 6] POST /token -> 200 | cache_control=no-store | fields=access_token,expires_in,refresh_token,scope,token_type | seconds=0.04
[step 7] POST /mcp -> 200 | tools=15 | transport=streamable-http
[step 7] tool notes_create -> 200 | note_id=note:354 | as_user=alice
```

The code exchange took **0.04 seconds**. A connector allows ten, and this path makes no
Nextcloud call at all, which is the reason.

**Every line above is from one run against the current code** (2026-08-16, Nextcloud
34.0.2, AppAPI HaRP `release`). Two of them are worth reading twice.

`tools=15` is what that run listed, and it is left as it was recorded. The set is 20 today:
`prepare_context` and the two pairs of Tables and Talk tools were added after this run, and
the number a release has to list is held by `tests/contract/test_tool_surface.py`, never by
this page.

The decision is `POST /authorize/decide` and it appears **twice**, which is the CR-01 relay
walked over the full chain. The first one is sent by the caller that started the flow: it
holds the flow id and the anti forgery value derived from it, which used to be the entire
authorisation of this request, and it has no Nextcloud account. It is refused with `400`
and no code exists. The second is sent by the browser that just signed in, carrying nothing
but its Nextcloud session cookies, and that one is granted. The walker refuses to continue
if the first is granted.

The answer is `200` with a page that carries the return address as a link and as a
`meta refresh`, not a `302`: Chromium and WebKit check `form-action` against the target of
a redirect that follows a form submission, and every page here carries `form-action 'self'`,
so a redirect never arrived in those browsers (CR-03). The address, the code, the state and
the `iss` are what the line shows. The run is repeated against the staging instance in plan
03-09.

### 2. The canonical root paths, with and without the two rules

The rules of the Install section were removed from the running reverse proxy and put back:

```
docker exec nc-mcp-exapp-caddy caddy reload --config /tmp/Caddyfile.norewrite --adapter caddyfile

/.well-known/oauth-protected-resource/exapps/mcp_connector/mcp        status=404
/.well-known/oauth-authorization-server/exapps/mcp_connector          status=404
/.well-known/openid-configuration/exapps/mcp_connector                status=404
/exapps/mcp_connector/.well-known/openid-configuration                status=200
/exapps/mcp_connector/.well-known/oauth-protected-resource/mcp        status=200

docker exec nc-mcp-exapp-caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

/.well-known/oauth-protected-resource/exapps/mcp_connector/mcp        status=200
/.well-known/oauth-authorization-server/exapps/mcp_connector          status=200
```

Without the rules the two canonical root paths are answered by Nextcloud with 404, exactly
as the third discovery path predicted, and the path appended variant keeps working either
way. That is what makes the rules an improvement rather than a requirement. The same
measurement was repeated with a real hosted client instead of curl, see "Are the two
reverse proxy rules required?" below: Claude.ai connects without them.

### 3. Success Criterion 5: the number of Nextcloud round trips

```
[sc 5] 5 accepted MCP calls -> 6 Nextcloud requests (1.2 per call): ['GET /index.php/apps/app_api/harp/user-info?appId=mcp_connector']
[sc 5] 5 refused MCP calls -> 5 Nextcloud requests (1.0 per call): ['GET /index.php/apps/app_api/harp/user-info?appId=mcp_connector']
[sc 5] POST /token -> 429 | attempts=11 | retry_after=300
[sc 5] GET /ocs/v2.php/cloud/user -> 200 | as_user=alice
```

Three numbers, and they are the ones that multiply with the number of users:

| Measurement | Result |
|-------------|--------|
| Nextcloud requests per accepted MCP request | **1** (six HTTP requests, one session `initialize` plus five `tools/list`, produced six lookups) |
| Nextcloud requests per refused MCP request | **1** |
| Refused token requests before the throttle answers 429 | **11**, with `Retry-After: 300` |
| Login flows one source may open per five minutes | **20** per path class, refused or not (CR-02) |

**Every request that carries an `Authorization` header costs exactly one Nextcloud round
trip, and this application cannot switch it off.** HaRP resolves a user for any request
with that header, and its session cache only covers cookies, so an OAuth bearer is looked
up on every single call. The verification of the token itself costs nothing: it is one
indexed lookup in this app's own store, answered from a five second process cache.

The counter check the research asks for holds: after eleven refused token requests and five
MCP requests with bearers this server never issued, the test user signs in normally
(`GET /ocs/v2.php/cloud/user -> 200`). An unknown bearer produces no brute force entry in
Nextcloud, so nobody is locked out by a flood.

### 4. A restart is not a disconnection

```
uv run --no-sync pytest -m integration tests/integration/test_oauth_flow_exapp.py -q
6 passed
```

`test_the_same_token_still_works_after_the_container_restarted` restarts
`nc_app_mcp_connector` with `docker restart`, waits until the app answers again and calls
the same tool with the same token. Three things have to survive for it to pass: the store
file on the persistent volume, the data key in Nextcloud's ExApp configuration, and the
ability to read that key back from a cold process.

### 5. Two accounts stay two accounts

`test_two_tokens_stay_two_accounts_over_the_whole_chain` builds one connection for each of
two users, writes a file as the first one and then asks the second one for it four ways:
`files_search`, `unified_search`, and `files_read` with the exact path. All three answer
empty or refuse, and the refusal carries no content of the file. The positive control runs
in the same test: the owner finds her own file at the same moment, so an empty answer
cannot be an empty instance.

### 6. Revocation, and what it removes

```
new Devices-and-sessions entries after the connection: [108]
revoke -> 200
still there after the revocation: []
removed by the revocation: [108]
```

Read with `occ user:auth-tokens:list alice`, which is the command line form of Settings,
Security, Devices and sessions. The Nextcloud app password behind the connection is really
handed back, not only marked as gone in this app's store.
`test_a_revocation_is_a_401_with_the_same_pointer_and_a_reconnection_works` adds the other
half: immediately after the revocation the next tool call is a `401` whose
`WWW-Authenticate` is byte for byte the one an anonymous request gets, and a complete new
connection can be built right away.

### 7. Success Criterion 3: the onboarding without OAuth

```
[sc 3] GET /connect -> 200 | cache_control=no-store
[sc 3] POST /connect -> 200
[sc 3] GET /connect/wait -> 400 | identity=none | credential_handed_over=False
[sc 3] GET /connect/wait -> 200 | identity=the session cookie of the sign in | signed_in_as=alice | credential=72 characters, shown once
[sc 3] GET /connect/wait -> 400 | credential_shown_again=False
[sc 3] POST /mcp -> 200 | auth=the credential from the page | server=uvicorn
```

The first of the three loads is the CR-01 relay on this surface: the caller that started
the flow asks for its result, holding the flow id and no Nextcloud account. It gets 400 and
no credential, and the app password the finished sign in produced is handed back to
Nextcloud in the same request (D-34), which is why the successful half below needs a flow
of its own rather than a second try on that one.

The credential is shown exactly once: the second load of the same address answers 400 and
carries no credential, because the flow record is deleted the moment the result is
rendered. The credential works immediately as a Basic header against `/mcp`, and
`Server: uvicorn` is the proof that the answer came out of the ExApp container rather than
from the proxy in front of it.

The entry it creates carries the expected name prefix:

```
docker exec -u www-data nc-mcp-exapp-nc php occ user:auth-tokens:list alice
| 98  | MCP Connector: browser onboarding | 2026-08-16T04:08:10+00:00 | permanent | filesystem |
| 102 | MCP Connector: browser onboarding | 2026-08-16T04:09:07+00:00 | permanent | filesystem |
```

An OAuth connection appears in the same list under the name the client registered itself
with, prefixed the same way, for example `MCP Connector: OAuth flow check`.

### 8. The sign ins nobody finished are cleaned up

A sign in that Nextcloud completed but that nobody ever approved leaves a working app
password behind. This app has no cron, so the cleanup hangs on the authorization request:
each one hands back at most three of those credentials. Measured by waiting out the twenty
minute deadline and then driving ten authorization requests:

```
MCP Connector entries before the sweep: 25
MCP Connector entries after ten authorization requests: 24
handed back by the sweep: [104]
```

Entry 104 was the credential of a sign in that never became a connection. Nothing else in
that list was touched: a running sign in and a live connection are both left alone by
definition, which is why only one entry moved.

### 9. The CR-01 counter check: what HaRP resolves, and what a refusal costs

The CR-01 fix rests on one assumption, and this section is that assumption measured rather
than argued: **does HaRP name the Nextcloud account of a request that carries nothing but a
browser session cookie, and does it do so on a route that is PUBLIC?**

Two oracles were used, both of them routes this app already serves. On the PUBLIC `/mcp`
route the middleware takes the AUTH-01 path when the AppAPI header names a user and demands
a bearer when it does not, so `200` means "identity resolved" and `401` means "no identity".
On `/authorize/decide` a `400` carrying this app's own error page means the request reached
the app, and anything else means the proxy answered instead.

| Credential of the request | `/mcp` (PUBLIC) | `/authorize/decide` |
|---|---|---|
| none | `401`, no identity | `400`, the app's own page |
| Basic, app password | `200`, identity resolved | `400`, the app's own page |
| Basic, account password | `200`, identity resolved | `400`, the app's own page |
| **Nextcloud session cookie** | **`200`, identity resolved** | **`400`, the app's own page** |
| session cookie plus `requesttoken` | `200`, identity resolved | `400`, the app's own page |

So the answer is yes, and it holds for a PUBLIC route: HaRP signs every request it forwards
with `AUTHORIZATION-APP-API` and writes the account it resolved into it, empty when the
caller sent no credential. A browser session is resolved exactly like an app password. The
whole relay was then walked against the running instance with three actors, and the
identity check is what separates them:

| Actor | `POST /authorize/decide` | `GET /connect/wait` |
|---|---|---|
| the caller that started the flow, no account | `400`, no code | `400`, no credential |
| `mallory`, a real session, the wrong account | `400`, no code | `400`, no credential |
| `alice`, the session that signed in | `200`, code issued | `200`, credential shown once |

**The access level this route must not carry.** The first shape of the CR-01 fix declared
`/authorize/decide` as `access_level` `USER`, which made HaRP refuse the anonymous case
itself with `403`. That is a denial of service of the whole app, and it was measured from a
cold HaRP:

```
attempt  1: anonymous POST /authorize/decide -> 403 | GET /.well-known/oauth-authorization-server -> 200 | POST /mcp -> 401
...
attempt  9: anonymous POST /authorize/decide -> 403 | GET /.well-known/oauth-authorization-server -> 200 | POST /mcp -> 401
attempt 10: anonymous POST /authorize/decide -> 403 | GET /.well-known/oauth-authorization-server -> 502 | POST /mcp -> 502
attempt 11: anonymous POST /authorize/decide -> 502 | GET /.well-known/oauth-authorization-server -> 502 | POST /mcp -> 502
```

HaRP records every refusal of a `USER` route in a blacklist of its own
(`HP_BLACKLIST_COUNT`, ten by default, inside `HP_BLACKLIST_WINDOW`, 300 seconds), and a
banned address is answered before the access level of the requested route is even looked
at. The tenth refusal therefore takes **every route of this app** away from that caller,
discovery documents and `/mcp` included, and it comes back 300 seconds after the last one
(measured: reachable again after five minutes, no restart needed). Refusals are this route's
normal traffic, not an anomaly: the relay attempt itself, a browser whose session expired
behind an open consent screen, a resubmitted form, and the negative probe
`scripts/oauth_flow_check.py` sends on every run. Two runs of the integration suite were
enough to lock the runner out, which is how this was found.

With the route PUBLIC, the same sequence stays inside this app's own throttle, which is
bounded per path class instead of per app:

```
attempt  1..10: anonymous POST /authorize/decide -> 400 | GET /.well-known/oauth-authorization-server -> 200
attempt 11..14: anonymous POST /authorize/decide -> 429 | GET /.well-known/oauth-authorization-server -> 200
```

Nothing is given up for that. HaRP resolves the account either way, and the comparison in
the app is the only check that can separate the two accounts anyway: the relay attacker of
CR-01 holds a valid Nextcloud account too, so the question is never whether the caller is
signed in, it is who they are signed in as.

**What an administrator takes from this.** If a route of an ExApp produces refusals as part
of its normal operation, it must not be declared `USER`. `HP_BLACKLIST_COUNT` and
`HP_BLACKLIST_WINDOW` are environment variables of the HaRP container and can be raised,
but that is the deploy daemon's configuration and not something this app may assume.

## End to end with hosted connectors

Everything above was measured through a proxy chain that we control on both ends. This
section is the other proof: three real clients, none of which knows anything about this
project, pointed at a public instance and left to do whatever they do.

Instance: `https://nc-staging.infranode.dev`, a throwaway machine, Nextcloud 34.0.2,
AppAPI 34.0.0, ExApp 0.1.0. All runs on **2026-08-16**. The user entered nothing but the
resource URL; both OAuth fields of the client stayed empty and dynamic client registration
did the rest.

The tool counts in the tables below are the ones those runs listed against 0.1.0, which was
15. The set is 20 today, `prepare_context` and the two pairs of Tables and Talk tools having
arrived after those runs; the number is held by `tests/contract/test_tool_surface.py` and not
by a recorded run.

### Claude.ai: connected

| | |
|---|---|
| Result | connected, 15 tools listed, tool calls answer 200 |
| Client id issued by our DCR | one per connection, a UUID |
| Redirect URI | `https://claude.ai/api/mcp/auth_callback`, fixed |
| Discovery path used | canonical root path when it exists, otherwise the path appended variant, see below |
| `POST /token` | 23 ms |
| `POST /register` | 8 ms |
| `GET /authorize` | 143 ms, the redirect to the consent page |

```
POST 401  /exapps/mcp_connector/mcp
GET  200  /exapps/mcp_connector/.well-known/oauth-protected-resource/mcp
GET  200  /.well-known/oauth-authorization-server/exapps/mcp_connector
POST 201  /exapps/mcp_connector/register
POST 200  /index.php/login/v2                  (client name "MCP Connector: Claude")
GET  302  /exapps/mcp_connector/authorize
GET  200  /exapps/mcp_connector/authorize/consent
POST 200  /login/v2/poll                       (exactly one poll)
POST 200  /exapps/mcp_connector/authorize/decide
POST 200  /exapps/mcp_connector/token
POST 200  /exapps/mcp_connector/mcp            (repeatedly)
```

Nextcloud shows its own sign in page with its own security warning and names the client
"MCP Connector: Claude". The connection then appears in the account's Nextcloud sessions
under that name and can be ended there.

### ChatGPT: connected, after this server was fixed

The first attempt failed, and the failure was ours. The authorization request carried
`scope=offline_access nextcloud`, which is exactly what our metadata advertises, and our
own server answered `error=invalid_scope, error_description=Client was not registered with
scope offline_access`: registration granted only `nextcloud`. A client that believes the
metadata was refused by the server that published it. Claude.ai never asked for
`offline_access`, which is why it never hit this.

After the fix, the same connector was told to connect again, without being recreated, and
the run completed.

| | |
|---|---|
| Result | connected |
| Redirect URI | `https://chatgpt.com/connector/oauth/<token>`, minted per connector |
| `scope` at `/authorize` | `offline_access nextcloud`, both advertised entries |
| Extra document it reads | `<public url>/.well-known/openid-configuration` |
| `POST /token` | 37 ms |
| `iss` on the way back | our issuer, as required |

Custom MCP servers need developer mode in ChatGPT: Settings, Security and sign in,
"Developer mode", which carries an "increased risk" badge.

### Cursor: registrable since 0.1.2, and still refused at sign in

Cursor 3.2.16 needs no button either, it picks up `~/.cursor/mcp.json` on its own. Up to
and including 0.1.1 its registration was refused with `400 invalid_redirect_uri`, and
Cursor printed our sentence verbatim in its log: `redirect_uris must use https, except
loopback addresses of native clients`.

The reason was never the loopback address. Cursor registers three return addresses at once:

```
cursor://anysphere.cursor-mcp/oauth/callback
https://www.cursor.com/agents/mcp/oauth/callback
http://localhost:8787/callback
```

The first is a private-use URI scheme. This server admits https and loopback only, and it
used to read the whole field: one inadmissible entry refused a registration that also
carried two admissible ones. Measured against the live instance on 2026-08-16: the payload
above was refused, the same payload without the first entry was accepted, and
`http://127.0.0.1:49731/callback` on its own was accepted as well.

**Since 0.1.2 an inadmissible entry is dropped instead of refusing the registration.** The
body above is answered with `201`, and the answer names the two addresses that were
actually registered, which is what RFC 7591 section 3.2.1 asks of a registration response.
Nothing about the rule itself moved: the private-use address is not in the record, so a
later `/authorize` naming it is refused by the exact matching, and in the allowlist mode it
cannot carry a listing either. A body whose every address is inadmissible is still refused
with the same `400 invalid_redirect_uri`, because a client with no return target has
nowhere to be sent.

The rule stays deliberate. RFC 8252 lists private-use schemes as one of three legitimate
forms for native clients, but on a desktop no application owns a scheme exclusively, so
another program can claim it and receive the authorization code. What changed is only that
a client which also offers an admissible address no longer pays for the one it does not
need to use.

**The live run happened on 2026-08-20 against Cursor 3.2.16, and Cursor still does not
connect.** It registers now, and then it asks to be sent to the address that was dropped:

```
15:26:39  POST 201  /register    record: www.cursor.com/agents/mcp/oauth/callback, localhost:8787/callback
15:26:40  GET  400  /authorize   redirect_uri=cursor://anysphere.cursor-mcp/oauth/callback
15:28:46  GET  400  /authorize   the same request, second attempt
```

The browser gets the refusal page and no redirect, so no code and no token are issued and
the sign in page is never reached. Three things did *not* move, and each was measured with
the same client id rather than argued:

```
redirect_uri=http://localhost:8787/callback    -> 302 to the consent page
redirect_uri=http://localhost:51234/callback   -> 302 to the consent page   (port rule, RFC 8252 7.3)
redirect_uri=cursor://anysphere.cursor-mcp/... -> 400, refusal page
```

So it is not the instance, not the loopback port rule and not the partial registration. It
is D-35 doing what it says, plus one client side property that was not known before: Cursor
keeps its own three addresses after the `201` instead of taking the registered ones out of
the answer, and therefore cannot notice that one of them is not registered. RFC 7591 3.2.1
asks the server to answer with what it registered, and this server does; a client that
ignores that answer cannot be helped by dropping an address silently.

**What was decided about that, on 2026-08-20.** The dropped part is made visible where a
reader and a user actually need it, which is this documentation and the refusal page, and the
shape of the registration answer stays as it is. D-35 stays as it is too. The part that was
not done has a measured reason rather than a guess: RFC 7591 3.2.1 asks for the registered
metadata in the answer and does not forbid extension fields, but the answer model of the SDK
in use carries no extra field, measured on 2026-08-20. The only way to name the dropped
addresses in the answer would therefore be an intervention in the registration answer on the
auth path itself, for a field that no measured client reads. The record of that decision,
including the raw evidence of that measurement, is the backlog entry BL-14 of this project.
For Cursor today, the app password way in `docs/client-setup.md` is the answer, and the
refusal page names that way in words as well. The numbers behind the paragraph above were
measured on 2026-08-20 on a Nextcloud 34.0.3 topology: the registration answered `201` with
the two admissible addresses and dropped the `cursor://` one, and the `/authorize` that
followed carried exactly the dropped address and was refused with `400`.

### Are the two reverse proxy rules required?

**No, they are a courtesy.** With both rules commented out and Caddy restarted, a fresh
Claude.ai connection was forced (the stored authorization was cleared server side first,
see the note below) and it succeeded:

```
POST 401  /exapps/mcp_connector/mcp
GET  200  /exapps/mcp_connector/.well-known/oauth-protected-resource/mcp
GET  404  /.well-known/oauth-authorization-server/exapps/mcp_connector
GET  404  /.well-known/openid-configuration/exapps/mcp_connector
GET  200  /exapps/mcp_connector/.well-known/openid-configuration     <- the fallback
POST 201  /exapps/mcp_connector/register
… consent, token, tool calls, all 200
```

Claude.ai tries three locations in order and settles on the OIDC style path below the
issuer, which is ours and needs no rule. Keep the rules for clients that stop after the
canonical path; do not treat them as a prerequisite.

A trap when running this measurement yourself: the Caddyfile is bind mounted as a single
file, so an editor that replaces the inode (`sed -i` does) changes the file on the host
while the container keeps reading the old one, and `caddy reload` reloads the unchanged
file. Verify the edit arrived inside the container before believing the result.

### Removing a connector in the client does not revoke anything

Measured with Claude.ai: the connector was removed in the UI, then added again with the
same server URL. The first request afterwards was a tool call that answered 200. No 401,
no discovery, no registration, and the entry even kept its old id. The stored authorization
had simply survived on the provider side.

Tell your users the same thing this project's consent page says: access ends when it is
revoked in Nextcloud. `occ user:auth-tokens:list <user>` shows the connection under its
client name, and the app's own connections page ends it.

## Known pitfalls

The seven things that made this phase expensive, in the words of somebody who runs the
instance.

**1. The canonical root path belongs to Nextcloud, not to this app.** Two of the three
discovery paths sit on the domain root and are answered there with 404. Only the path
appended variant lives below the app's own prefix. If a client reports "could not discover
authorization server" although `/mcp` answers a proper 401, add the two reverse proxy rules.

**2. The authorization server document has no pointer.** The protected resource document is
found through a header; the authorization server document is found by guessing three paths.
There is nothing to configure that would make a client look somewhere else, which is why
the issuer in the document has to be exactly the value the URL was built from.

**3. The PHP proxy caches JSON.** A JSON answer without a `Cache-Control` header is cached
for an hour by AppAPI's PHP proxy. Every answer of the authorization server therefore
carries `no-store`, set by a wrapper over all of its routes rather than per handler. If you
put a cache in front of this app, exclude these routes.

**4. HaRP asks Nextcloud on every request with an `Authorization` header.** One MCP call is
one Nextcloud PHP request, measured above. Its session cache only covers cookies, so an
OAuth bearer never hits it. Plan for it in sizing; there is no setting that removes it.

**5. The Login Flow v2 answers its poll exactly once.** The moment Nextcloud says the sign
in is done, the credential exists and the record is gone. This app therefore stores the
authorization at that moment, before anybody has consented, and hands the credential back
when the user denies or never finishes. If you see an app password of this connector for a
connection that does not exist, it is either younger than twenty minutes or a failed
cleanup, and the app remembers the second case.

**6. A loopback client comes back on the port it actually got, and only the port is free.**
Up to and including 0.1.2 a client with a loopback return address and a port that changes
per run did not fit: the return address was compared exactly, so the address the client
published without a port and the address it arrived with never matched, and such a client
was pointed at the app password way of [client-setup.md](./client-setup.md). That was
wrong of us rather than a limit of v1. RFC 8252 section 7.3 says MUST: "The authorization
server MUST allow any port to be specified at the time of the request for loopback IP
redirect URIs, to accommodate clients that obtain an available ephemeral port from the
operating system at the time of the request." A native client takes whatever port the
operating system hands it, so refusing it over that port refuses it over a property it does
not control.

Since this build the port of a loopback address is not compared, and **nothing else moved**.
Scheme, host, path and query are still compared character for character, `localhost` still
does not stand in for `127.0.0.1`, and a hosted client on `https` gains no freedom at all.
D-35 is unchanged too: which addresses may be registered in the first place is still `https`
anywhere and `http` on loopback only, and the requested address is checked against that rule
again where it is used. The relaxed address is never written into the registration; it is a
comparison and not a second registration.

**Measured on 2026-08-20 against Claude Code 2.1.233, and the port really does change.** Four
runs, each started from a connection that had been fully given up, on a Nextcloud 34.0.3
instance:

```
run 1  16:06:38Z   redirect_uri=http://localhost:45157/callback   -> POST /token 200
run 2  16:08:44Z   redirect_uri=http://localhost:47608/callback   -> POST /token 200
run 3  16:09:11Z   redirect_uri=http://localhost:41977/callback   -> POST /token 200
run 4  16:09:27Z   redirect_uri=http://localhost:34567/callback   -> POST /token 200   (MCP_OAUTH_CALLBACK_PORT=34567)
```

The client's document publishes `http://localhost/callback` and `http://127.0.0.1/callback`,
both without a port. Three consecutive runs, three different ports, and the documented
default 3118 was not among them: a server that compares the port would have refused this
client three times out of four over a property it does not choose. Run 4 stands apart on
purpose, because one fixed value proves that an environment variable works and nothing about
whether a port changes.

**The decision, and the risk that is accepted with it.** The measurement confirms the
problem, so the RFC 8252 section 7.3 exception is implemented rather than noted as a risk.
What is accepted with it is port squatting on loopback: any program on that machine can hold
a port, so the port no longer distinguishes one local program from another. Three reasons
that is the smaller risk. The specification says MUST, so refusing it is not an option a
conforming server has. Scheme, host, path and query stay exact, so nothing but the port is
free. And a program that catches the redirect gains an authorization code it cannot redeem:
the code is bound to the PKCE verifier of the client that started the flow, `S256` is the
only method this server accepts, and the exchange without the verifier is refused.

**The rule is applied to the three hosts of `LOOPBACK_HOSTS`,** `127.0.0.1`, `::1` and
`localhost`, and the last of those is the one worth explaining. Section 7.3 names the IP
literals, and section 8.3 advises a client against the name. But D-35 already lets all three
be registered, and the client this rule exists for arrives with the name and not with the
literal (`http://localhost:45157/callback` in every run above). A literal reading of 7.3
would therefore have left exactly the measured client out. The relaxation stops at the host:
`127.0.0.1` against a registered `localhost` is a refusal, measured on the running instance,
because the two names resolve through different mechanisms and a client that publishes both
can send either.

Three counter checks on the same instance say the boundary holds: a registered path swapped
for another one (`/other`) is `400`, a loopback host the document does not carry (`[::1]`) is
`400`, and a public host that only looks like loopback (`localhost.example.com`) is `400`, all
three with the same page and no redirect. All four requests were sent on 2026-08-20 against
the same running instance with the same `client_id`, the same challenge and the same
`resource`, and only the return address was exchanged between them, which is what makes the
three refusals a statement about the address and not about the request.

**7. What the metadata advertises is what a registration has to get.** A client reads
`scopes_supported` and asks for what it finds there, and the authorization endpoint compares
that request against the scopes the client was registered with. If the two sets differ, the
server refuses a request its own document invited: measured with ChatGPT, which asks for
`offline_access nextcloud` and was answered with
`error=invalid_scope, error_description=Client was not registered with scope offline_access`,
while Claude.ai asks for the tool scope alone and never saw it. Every dynamic registration
of this server is therefore recorded with both scopes, whatever it sent, and the
registration response echoes them. `offline_access` is not a second data scope: it is the
refresh switch of RFC 6749, this server rotates refresh tokens for every connection either
way, and what a token reaches is the one tool scope `nextcloud`. A scope this server does
not have is still refused, at `/register` with `invalid_client_metadata` and at `/authorize`
with `invalid_scope`.

## Security notes for production

**The data key lives in Nextcloud, and the store lives in the volume.** Every app password
this app keeps is encrypted with AES-GCM, bound to the row it is stored in, with a key that
sits in Nextcloud's own ExApp configuration and is marked as sensitive. Two consequences an
operator has to know: a backup of the volume without the Nextcloud database is useless, and
replacing that configuration value by hand makes every stored authorization unreadable, so
every connected assistant has to connect again.

**Start the very first container with one worker.** The data key of this installation is
created on the first start and stored in Nextcloud's ExApp configuration, and that API has
no compare and set. Two workers that start at the same moment on an installation without a
key can both write one; the second write wins, and the worker that lost encrypts with a key
nobody can read again. Every later start reads the stored key and this cannot happen, so it
is one moment per installation. A loser is loud rather than silent: it logs "another worker
stored the data key first", and rows written with the lost key answer as unreadable instead
of decrypting into something wrong (WR-02).

**The persistent volume is not optional.** `APP_PERSISTENT_STORAGE` is where the store file
lives. Without a real volume every restart of the container loses every connection, and the
failure looks like a working installation until the first restart.

**The allowlist mode is a closed door, not a filter.** With
`NC_MCP_OAUTH_ALLOWLIST_ONLY` on and an empty list, nobody can authorize. That is the
intended reading and it is checked in four places, so a client that is blocked after its
token was issued stops working immediately rather than at the next expiry.

**On an instance that is reachable from the internet, run one of the two switches.** Either
`NC_MCP_OAUTH_ALLOWLIST_ONLY=1` with the clients you actually want, or
`NC_MCP_OAUTH_DCR=0` if you register your clients by hand. With both off, anybody who can
reach the URL can create a client registration. That alone hands out no data, because an
authorization additionally requires an account on this instance and the decision is bound
to the account that signed in, and the throttle caps the attempts. But an open registration
endpoint on a public host is an invitation nobody needs to accept, and the deliberate
exception is a short measurement window, not an operating mode. This project ran such a
window itself, for the connector proof of 2026-08-16, and closed it by deleting the
instance the same day.

**A connection is granted by the account that signed in, and by nobody else.** The consent
screen is reachable with a flow id alone, because a browser that has not signed in yet has
nothing else, but the decision behind it is not. HaRP resolves the Nextcloud account of
every request it forwards and writes it into the AppAPI header, empty when the caller sent
no credential, and `POST /authorize/decide` compares it with the account whose sign in
produced the authorization; a mismatch, and an absent account, are refused without a code.
The same rule guards the one page that shows an app password in clear text,
`GET /connect/wait`: a credential that cannot be handed to the account that signed in is
handed back to Nextcloud instead of being shown. Without those two checks the flow id was
the whole authorisation, and whoever started a flow could finish a sign in somebody else
performed (CR-01, the Login Flow v2 relay). Both routes are PUBLIC and both refusals are
this app's own, deliberately so: see section 9 of the evidence above for what the `USER`
access level costs and why it buys nothing here.

**The throttle protects the authorization endpoints and never the MCP route.** Ten refused
attempts per source and path class in five minutes end in `429` with `Retry-After`, and a
success pays back one of them rather than clearing the window. Rate limiting the tool calls
themselves would be this server's own denial of service, so the measured number above is the
honest ceiling: an accepted MCP request is not throttled here and costs one Nextcloud round
trip.

**On the two routes that open a Nextcloud login flow, every request is counted, not only
the refused ones.** `POST /connect` and `/authorize` answer 200 and 302 when they work, and
each of those answers costs one Nextcloud round trip plus one login flow record that lives
for twenty minutes there. Counting refusals bounded nothing at all on exactly the path
success criterion 5 is about, so those two carry a path class and a limit of their own:
twenty per source per five minutes, counted before the work. The screens behind them, the
consent surface and the waiting page, keep the refusal counter, because a waiting screen
reloads itself every three seconds and is doing nothing wrong (CR-02).

**A revocation takes effect before the request returns.** The store, the process caches and
the Nextcloud app password are ended in that order, and the third step may fail without
holding up the first two. A user ends their own connection under Settings, Security,
Devices and sessions; a client ends it with `POST /revoke`. Both are immediate.

**The end of a decision is a page that navigates, not a redirect.** The consent decision is
a form submission, and Chromium and WebKit check `form-action` against the target of a
redirect that follows one. Under the policy every page of this flow carries,
`form-action 'self'`, a `302` to the client would be refused by those browsers and the user
would be left on a blank page. So the decision answers `200` with a page that carries the
return address twice, as a `meta refresh` that fires immediately and as a button the reader
can see and press. Nothing about the OAuth response changes: the same address, the same
code, the same `state` and the same `iss` (CR-03).

**Nothing of a token is written anywhere.** No log record, no error page and no answer of
this server carries a bearer, a code, a PKCE value or an app password. The one page that
shows a credential is the onboarding result page, once, with `no-store`.

## Related

- Installing the ExApp itself: [exapp-install.md](./exapp-install.md)
- What a user enters into a client: [client-setup.md](./client-setup.md)
- The throwaway instance the hosted connectors are measured against:
  [staging-setup.md](./staging-setup.md)
- Where the discovery paths were measured first: [spike-discovery.md](./spike-discovery.md)
- Requirements `AUTH-02` (browser onboarding), `AUTH-03` (OAuth 2.1 to the MCP
  authorization specification) and `AUTH-07` (the three administrator switches)
- Running without AppAPI at all: [standalone-oauth.md](./standalone-oauth.md)
