# Token exchange setup

**Scope:** configuring the token exchange path of this app end to end, from the identity
provider to the first tool call. It is the path on which a service of the organization
exchanges a token at its own provider (RFC 8693) and presents the result to this connector
in a user's name.

The path is **off in the factory state**. An installation that arms nothing reads not one
variable of the `NC_MCP_EXCHANGE_` namespace and behaves exactly as it did before this
milestone. Everything below describes what an operator turns on deliberately.

This document names what is decided here and what is not. The part that is not decided here
sits in section 10, in its own section rather than in a footnote, because a setup instruction
that presents an open question as settled builds an installation that has to be rebuilt.

---

## 1. The chain in one picture

```
  service of the organization            Keycloak                    this connector
  (the orchestrator)                     (the realm)                 (Nextcloud)
          |                                  |                              |
          |  1. token exchange, RFC 8693     |                              |
          |--------------------------------->|                              |
          |<---------------------------------|                              |
          |     exchanged access token       |                              |
          |                                                                 |
          |  2. POST /mcp, Authorization: Bearer <exchanged token>           |
          |---------------------------------------------------------------->|
          |                                                                 |
          |                          3. check, map, act as that account      |
          |<----------------------------------------------------------------|
```

**This connector never exchanges anything itself.** It holds no client credentials at the
provider, it makes no token request, and it has no way to turn one token into another. It
accepts a token that already exists, checks it against rules it was configured with, maps the
account it names, and then acts with the permissions of that account and no others. Step 1 is
the orchestrator's business alone, and nothing in this document configures it.

---

## 2. The Keycloak side

What has to exist at the provider before an operator arms anything here.

**Standard Token Exchange V2** enabled on the realm. This is the exchange the orchestrator
performs in step 1 above.

**A target client.** The exchanged token is minted for it, and its identity is what this
instance accepts. Two values of that client matter here:

* `aud`, the audience the exchange writes into the token,
* `azp`, the authorized party, which names who asked for the exchange.

**The audience convention.** A token minted for instance A must not hold at instance B, so
the audience is the instance boundary and never a generic name. By default this server
expects the resource URL of this instance in `aud`, which is the same value it writes into
the tokens it issues itself.

> **Recommendation, not a rule.** Setting the `client_id` of the target client to exactly the
> canonical resource URI of the instance makes `aud` and `client_id` one value instead of
> two, which removes the most common way this path is misconfigured. This is written as a
> recommendation on purpose: which value F13 actually writes into `aud` is the first of its
> four open decisions (section 10). An operator who configures against this recommendation
> today may have to change one value later, and the value is `NC_MCP_EXCHANGE_AUDIENCE`.

**The azp allowlist.** `NC_MCP_EXCHANGE_AZP` names which authorized parties may act on this
instance at all, comma separated. It has no default, for the same reason the issuer has none:
it decides who may act, and a guessed default would decide it wrongly and silently.

**The key set.** By default this server fetches the provider's key set from the issuer plus
`/protocol/openid-connect/certs`, which is where a Keycloak realm publishes it. A split
network that serves the key set from a different origin sets `NC_MCP_EXCHANGE_JWKS_ORIGIN`;
without it the same origin rule holds the fetch on the issuer.

**Signing.** Asymmetric algorithms only. `HS*` and `none` are never accepted, whatever the
configuration says.

---

## 3. The connector side: the variables

Every variable of the path, and what each one decides. The table deliberately carries no
default values: they live in exactly one place, and a second copy here is the kind of double
maintenance that goes stale without anybody noticing.

