# Token Exchange Two Account Evidence (EXCH-07, AUDIT-07)

**Status:** done, with one refuted expectation (measurement 4)
**Measured:** 2026-09-24
**Nextcloud version:** 35.0.0 (build 35.0.0.10)
**AppAPI version:** 35.0.0
**Deploy daemon:** HaRP, over the `compose.nc35.yml` topology (Caddy on `127.0.0.1:8082`)
**App version:** `mcp_connector` 0.2.1, deployed from the loopback registry
**Test issuer:** `caddy:2` serving one static key set over HTTPS with its own internal CA
(service `test-issuer` of `compose.nc35.yml`), never a Keycloak
**Scope:** do two accounts that were born on the **token exchange path** stay apart, measured
against a running Nextcloud rather than claimed by this code.

The two identities of this document came from two RS256 tokens of a foreign issuer, checked
by `oauth/exchange.py` against an armed `NC_MCP_EXCHANGE_*` configuration and mapped onto a
Nextcloud account by `oauth/mapping.py`. Neither came from Login Flow v2 and neither came
from an AppAPI credential a client held. That distinction is the whole point of this file:
`docs/spike-dav.md` proved the boundary for the AppAPI path on 2026-08-15, and a proof whose
two identities were connected any other way would only prove that one again.

Everything below is the raw output of `scripts/exchange_evidence.py`, which is the repeatable
form of this run. The signing key of the test issuer lives in that process and is never
written down; the two tokens live five minutes and are never written down either.

One exception, and it is written here rather than left to be found: the eight text lines of
`occ mcp_connector:audit:read` in the two sections below lost empty columns on their way into
this file, so they were not the raw form they claimed to be (WR-01 of the phase 24 review).
They now stand as `exapp/audit_read._line` prints them, recomputed from the values of the
same run: the six refusal lines from the measured sequence numbers, moments, group and count,
and the two `u:alice` lines from the `--json` block that stands beside them in this document
and was never touched. No measured value changed; only the number of separators did.
`tests/unit/test_docs_exchange_truth.py` now holds those lines against that function, so a
column that moves in the code makes this document fail rather than age.

## The armed configuration, and the trace that makes this an exchange proof

The run registers the deployed ExApp with the bootstrap payload plus four variables, and puts
the bootstrap registration back when it is finished. The variables, verbatim from the run and
without a secret among them:

```
== arming the exchange path on the deployed ExApp ==
NC_MCP_AUDIT_LOG=yes
NC_MCP_EXCHANGE_AZP=mcp-evidence-orchestrator
NC_MCP_EXCHANGE_ENABLED=yes
NC_MCP_EXCHANGE_ISSUER=https://test-issuer/realms/evidence
NC_MCP_PUBLIC_URL=http://127.0.0.1:8082/exapps/mcp_connector
ExApp mcp_connector deployed successfully.
ExApp mcp_connector successfully registered.
ExApp mcp_connector already enabled.
ExApps:
mcp_connector (MCP Connector): 0.2.1 [enabled]
```

`NC_MCP_EXCHANGE_JWKS_URI`, `NC_MCP_EXCHANGE_AUDIENCE`, `NC_MCP_EXCHANGE_ACCOUNT_CLAIM` and
`NC_MCP_EXCHANGE_MAPPING` are not set, so the documented defaults of `oauth/chain.py` are in
force: the key set is the issuer plus `/protocol/openid-connect/certs`, the audience is
`http://127.0.0.1:8082/exapps/mcp_connector/mcp`, the account claim is `sub`, and the mapping
profile is `account_id_v1`.

The second half of the trace is in the audit chain, and it is quoted in full further down: a
call over this path carries `client_id = urn:mcp-connector:token-exchange`, which is the
reserved value of `oauth/exchange_accounts.py` and belongs to no other way into this app.

## The topology this ran against

```
== topology, 2026-09-24T06:14:01Z ==
nc_app_mcp_connector  127.0.0.1:5000/mcp_connector:0.2.1  Up 42 seconds (healthy)
nc35-test-issuer  caddy:2  Up 20 minutes
nc35-caddy  caddy:2  Up 5 days
nc35-harp  ghcr.io/nextcloud/nextcloud-appapi-harp:release  Up 5 days (healthy)
nc35-nc  nextcloud:35.0.0-apache-local  Up 5 days (healthy)
ExApps:
mcp_connector (MCP Connector): 0.2.1 [enabled]
35.0.0
```

