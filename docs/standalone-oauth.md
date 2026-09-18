# Standalone OAuth deployment

**Scope:** running this app as its own process, `nc-mcp-oauth`, without AppAPI. It serves
the same `/mcp` endpoint, the same OAuth 2.1 authorization server and the same consent
screen as the ExApp, for a Nextcloud it reaches over HTTPS like any other client. The
credential-based and ExApp deployment ways are described in
[client-setup.md](./client-setup.md) and [exapp-install.md](./exapp-install.md).

## What this mode is

AppAPI gives the ExApp two things this process does not have: a container identity Nextcloud
already trusts, and an `Authorization` header that names the signed-in account on every
request HaRP forwards. Outside AppAPI neither exists, so the standalone entry point
(`src/mcp_connector/entry_oauth.py`) replaces both with explicit configuration and one more
moving part: an independent browser identity for the consent decision.

That identity is an OIDC single sign-on at the organization's own identity provider, the one
Nextcloud itself already trusts through the `user_oidc` app. The consent screen offers it,
and only after that sign-on names the same account as the Nextcloud Login Flow v2 that
started the authorization is a decision accepted. This is CR-01: without an AppAPI header,
nothing else in the request proves that the browser approving consent is the browser that
signed in to Nextcloud a moment earlier, and a login-flow relay would otherwise let one
browser finish a sign-in another one performed.

`/mcp` accepts nothing but a verified OAuth bearer. What this mode does **not** attach:

- the browser onboarding routes (`/connect`),
- the connections page,
- purge,
- the audit routes.

Those all read an AppAPI or occ identity this process does not have. A standalone
deployment that also needs them belongs to the ExApp mode instead.

## Requirements

- Nextcloud reachable over HTTPS from this process, at the URL in `NC_MCP_URL`.
- The `user_oidc` app installed and configured with the organization's identity provider,
  with **"unique user id"** turned on and **`sub`** set as the effective mapping claim. This
  process reproduces that derivation itself (`user_oidc_unique_uid_sub_v1`): the account id
  is the lowercase hex SHA-256 of `"<provider id>_0_<sub>"`. The operator is asserting that
  `user_oidc` is configured this way; a wrong assertion is not trusted on its own: the
  derived id is compared against the account id Nextcloud's own Login Flow v2 produced, and
  a mismatch fails closed rather than picking one of the two.
- An OIDC client registered at the provider:
  - authorization code flow with PKCE, **S256** only,
  - redirect URI `<public url>/oidc/callback` (for example
    `https://mcp.example.com/oidc/callback`),
  - ID tokens signed with an asymmetric algorithm (`RS256` unless configured otherwise;
    `HS*` and `none` are never accepted),
  - a client secret is optional; public and confidential clients are both supported.
- A public HTTPS address for this process (`NC_MCP_PUBLIC_URL`, for example
  `https://mcp.example.com`). It must be HTTPS: the browser identity of every route here,
  including the OIDC proof, lives in `__Host-` cookies, which browsers only keep over HTTPS.

## Configuration

Every variable `load_settings` and `main` read. All are required unless marked optional.

| Variable | Meaning |
|---|---|
| `NC_MCP_AUTH_MODE` | Must be `oauth` to select this mode at all. |
| `NC_MCP_URL` | The base URL of the Nextcloud instance. |
| `NC_MCP_PUBLIC_URL` | The public HTTPS address of this process. Used as-is to build the OIDC redirect URI (`<public url>/oidc/callback`) and every issued link. |
| `NC_MCP_OAUTH_STORAGE_DIR` | Directory for the OAuth store. Must already exist, be writable by this process, and not be writable by its group or by others. No fallback and nothing is created for you. |
| `NC_MCP_OAUTH_DATA_KEY_FILE` | Path to the data key file (see Secrets, below). |
| `NC_MCP_OIDC_ISSUER` | The provider's issuer URL, exactly as it appears in its discovery document, no trailing slash. |
| `NC_MCP_OIDC_CLIENT_ID` | The client id registered at the provider. |
| `NC_MCP_OIDC_CLIENT_SECRET_FILE` | Optional. Path to a file holding the client secret, for a confidential client. Omit for a public client. |
| `NC_MCP_OIDC_PROVIDER_ID` | The numeric id of the `user_oidc` provider in Nextcloud, matching the mapping strategy above. |
| `NC_MCP_OIDC_MAPPING` | The identity mapping strategy. Only `user_oidc_unique_uid_sub_v1` exists today; any other value is refused. |
| `NC_MCP_OIDC_ALGORITHMS` | Optional, comma-separated. Signing algorithms an ID token may use. Defaults to `RS256`. Only asymmetric algorithms may be listed. |
| `NC_MCP_TRUST_FORWARDED_FOR` | Optional. `1` when a reverse proxy sets `X-Forwarded-For` and is the only way in; the rate limiter then counts per forwarded address. Default off in this mode. |
| `NC_MCP_BIND_HOST` | Optional. Interface `nc-mcp-oauth` binds to. Defaults to `127.0.0.1`. |
| `NC_MCP_BIND_PORT` | Optional. Port `nc-mcp-oauth` binds to. Defaults to `8765`. |