| Variable | What it decides |
|---|---|
| `NC_MCP_EXCHANGE_ENABLED` | The switch. While it is off, no variable below is read and no default is computed. |
| `NC_MCP_EXCHANGE_ISSUER` | Required. The realm URL of the provider, HTTPS, no trailing slash. It decides whose signatures this server will trust. |
| `NC_MCP_EXCHANGE_AZP` | Required, comma separated. Which authorized parties may act at all. |
| `NC_MCP_EXCHANGE_JWKS_URI` | Where the key set is fetched, for a provider that does not publish it under the standard path. |
| `NC_MCP_EXCHANGE_JWKS_ORIGIN` | Only a split network needs it: it moves the same origin rule of the key set fetch off the issuer. |
| `NC_MCP_EXCHANGE_AUDIENCE` | Which `aud` value a presented token has to carry. Exactly one string, never a list. |
| `NC_MCP_EXCHANGE_ACCOUNT_CLAIM` | Which claim of the checked token names the Nextcloud account. |
| `NC_MCP_EXCHANGE_ALGORITHMS` | Comma separated. Which signing algorithms a token may be signed with. |
| `NC_MCP_EXCHANGE_MAPPING` | Which mapping profile turns the checked claim into the canonical Nextcloud principal. |
| `NC_MCP_EXCHANGE_OIDC_PROVIDER_ID` | Belongs to the `user_oidc_unique_uid_sub_v1` profile alone: the numeric id of the `user_oidc` provider its derivation is keyed with. Set while the other profile is in force, it is refused rather than ignored. |

**Where the defaults live.** In the module docstring of
`src/mcp_connector/oauth/chain.py`, one entry per variable, each with the reasoning for the
value it defaults to and for the two that deliberately default to nothing. That docstring is
the single source; this page names meanings and points at it for values.

**The two mapping profiles** of `NC_MCP_EXCHANGE_MAPPING`:

* `account_id_v1` treats the value of the configured claim as the Nextcloud account id
  itself. This is the case in which the provider already carries the canonical id.
* `user_oidc_unique_uid_sub_v1` reproduces the derivation the `user_oidc` app performs with
  "unique user id" turned on: the account id is the lowercase hex SHA-256 of
  `"<provider id>_0_<sub>"`. It needs `NC_MCP_EXCHANGE_OIDC_PROVIDER_ID`.

**An armed path with a missing audience is refused, not defaulted.** The default audience is
derived from `NC_MCP_PUBLIC_URL`; without that variable the derivation would fall back to a
loopback placeholder that is identical on every installation, which would be no instance
boundary at all. So an armed path without either variable refuses to start.

---

## 4. The account, per deployment mode

The two deployment modes differ in exactly one question: how does a mapped principal become
an identity this server may act with.

**ExApp mode.** AppAPI impersonation, and nothing is provisioned. The account the token names
has to exist in Nextcloud already. The app asks whether it exists and acts as it; it never
creates it.

**Standalone mode.** The binding is granted in advance, in a browser, on the enrollment page
`/exchange`. The user is shown what the permission is, signs in to Nextcloud, confirms with
the independent single sign-on the consent screen also demands, and can take the permission
back on the same page. Described in full in
[standalone-oauth.md](standalone-oauth.md).

**Both modes fail closed.** Uncertainty is a refusal and never a pass: not found, not
enrolled, not readable and not allowed are one answer from outside, and none of them says
which one it was. This is the deliberate opposite of the audit sweep, where an unreadable
account list means "keep the chain", because there a kept chain costs storage while here a
passed uncertainty would cost somebody's data.

---

## 5. The first tool call, and where to find it

A success is an ordinary MCP call: `POST /mcp` with the exchanged token in the
`Authorization` header, answered with the result of the tool. Nothing in the answer says that
the token was an exchanged one, and nothing needs to.

Where it becomes visible is the audit log, with the audit log turned on:

```bash
occ mcp_connector:audit:read --json
```

Two fields identify such a call:

* `client_id` is `urn:mcp-connector:token-exchange`. The exchange path has no registered
  client, because the acting party registered at a foreign realm and not here, so every
  exchange identity is booked under this one reserved identifier. A reader can tell an
  exchange call from a call of a registered client at a glance.
* `actor` carries the acting party, which is the `azp` of the token. The chain grew no column
  for it: the field the schema already had for who acted is the one it uses.

`occ mcp_connector:audit:verify --json` walks the chains afterwards and names the first place
one of them is broken.

---

## 6. The dry run

Before a first real call, an administrator can hold a token against the configured rules
without using it for anything:

```bash
occ mcp_connector:exchange:check --token=<token>
occ mcp_connector:exchange:check --token=<token> --json
```

It reports every rule with its outcome. The answer never repeats the token value.

**The price, said out loud.** The value stands in the process list of the Nextcloud host
while the command runs, and in the shell history afterwards. There is no technical way around
this: AppAPI hands no stdin through to an ExApp command, and a `--token-file` would lie on
the Nextcloud host while the handler reads inside the ExApp container. So **use a short lived
test token here and never a productive one.**