The last line is `AA_VERSION` out of the ExApp container, which is how AppAPI names itself to
the app it deployed.

## The test issuer, and the assumption it was built on

`ExchangeSettings` requires an HTTPS issuer and `jwks.fetch_json` pins the key set to the
origin of that issuer, so this run needs a TLS terminated key set endpoint inside the compose
network. `24-RESEARCH.md` carried that as assumption A6: httpx 0.28.1 builds its client
without `verify=` and without `trust_env=False`, so `SSL_CERT_FILE` should be enough to trust
a self signed test issuer. The assumption was read in the source and not measured. It is
measured now, from inside the ExApp container, with nothing set but that variable:

```
== assumption A6: the key set over HTTPS, from inside the ExApp container ==
200 application/json {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid"
```

A6 holds. One qualification belongs next to it, and it is the reason the run itself takes a
second route: httpx builds an SSL context for every client, including the ones this app
builds on its own way to Nextcloud, and `ssl.create_default_context` raises
`FileNotFoundError` for a file that is not there yet. A deploy variable that names a
certificate which only arrives after the deploy daemon started the container would therefore
turn the first outgoing call of the app into a crash. The run puts the root of the test
issuer into the trust bundle the image already carries instead, which is the same mechanism
without the window.

## Measurement 1: each account creates and reads its own file

```
files_upload({"content": "# exchange-alice-1a377c064b\n...", "path": "/exchange-alice-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-alice-1a377c064b.md","etag":"...","created":true}
files_read({"path": "/exchange-alice-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-alice-1a377c064b.md","content":"# exchange-alice-1a377c064b\n...","size":68,"content_type":"text/markdown"}
files_upload({"content": "# exchange-bob-1a377c064b\n...", "path": "/exchange-bob-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-bob-1a377c064b.md","etag":"...","created":true}
files_read({"path": "/exchange-bob-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-bob-1a377c064b.md","content":"# exchange-bob-1a377c064b\n...","size":66,"content_type":"text/markdown"}
```

This is the positive control, and without it every refusal below would be worthless: a
refusal that comes from a broken path looks exactly like a refusal that comes from an
enforced boundary. Both tokens work, both accounts write and read, and the files both
measurements below reach for exist.

## Measurement 2: alice's token on the known path of bob's file

The path is known in both spellings a caller could try it in, and the search is the third
way, because a tool that finds what it may not read leaks the existence of the file even
while the read stays refused.

```
files_read({"path": "/exchange-bob-1a377c064b.md"}) -> REFUSED | Error executing tool files_read: File not found: /exchange-bob-1a377c064b.md.
files_read({"path": "/../bob/exchange-bob-1a377c064b.md"}) -> REFUSED | Error executing tool files_read: The path '/../bob/exchange-bob-1a377c064b.md' points outside the user's files.
files_search({"query": "exchange-bob-1a377c064b"}) -> ANSWERED | {"query":"exchange-bob-1a377c064b","folder":"/","count":0,"items":[]}
```

The path is already known, so nothing but Nextcloud's own permission check stands between
alice and bob's file. The answer is `404`, never `200`. The status code is not in the tool
answer, it is in the access log of the Nextcloud container, and it is quoted below.

## Measurement 3: bob's token on the known path of alice's file

```
files_read({"path": "/exchange-alice-1a377c064b.md"}) -> REFUSED | Error executing tool files_read: File not found: /exchange-alice-1a377c064b.md.
files_read({"path": "/../alice/exchange-alice-1a377c064b.md"}) -> REFUSED | Error executing tool files_read: The path '/../alice/exchange-alice-1a377c064b.md' points outside the user's files.
files_search({"query": "exchange-alice-1a377c064b"}) -> ANSWERED | {"query":"exchange-alice-1a377c064b","folder":"/","count":0,"items":[]}
```

Symmetric. Neither direction sees the other.

## The status code behind every answer

The tool answer says refused; the access log of `nc35-nc` says with which code, and the
request it logs is the one the app made under the identity the exchange token named.