`NC_MCP_ALLOWED_HOSTS` and `NC_MCP_DISABLE_DNS_REBINDING_PROTECTION` apply here the same way
they do in the other HTTP modes; see [oauth-setup.md](./oauth-setup.md) and the ExApp docs
for what they do.

This process refuses to start if `NC_MCP_STATIC_BEARER`, `NC_MCP_APP_PASSWORD`,
`NC_MCP_USER`, `APP_ID` or `APP_SECRET` is set. Every MCP call here is authenticated by this
app's own OAuth tokens only; a second credential channel would be a silent fallback.

## Secrets

**The data key file** (`NC_MCP_OAUTH_DATA_KEY_FILE`) encrypts every app password this
process stores. It must hold exactly 64 hex characters (32 bytes), generated once with:

```
openssl rand -hex 32
```

Permissions: the file must grant nothing to others and no write access to its group. It is
only ever read, never generated by this process. A missing file is a startup error, not the
start of a fresh key. **Do not regenerate it.** A new key cannot decrypt rows written with
the old one, so replacing the file makes every stored authorization unreadable and every
connected assistant has to connect again.

**The client secret file** (`NC_MCP_OIDC_CLIENT_SECRET_FILE`), when used, follows the same
rule: nothing for others, no group write. Its content is never included in an error message.

**The storage directory** (`NC_MCP_OAUTH_STORAGE_DIR`) must not be writable by its group or
by others, and needs a persistent volume: without one, every restart loses every stored
authorization, and the failure looks exactly like a working installation until the first
restart.

**These permission checks run on POSIX systems only** (Linux, macOS, containers). Windows
models a read-only flag in these bits and nothing else, so there the process does not check
them, and the ACLs of the key file, the secret file and the storage directory are the whole
boundary. Restrict them to the account that runs the connector.

## Running

The console script is `nc-mcp-oauth`. It validates the configuration, checks the data key,
then serves until stopped. An invalid configuration exits with status `2` and a named error
message on stderr; nothing partially starts.

It binds to `NC_MCP_BIND_HOST` (default `127.0.0.1`) and `NC_MCP_BIND_PORT` (default
`8765`), and is meant to run behind a TLS-terminating reverse proxy, never exposed directly.
Addresses, links and cookies are built from `NC_MCP_PUBLIC_URL`, never from forwarded
headers. The rate limiter uses the address of the peer it is talking to. In this mode
`X-Forwarded-For` is ignored unless `NC_MCP_TRUST_FORWARDED_FOR` says otherwise, because
without a proxy in front that header is whatever the caller wrote, and one caller could
then spend the limit of everyone else. Set `NC_MCP_TRUST_FORWARDED_FOR=1` when a reverse
proxy sets the header itself and **is the only way to reach this process**.

Discovery: `/.well-known/oauth-protected-resource/mcp` and
`/.well-known/oauth-authorization-server`. On a public address without a path prefix the
OpenID Connect variant `/.well-known/openid-configuration` is not served, because this
process is not an OpenID provider and clients such as ChatGPT would otherwise switch on
their OIDC mode for it. Under a path prefix it stays, as in the ExApp.

`GET /health` answers `{"status": "ok", "version": ...}` without authentication and is the
probe to use.

### In a container

The published image starts the ExApp by default. For this mode, override the entry point and
the health check, and mount the two secrets and the store directory:

```yaml
services:
  mcp-connector:
    image: ghcr.io/<owner>/<image>:<tag>
    entrypoint: ["nc-mcp-oauth"]
    environment:
      NC_MCP_AUTH_MODE: oauth
      NC_MCP_BIND_HOST: 0.0.0.0
      NC_MCP_URL: https://cloud.example.com
      NC_MCP_PUBLIC_URL: https://mcp.example.com
      NC_MCP_OAUTH_STORAGE_DIR: /data
      NC_MCP_OAUTH_DATA_KEY_FILE: /run/secrets/data_key
      NC_MCP_OIDC_ISSUER: https://sso.example.com
      NC_MCP_OIDC_CLIENT_ID: "<client id>"
      NC_MCP_OIDC_CLIENT_SECRET_FILE: /run/secrets/oidc_client_secret
      NC_MCP_OIDC_PROVIDER_ID: "<user_oidc provider id>"
      NC_MCP_OIDC_MAPPING: user_oidc_unique_uid_sub_v1
    volumes:
      - mcp-data:/data
    secrets: [data_key, oidc_client_secret]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8765/health"]
```

The image runs as uid 10001: the store directory must belong to that user with mode `0700`,
and the secret files must be readable by it without granting anything to others.

## Operations and security notes

The process's own access log never shows the query string of `/oidc/callback`; it is
replaced with `?[redacted]`. Logs in front of it (reverse proxy, CDN) need the same rule.

Rate limiting counts per client address. Behind a proxy that address comes from the first
entry of `X-Forwarded-For`, which only means something when nothing but that proxy can
reach this process; see `NC_MCP_TRUST_FORWARDED_FOR` above.

- **Redact the query string of `/oidc/callback` in every access log this process or its
  proxy writes.** A successful callback carries an authorization code from the identity
  provider in that query string.
- **Rate limiting is keyed by `X-Forwarded-For`.** Only put this process behind a proxy that
  sets that header correctly; without one, or behind a proxy that forwards a caller-supplied
  value verbatim, the per-source limit can be defeated. A path-class ceiling that no header
  can escape still applies underneath it.
- **A callback URL and its `state` let a bystander abort that one sign-in, not finish it.**
  Knowing a pending flow's callback address is not proof of anything: the proof only exists
  once a callback validates a code, a nonce and a PKCE verifier the browser itself produced,
  and once the mapped account matches the authorization's account.
- Every browser and OAuth route attached here reads at most 64 KiB of request body; a larger
  announced or streamed body is refused with `413` before it is parsed. The MCP route itself
  keeps the limits of the MCP SDK.
- An invalid configuration always exits with status `2`, logging one message and one hint;
  there is no partial start.

## The consent flow, from the user's side

1. An MCP client opens the authorization URL of this app.
2. Nextcloud's own Login Flow v2 asks the user to sign in (including any second factor
   Nextcloud itself enforces). This app never sees a password.
3. The consent screen appears, naming the client and what it is asking for, with a
   **"Continue with single sign-on"** action instead of the usual approve/deny buttons,
   because this browser has not yet proven it is the same one that just signed in to
   Nextcloud.
4. That action sends the browser to the organization's identity provider
   (`sso.example.com`), where the user signs in if they are not already.
5. The provider redirects back to `/oidc/callback`. Once the callback validates, the
   browser holds a short-lived proof, and it is returned to the consent screen.
6. The consent screen now shows the ordinary approve or deny buttons, because the proof
   matches the account that signed in in step 2.
7. Approving or denying ends on a handoff page rather than a redirect: it carries the
   return address twice, as an immediate `meta refresh` and as a link to click. This is
   because the page enforces `form-action 'self'` and the decision is a form submission, and
   Chromium and WebKit refuse a redirect that follows a form POST under that policy. The
   handoff page navigates the browser onward instead of asking the server to.

## Troubleshooting

- **`421`**: the request's `Host` header is not on the allowlist `NC_MCP_ALLOWED_HOSTS`
  builds. Check that the public host (and, if the client sent a port, `host:port`) is
  covered.
- **"store key mismatch" at startup**: the data key file does not match the key the store
  was written with. Restore the original key file; a new one cannot be generated to replace
  it.
- **The single sign-on proof is never accepted**, and the consent screen keeps offering the
  sign-on step: `NC_MCP_OIDC_PROVIDER_ID` or `NC_MCP_OIDC_MAPPING` most likely does not match
  how `user_oidc` is actually configured (unique user id, `sub` as the mapping claim), so the
  derived account id never equals the one Nextcloud's Login Flow v2 produced.
- **`401` on `/mcp` without a token is expected.** It is the discovery response every OAuth
  client relies on, not a misconfiguration.

## Related

- OAuth 2.1 in the ExApp mode: [oauth-setup.md](./oauth-setup.md)
- Installing the ExApp itself: [exapp-install.md](./exapp-install.md)
- What a user enters into a client: [client-setup.md](./client-setup.md)