**With `--json`, the key a script watches is `passed`.** Not the exit code, which is always 0:
AppAPI drops the body of any answer that is not a 200, and here the answer is the body.

**What a green run does not mean.** The dry run makes no Nextcloud call, creates no session
and no authorization, and writes no row into the audit log. In particular it does **not**
check that the account the token names exists. A green run says the token would pass the
rules of this instance, not that a call with it would succeed.

**The dry run exists in ExApp mode only.** occ is an ExApp surface; the standalone deployment
has no second surface for it and does not get one in this milestone. The rule itself is a pure
function, so a second surface would be one file later, but today it does not exist.

---

## 7. The `occ oauth2:add-client` playbook

```bash
occ oauth2:add-client "<name>" "<redirect-uri>"
```

Two required arguments, no options beyond the output formats of the base class. The redirect
URI is validated with `FILTER_VALIDATE_URL`. Verified against the source of Nextcloud 35.0.0,
`apps/oauth2/lib/Command/AddClient.php`.

> **What this client is for is an open F13 answer, deferred on 2026-09-24.**
>
> The command above is verified; its role in this setup is not. The source that would explain
> it is section 6 of F13's specification note, which is not part of this repository. Nothing
> in this connector uses a Nextcloud-owned oauth2 client: the ExApp mode speaks through
> AppAPI, and the standalone mode speaks to an external provider through the `NC_MCP_OIDC_`
> variables and to Nextcloud through Login Flow v2. Several roles for such a client are
> conceivable, and they are **not distinguishable** from anything in this repository, so this
> document names none of them rather than inventing one.
>
> **Ask F13 what the client is for before you create one.** A client created for the wrong
> reason is a standing credential nobody is maintaining.

---

## 8. Sizes and limits of the route

Every number below is measured, and carries the date it was measured on. The two environment
limits were measured against a running Nextcloud 35.0.0 HaRP topology; the two bounds of this
app are constants whose switch point was measured at exactly the value the constant names.

| Limit | Where it bites | Measured |
|---|---|---|
| about 14.9 kB of token through Caddy, about 15.1 kB directly on HaRP | The whole request header. Past it the answer is a `431` and nothing of the request reaches this app. | 2026-09-23: last token length passed through was 14912 bytes over Caddy and 15058 bytes directly on HaRP, then `431` |
| **8190 bytes per header line** in Nextcloud's Apache (`LimitRequestFieldSize`, its default) | The `Authorization` header on the `user-info` path, which is the PHP side HaRP consults. Past it Apache answers `400` before PHP sees anything. **This is the binding environment limit of the route.** | 2026-09-23: the switch was located between token length 8050 and 8200 bytes |
| 8192 bytes of raw token (`MAX_TOKEN_BYTES`) | This app, checked before the first base64 step, so no attacker-shaped bytes are decoded first. | 2026-09-24: the switch point of the whole way through AppAPI sits at exactly this value, so nothing in front of it cuts anything |
| twice `MAX_TOKEN_BYTES` for the dry run request body | The dry run handler, which needs room for a full token plus the JSON envelope, the second option and the quoting. A bound below the token bound would answer a merely large token with a form error, which is the one answer a dry run exists to avoid. | 2026-09-24: an option value of 8193 bytes arrived through AppAPI uncut |

**What decides the token size.** With RS256 and a 2048 bit key the signature part is a
constant 342 characters, so the size is determined entirely by the claim set. Tokens built
from realistic claim sets measured 920, 1477 and 4132 bytes on 2026-09-23, and the threshold
to 8192 bytes was reached at about **68 realm roles and 68 groups**.

> **The advice this page owes the F13 side: keep the role and group mapper of the target
> client lean.** A generous LDAP group mapper on an agency instance can reach the 68/68 mark,
> and this connector, Apache and nginx all draw their line at about 8 kB. A token that grows
> past it does not degrade, it stops working.

The raw output of the measurements this path was proven with is in
[exchange-evidence.md](exchange-evidence.md), against a running Nextcloud, with the
configuration of every run in it.

---

## 9. What this path does not do

An honest list, because every entry of it is something an operator would otherwise assume.

**No silent account creation.** Neither mode provisions anything. A token naming an account
that does not exist is refused, not honoured by creating it.