```
"PUT      /remote.php/dav/files/alice/exchange-alice-1a377c064b.md HTTP/1.1" 201
"PROPFIND /remote.php/dav/files/alice/exchange-alice-1a377c064b.md HTTP/1.1" 207
"GET      /remote.php/dav/files/alice/exchange-alice-1a377c064b.md HTTP/1.1" 200
"PUT      /remote.php/dav/files/bob/exchange-bob-1a377c064b.md     HTTP/1.1" 201
"PROPFIND /remote.php/dav/files/bob/exchange-bob-1a377c064b.md     HTTP/1.1" 207
"GET      /remote.php/dav/files/bob/exchange-bob-1a377c064b.md     HTTP/1.1" 200
"PROPFIND /remote.php/dav/files/alice/exchange-bob-1a377c064b.md   HTTP/1.1" 404
"PROPFIND /remote.php/dav/files/bob/exchange-alice-1a377c064b.md   HTTP/1.1" 404
```

The two `404` lines are the ones that matter, and they also show where the request went:
alice's token asked inside **alice's** home for a name only bob's home carries, and bob's
token asked inside **bob's** home. The home a request reaches is built from the principal the
mapping produced, which is why the traversal attempt of measurements 2 and 3 never leaves it.

## The Nextcloud side proof

Every request above appears in `data/exapp_impersonation.log`, one JSON line per request with
the user Nextcloud itself resolved. The two interesting rows are the two cross reads:

```
{"reqId":"rAQZOpv4uNHM2KBndmex","level":2,"time":"2026-09-24T06:14:15+00:00","remoteAddr":"172.30.42.130","user":"alice","app":"mcp_connector","method":"PROPFIND","url":"/remote.php/dav/files/alice/exchange-bob-1a377c064b.md","scriptName":"/remote.php","message":"impersonation request","userAgent":"nextcloud-mcp-connector/0.1","version":"35.0.0.10","data":{"app":"mcp_connector"}}
{"reqId":"3fHx5uWoO0At6aS7NUUn","level":2,"time":"2026-09-24T06:14:15+00:00","remoteAddr":"172.30.42.130","user":"bob","app":"mcp_connector","method":"PROPFIND","url":"/remote.php/dav/files/bob/exchange-alice-1a377c064b.md","scriptName":"/remote.php","message":"impersonation request","userAgent":"nextcloud-mcp-connector/0.1","version":"35.0.0.10","data":{"app":"mcp_connector"}}
```

`user` is what Nextcloud resolved, not what this app asserted in a log line of its own. The
`remoteAddr` is the ExApp container inside the compose network, not a public address.

## Measurement 4: a valid Basic credential next to an exchange token

This is the confused deputy case, and for the exchange path it is new: two bearer ways lie
next to each other here, and the question is which of them decides who acts. The oracle is
one read of the file alice owns and bob may not see. Answered means the request ran as alice,
refused means it ran as bob, and the two controls establish both readings first.

```
control, the Basic credential of alice alone:
HTTP 200 | {"result":{"content":[{"text":"{\"path\":\"/exchange-alice-1a377c064b.md\",\"content\":\"# exchange-alice-1a377c064b\\n..."

control, the exchange token of bob alone:
HTTP 200 | {"result":{"content":[{"text":"Error executing tool files_read: File not found: /exchange-alice-1a377c064b.md. ..."

the case, Basic of alice first and the exchange token of bob second:
HTTP 401 |

the case, the exchange token of bob first and Basic of alice second:
HTTP 200 | {"result":{"content":[{"text":"{\"path\":\"/exchange-alice-1a377c064b.md\",\"content\":\"# exchange-alice-1a377c064b\\n..."

the audit row that case wrote:
1 entry, newest first, at most 1 per read
491 - 2026-09-24T06:14:16Z - u:alice - files_read - - - - - ok - - - 79 - path - -

the same case with a Basic credential alice never had:
HTTP 200 | {"result":{"content":[{"text":"Error executing tool files_read: File not found: /exchange-alice-1a377c064b.md. ..."
```

**The expected result did not happen, and this document says so rather than rewording it.**
`docs/spike-dav.md` measured for the AppAPI path that a client set `Authorization` header is
ignored. The mirror image of that sentence does not hold here: with a valid Basic credential
of alice next to an exchange token that names bob, the request ran as **alice**.