**No delegation semantics.** Keycloak's Standard Token Exchange V2 writes no `act` claim, so
there is no chain of "A acting for B" in the token. The only trace of who asked for the
exchange is `azp`, and that is what the audit line records as the acting party. Anybody
reading the audit log for a delegation chain will not find one, because none was ever there.

**No introspection and no revocation list in the hot path.** This app does not ask the
provider whether a token is still good; it checks the signature and the claims and nothing
else. **The lifetime is therefore the only bound on how long a leaked token, or one revoked
at the provider, keeps working here.** A token older or longer-lived than 900 seconds is
refused outright rather than shortened, with 30 seconds of clock tolerance.

**The token travels through Nextcloud's PHP on every request.** HaRP passes the request
headers on to the `user-info` path, so a foreign token goes through Apache on each call. When
it is too large for a header line, that is where the `400` comes from, and it is a property of
the environment rather than a decision of this app.

**A dry run does not check account existence.** See section 6.

**On an LDAP-backed instance whose account list answers incompletely, valid tokens of valid
accounts would be refused.** The account list this app asks is the AppAPI user list of the
instance, and whether that list answers completely on an LDAP or directory backend is
unmeasured. In the audit sweep an unreadable list means "do nothing"; on the exchange path the
same uncertainty means "refuse", because the path fails closed. That inversion turns an
accepted residual risk into a thing to watch on exactly this kind of instance.

**A resolvable Nextcloud sign-in decides which account acts, before the exchanged token
does.** This was measured on 2026-09-24 and it contradicted the expectation of the run that
found it:

> On an ExApp installation the Nextcloud sign-in that the reverse proxy can resolve from the
> request decides which account acts, and only after that does the exchanged token. Whoever
> puts a session cookie, an app password or any other resolvable credential next to an
> exchanged token acts as the account of that credential, and nothing in the answer says that
> the token did not decide.

The audit line of such a call carries neither a `client_id` nor an acting party, while a call
of the exchange path carries both, which is how the case is told apart afterwards. This is the
documented order of the ExApp middleware (verify the AppAPI handshake, then the bearer) and it
holds for this app's own OAuth tokens in the same way. It is **not** a privilege escalation:
the caller has to hold a working Nextcloud sign-in of the other account, and whoever holds
that acts as that account anyway. What it is, is a reason to keep this path away from a
browser-near deployment in which a cookie rides along unintentionally.

---

## 10. What hangs on F13's four open answers

Four decisions of the specification note are not made yet. Everything that hangs on them is
configuration surface with a documented default, so the path can be built and measured
without them, but an installation configured today may have to change one value per decision.

| No. | Open decision | What stands in its place today |
|---|---|---|
| 1 | **The audience convention**: which value F13 writes into `aud` | The default is the resource URL of this instance; the recommendation to F13 is in section 2, marked as a recommendation |
| 2 | **The account claim**: which claim points at the Nextcloud account | `NC_MCP_EXCHANGE_ACCOUNT_CLAIM` with a documented default, plus the two mapping profiles of section 3 |
| 3 | **An example token and a realm export** | Testing happens against tokens this project builds itself; a golden fixture from a real realm is a future requirement and deliberately out of scope |
| 4 | **The exchange target entry at F13** | Open. Without it, F13 does not exchange onto this instance at all |

The role of the `occ oauth2:add-client` step in section 7 is a fifth open point of the same
note, deferred by the owner on 2026-09-24.

**Two lists, and which is which.** The table above is the authoritative one: it holds the four
**decisions** of the specification note. A second list of four appears elsewhere in this
project's research and holds the four **knowledge gaps** that hang on those decisions: which
value F13 writes into `aud`, whether the F13 realms carry `preferred_username` in exchanged
tokens, whether the target instances are LDAP-backed, and whether the AppAPI user list answers
completely on an LDAP backend. When both are quoted, this is the difference between them: the
first list is decided by F13, the second is answered by measuring.

---

## Related

* [standalone-oauth.md](standalone-oauth.md) for the enrollment page `/exchange` and the
  deployment without AppAPI.
* [oauth-setup.md](oauth-setup.md) for this app's own authorization server, which is a
  different path and is not configured here.
* [exchange-evidence.md](exchange-evidence.md) for the raw output of the runs this path was
  measured with.