The measurement says why, without leaving anything to interpretation:

- The audit row of that request carries no client id and no acting party. A call over the
  exchange path carries both (see the mixed run below), so this row was not written by the
  exchange path: the identity came from the AppAPI header HaRP injected after it resolved
  alice out of her Basic credential.
- The same request with a Basic credential alice never had runs as bob. So the exchange token
  decides whenever, and only whenever, the transport boundary could not resolve an account.
- With the two headers in the other order the request is refused outright with `401`: HaRP
  resolves nothing, and the app reads the first `Authorization` header, which is not a
  bearer.

This is the documented order of `exapp/middleware.py` ("verify the AppAPI handshake, then the
bearer") and it is the same order our own OAuth tokens run under, so it is not new behaviour
and it is not a new hole. What is new is that it was measured, and what it means for an
operator is a sentence that belongs in the setup documentation rather than in a footnote:

> On an ExApp deployment the account a request runs as is decided by the Nextcloud credential
> the reverse proxy can resolve from the request, and only then by the exchanged token. A
> caller that sends a Nextcloud session cookie, an app password or any other credential HaRP
> can resolve next to an exchanged token acts as the account of that credential, and nothing
> in the answer says that the token was not what decided.

There is no privilege escalation in it: the caller has to hold a working Nextcloud credential
of the other account, and whoever holds one can act as that account without any token at all.
The risk it names is a browser adjacent deployment, where a cookie travels without anybody
intending it to.

## The mixed run: both ways, one principal, one chain

Success criterion 1 of this phase asks whether a run with mixed calls stays verifiable. One
tool call with an access token this server issued itself, one over the exchange path, both
for the same account:

```
== the mixed run: one own token and one exchanged token, same principal ==
files_read({"path": "/exchange-alice-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-alice-1a377c064b.md", ...}
files_read({"path": "/exchange-alice-1a377c064b.md"}) -> ANSWERED | {"path":"/exchange-alice-1a377c064b.md", ...}
```

The chain is unbroken afterwards:

```
== occ mcp_connector:audit:verify --json ==
{"checked":true,"chains":5,"entries":495,"tombstones":0,"explained_entries":0,"used_bytes":147456,"sweepable_entries":476,"over_bound_unevictable":false,"broken":false,"findings":[],"limit":"This check finds an entry that was changed or removed unnoticed. It does not find somebody who can write this file, because whoever can write it can recompute the chain behind the change."}
```

Both calls stand in the same chain `u:alice`, because `oauth/mapping.py` answers the
canonical principal and never a login name (MAP-01):

```
== occ mcp_connector:audit:read --user=alice --limit=2 ==
2 entries, newest first, at most 2 per read
495 - 2026-09-24T06:14:20Z - u:alice - files_read - - - mcp-evidence-orchestrator - ok - - - 78 - path - -
494 - 2026-09-24T06:14:19Z - u:alice - files_read - exchange evidence - - - ok - - - 93 - path - -
```

The same two rows as data, which is where the reserved client id of the exchange path is
visible and where the two hashes show that they are neighbours in one chain:

```
== occ mcp_connector:audit:read --user=alice --limit=2 --json ==
{"read":true,"count":2,"limit_applied":2,"truncated":true,"entries":[
 {"seq":494,"chain":"u:alice","kind":"call","at":1790230459,"nc_user":"alice","tool":"files_read","client_id":"bc6b83e8-9c90-4382-be3d-e087ca300871","auth_id":"A4RV9s7-IoKoCfL1HMaVNK1l5rTgNjwtsQZPfqyzMJY","client_name":"exchange evidence","actor":null,"outcome":"ok","reason":null,"duration_ms":93,"params":["path"],"removed":null,"prev_hash":"cdf94a71d6292d9d5b03bfd43dd97ca4de179bf4e6c4f6c77025d741c0d35c3f","hash":"74314bbc3e4af6e4aa3fb3f984a1ed4b558c7acaf848b251811e98298e7dcbce"},
 {"seq":495,"chain":"u:alice","kind":"call","at":1790230460,"nc_user":"alice","tool":"files_read","client_id":"urn:mcp-connector:token-exchange","auth_id":"","client_name":null,"actor":"mcp-evidence-orchestrator","outcome":"ok","reason":null,"duration_ms":78,"params":["path"],"removed":null,"prev_hash":"74314bbc3e4af6e4aa3fb3f984a1ed4b558c7acaf848b251811e98298e7dcbce","hash":"da3e6f96dcb154c19dab434a3c60a9e49a77a43794eb638d066c658dbbd5ea54"}]}
```

Row 494 is the own token: a registered client id, a stored authorization, a client name, and
no acting party. Row 495 is the exchanged token: the reserved client id
`urn:mcp-connector:token-exchange`, an empty authorization because there is none to look up,
no client name because no client is registered on that way, and the acting party in the
column that says who acted (AUDIT-07, plan 24-01). The `prev_hash` of 495 is the `hash` of
494, so the two calls are neighbours in one chain and not two records that merely agree.

## The refused attempt

A token signed by the same key but carrying an issuer this instance never named. The request
is refused at the transport boundary, and the refusal is visible to the operator without a
single value out of the token reaching the log (AUDIT-07, plan 24-03):

```
== the refused attempt: a token of an issuer this instance never named ==
POST /mcp with a token of a foreign issuer -> HTTP 401

== occ mcp_connector:audit:read --user=refusals ==
6 entries, newest first, at most 200 per read
493 - 2026-09-24T06:14:17Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
474 - 2026-09-24T06:13:05Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
456 - 2026-09-24T06:11:31Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
438 - 2026-09-24T06:10:44Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
423 - 2026-09-24T06:09:48Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
408 - 2026-09-24T06:07:35Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1
```

The row carries the rejection identifier `exchange_issuer`, the number of attempts it stands
for, and no account, no client, no subject and no claim. The six rows are the six runs of
this script during the day this was measured; each run makes exactly one refused attempt.

## The state of the instance afterwards

The run puts the bootstrap registration back and asks the instance whether it took:

```
== restoring the bootstrap registration ==
ExApp mcp_connector successfully registered.
ExApps:
mcp_connector (MCP Connector): 0.2.1 [enabled]
the token exchange path is not configured on this instance, so there is nothing to hold a
token against. Nothing was checked and nothing about the token follows from that.
```

## Consequence

The two account boundary holds on the token exchange path, measured and not argued. Neither
of two identities that were both born on that path sees anything of the other: not by the
known path, not by naming the other home, and not through a search. The refusal is Nextcloud's
own `404`, and the Nextcloud side log names the account each request ran as.

Concretely:

- EXCH-07 is met. `oauth/mapping.py` produces a principal, `oauth/exchange_appapi.py` turns it
  into an impersonated identity for an account that already exists, and everything past that
  is Nextcloud's ACL, exactly as `docs/spike-dav.md` measured it for the AppAPI path.
- Success criterion 1 of phase 24 is met: a run with mixed calls leaves both calls in one
  chain, `audit:verify` finds nothing, and the two rows are distinguishable by the reserved
  client id and the acting party.
- Success criterion 2 is met: a refused attempt is visible with its identifier and its count
  and with nothing out of the token.
- Measurement 4 refutes the expectation it was written against. The acting identity on an
  ExApp deployment is decided by the Nextcloud credential the reverse proxy can resolve, and
  only then by the exchanged token. The sentence quoted above belongs in
  `docs/token-exchange.md` when that page is written.

## What this does not prove

- It ran against Nextcloud 35.0.0 with SQLite in a throwaway instance, with one ExApp
  container and one account list.
- The issuer was a static key set, not a Keycloak. Nothing in the checked claim set depends on
  who produced it, but a real realm writes claims this run did not have to handle, and the
  golden fixture that would cover them is deliberately out of scope.
- Both accounts were local Nextcloud accounts mapped by the `account_id_v1` profile, where the
  claim carries the account id itself. The `user_oidc` sub profile derives a different
  principal and is not measured here.
- Group folders, external storage, server side encrypted instances and LDAP or SSO backed
  users are outside this measurement, exactly as they are outside `docs/spike-dav.md`.
- Shares were not exercised. The negative case proves the default boundary; an explicit share
  is Nextcloud's own ACL and was not the subject.
