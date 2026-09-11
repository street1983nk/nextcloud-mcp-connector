# ExApp installation

## Install the published app (start here)

Two ways, and the second one works on every version. `mcp_connector` is the app id.

**From the app store**, on Nextcloud 34.0.3 and later: open Apps, find MCP Connector, press
**Deploy and enable**. Earlier versions of Nextcloud list no external app in that interface
at all, which is an upstream bug, so there use the command below.

**With occ**, on any version:

```
occ app_api:app:register mcp_connector
```

The daemon is optional in that command: AppAPI takes the one marked default. If the
instance has several, name the one to deploy into, and `occ app_api:daemon:list` prints
their names with the default marked `*`:

```
occ app_api:app:register mcp_connector <daemon-config-name> --wait-finish
```

Then give the app the one thing it cannot know by itself: the address it is reachable under
from the internet, without a trailing slash. Left unset it names a loopback default and no
assistant can complete a connection.

- **Installed from the app store:** enter it in Nextcloud, under Administration settings,
  MCP Connector. A store installation has no way to pass a deploy variable, so this is the
  way there, and the value entered here wins over the variable.
- **Registered with occ:** pass it right away, because the daemon injects a variable only at
  registration time:

```
occ app_api:app:register mcp_connector \
  --env "NC_MCP_PUBLIC_URL=https://cloud.example.com/exapps/mcp_connector"
```

The other switches, all optional, are in [oauth-setup.md](./oauth-setup.md).

Check that it came up:

```
occ app_api:app:list
```

It answers `mcp_connector (MCP Connector): <version> [enabled]`. Removing the app again is
[uninstall.md](./uninstall.md).

Everything below this section is about building and running the app from source in a local
test topology. An administrator installing the published app does not need it.

---

**Status:** proven on a local HaRP topology
**Measured on:** 2026-08-15; the credential flood numbers in the Security notes on 2026-08-19
**Scope:** installing this app as an AppAPI ExApp with the HaRP deploy daemon, on
`docker compose`, from a locally built image. Nextcloud All-in-One is the second smoke step
and is handled as a named handoff to phase 5 in the Nextcloud AIO section below.

Everything below was executed against Nextcloud 34.0.2 with AppAPI 34.0.0 and the image
`ghcr.io/nextcloud/nextcloud-appapi-harp:release`. The outputs in the Evidence section are
copied verbatim from that run.

## Topology

Four containers, described by `compose.exapp.yml` (project name `nc-mcp-exapp`):

| Service | Image | Why it is there |
|---------|-------|-----------------|
| `caddy` | `caddy:2` | Reverse proxy on `127.0.0.1:8081`. It routes `/exapps/*` to HaRP and everything else to Nextcloud. |
| `nextcloud` | `nextcloud:34-apache` | The server. It publishes no port of its own and is reachable through Caddy only. |
| `appapi-harp` | `ghcr.io/nextcloud/nextcloud-appapi-harp:release` | The deploy daemon. It starts the ExApp container over the Docker socket and proxies every request to it. |
| `registry` | `registry:2` | A loopback registry on `127.0.0.1:5000` that holds the locally built ExApp image. |

**The reverse proxy is not optional.** AppAPI reaches an ExApp under
`<nextcloud_url>/exapps/<appid>`, which means through the public URL of the Nextcloud
instance and therefore through whatever sits in front of it. Without a `/exapps/*` rule the
installation fails at the very first step, the heartbeat, with "heartbeat check failed.
Make sure that Nextcloud instance and ExApp can reach it other." Nextcloud All-in-One ships
exactly this rule in its bundled Caddy, and `deploy/Caddyfile` rebuilds it.

The app declares thirteen routes, and they are its whole external surface. As of phase 4 they
are these, in the order `appinfo/info.xml` declares them:

| Route | Access | What it is for |
|-------|--------|----------------|
| `/mcp` | public | The MCP transport. Public since plan 03-01, because the OAuth discovery flow begins with a 401 that this app has to answer itself; the protection it replaced is a bearer check inside the container. |
| `/.well-known/oauth-protected-resource/mcp` | public | RFC 9728, the document the 401 points at. |
| `/.well-known/openid-configuration` | public | The same document at the one path that survives a stripped prefix. |
| `/.well-known/oauth-authorization-server` | public | RFC 8414, and the rewrite target of the optional reverse proxy rule. |
| `/connect`, `/connect/wait` | public | The browser onboarding for clients that cannot speak OAuth (AUTH-02). |
| `/authorize`, `/authorize/consent` | public | The authorization endpoint and the consent screen. |
| `/authorize/decide` | public | The decision behind the consent screen. It resolves the signed in Nextcloud account out of the AppAPI header HaRP writes on a public route too, and the app grants nothing unless that account is the one that signed in (CR-01). |
| `/token`, `/register`, `/revoke` | public | The machine endpoints of the authorization server. |
| `/connections` | public | The per user page of phase 4: it lists the connections of the signed in account and carries the pause switch. Public for the same measured reason as `/authorize/decide`: a `user` route feeds the HaRP blacklist with exactly the rejections this page produces as normal traffic (CR-01). |

Every route is public, and public here means only that HaRP does not decide access. Each one
carries its own check: `/mcp` refuses any request without a bearer this app issued,
`/authorize/decide` and `/connections` compare the account HaRP resolved with the account the
request is about, and the machine endpoints authenticate their client. HaRP signs every
forwarded request with `AUTHORIZATION-APP-API` and writes the resolved account into it, empty
when the caller sent no Nextcloud credential, which is why an app can do that check on a
public route at all. The OAuth half is configured in [oauth-setup.md](./oauth-setup.md), which
also lists the four deploy variables the manifest declares.

Two more properties of the file are deliberate:

* Every published port binds to `127.0.0.1`. The instance carries throwaway credentials and
  runs with the bruteforce guard disabled, so a `0.0.0.0` binding would hand a trivially
  ownable Nextcloud to everyone on the same network.
* HaRP publishes no port at all. Caddy reaches it inside the compose network, which is the
  only place that needs to reach it.

## Install

```
export HP_SHARED_KEY="$(openssl rand -hex 32)"
docker compose -f compose.exapp.yml up -d --wait
bash scripts/bootstrap_exapp.sh
docker compose -f compose.exapp.yml down        # when you are done, keeps the volume
```

The first line is not optional. The compose file used to carry a fixed default for
`HP_SHARED_KEY`, which meant the documented command produced the same key on every machine
that ever ran it, published in this repository, and the bootstrap then wrote it into
`.env.exapp` where it looked generated (WR-11). `up` now fails with a named variable until a
real one is exported, and the bootstrap refuses anything that is not 64 hex characters.

`down` stops the four services of the file. The ExApp container is not one of them: the
deploy daemon created it over the Docker socket, so it keeps running and has to be stopped
separately, which is also why the compose network stays in use until then.

```
docker stop nc_app_mcp_connector
```

The bootstrap script is idempotent: it creates the test users and their calendars, installs
or enables AppAPI, registers the HaRP daemon, builds the image, pushes it into the loopback
registry and registers the app. A second run is a no-op apart from a fresh app password in
`.env.exapp`.

The registration overrides exactly three fields of `appinfo/info.xml`: registry, image and
image tag. The manifest keeps pointing at `ghcr.io`, because that is the state the app store
will see, while the local test needs an image that exists today. Nothing is published; the
image never leaves the loopback registry.

## Evidence

All commands below were run on **2026-08-15** on the development host, in the order shown.

### 1. The app is registered and enabled

```
docker compose -f compose.exapp.yml exec -T --user www-data nextcloud php occ app_api:app:list
ExApps:
mcp_connector (MCP Connector): 0.1.0 [enabled]
```

The deploy daemon it belongs to:

```
docker compose -f compose.exapp.yml exec -T --user www-data nextcloud php occ app_api:daemon:list
Registered ExApp daemon configs:
+-----+-------------------+---------------------+----------------+----------+------------------+--------------+---------+------------------+-------------------------+
| Def | Name              | Display name        | Deploy ID      | Protocol | Host             | NC Url       | Is HaRP | HaRP FRP Address | HaRP Docker Socket Port |
+-----+-------------------+---------------------+----------------+----------+------------------+--------------+---------+------------------+-------------------------+
| *   | harp_proxy_docker | Harp Proxy (Docker) | docker-install | http     | appapi-harp:8780 | http://caddy | yes     | appapi-harp:8782 | 24000                   |
+-----+-------------------+---------------------+----------------+----------+------------------+--------------+---------+------------------+-------------------------+
```

### 2. The container the daemon started is healthy

```
docker ps --filter name=mcp_connector --format '{{.Names}} {{.Status}}'
nc_app_mcp_connector Up 3 minutes (healthy)
```

### 3. Deploy and init both reached 100

The lifecycle state AppAPI keeps for the app, read out of the `ex_apps` table:

```
docker compose -f compose.exapp.yml exec -T --user www-data nextcloud php -r '
require_once "/var/www/html/lib/base.php";
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$q = $db->getQueryBuilder();
$q->select("appid","version","enabled","port","status")->from("ex_apps");
foreach ($q->executeQuery()->fetchAll() as $row) { echo $row["appid"], " | enabled=", $row["enabled"], " | port=", $row["port"], " | status=", $row["status"], PHP_EOL; }
'
mcp_connector | enabled=1 | port=23000 | status={"deploy":100,"init":100,"action":"","type":"","error":"","deploy_start_time":1786788523,"init_start_time":1786788531}
```

`init: 100` is the interesting number: `POST /init` was answered with 200 and the app then
reported progress 100 back to Nextcloud over OCS. An app that answers 200 and stays silent
hangs at 0 percent until the init timeout expires.

### 4. The MCP route rejects an anonymous request

```
curl -i -s -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  http://127.0.0.1:8081/exapps/mcp_connector/mcp
HTTP/1.1 403 Forbidden
Content-Length: 13
Content-Type: text/plain
Via: 1.1 Caddy
```

The 403 comes from HaRP, not from the app: at the time of this run the route was declared with
`access_level` `USER`, and HaRP could not resolve a user for the request. The request never
reached the container.

That is the one measurement on this page the manifest has since moved past. Since plan 03-01
the route is `PUBLIC` and the refusal is the app's own. Measured again on **2026-08-19** with
the same call, twenty times: `401` every time, and the Nextcloud access log grew by nothing at
all, because HaRP asks Nextcloud who the caller is only for a request that carries an
`Authorization` header. The Security notes section below turns that into numbers.

### 5. The MCP route serves a request with a user app password

```
curl -i -s -u "alice:<app password>" -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"evidence","version":"1.0"}}}' \
  http://127.0.0.1:8081/exapps/mcp_connector/mcp
HTTP/1.1 200 OK
Cache-Control: no-cache, no-transform
Content-Type: text/event-stream
Mcp-Session-Id: 1d92d8a13d114fafac3f6926ffa93489
Server: uvicorn
Via: 1.1 Caddy

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{...},"instructions":"Read and create content in the user's own Nextcloud. This server can never delete, overwrite or re-share anything.","protocolVersion":"2025-06-18","serverInfo":{"name":"MCP Connector","version":"0.1.0"}}}
```

`Server: uvicorn` is the proof that the answer came out of the ExApp container. HaRP resolved
the app password to the user `alice` and signed the request with the AppAPI headers.

### 6. The lifecycle paths are not reachable from outside

```
curl -i -s http://127.0.0.1:8081/exapps/mcp_connector/heartbeat
HTTP/1.1 502 Bad Gateway
Server: Caddy
Date: Sat, 15 Aug 2026 10:12:07 GMT
Content-Length: 0
```

Two controls hold here, and this measurement shows the outer one. `appinfo/info.xml`
declares no route that matches `/heartbeat`, `/init` or `/enabled`, and HaRP additionally
blocks those three paths for anything that does not carry a valid AppAPI signature: it logs
"Only requests from AppAPI allowed to the internal endpoints" and drops the connection
without an answer, which Caddy reports to the client as a `502` with an empty body. The
plan expected a `404` from the route mismatch; the measured behaviour is stricter, because
the request is dropped one layer earlier. Either way the container never sees the call, and
`/enabled` cannot be used from the outside to switch the app off.

## Development loop

Rebuilding an image per iteration is slow. AppAPI has a second deploy mode for that, and the
script knows it:

```
docker compose -f compose.exapp.yml up -d --wait
bash scripts/bootstrap_exapp.sh --manual
```

This registers a `manual-install` daemon and the app on a fixed port with a fixed secret, so
a locally started process serves the requests:

```
set -a && . ./.env.exapp && set +a
APP_PORT=23001 nc-mcp-exapp
```

**Do not add `APP_HOST=0.0.0.0` here.** That is what this document used to print, and it
contradicts the loopback rule two sections above (WR-12). The default of `entry_exapp` is
already `127.0.0.1`, and it has to stay that way: in this mode there is no HaRP and no
manifest filter in front of the process, so `/init` and `/enabled` are reachable directly and
are guarded by `APP_SECRET` alone, which sits in `.env.exapp` in the same directory.
`/heartbeat` authenticates nothing at all by contract.

Docker Desktop reaches a service bound to the host's loopback through
`host.docker.internal`, which is the address the manual daemon is registered with, so
nothing else is needed on Windows or macOS. On a plain Linux Docker, where
`host.docker.internal` is not a loopback path, forward the port explicitly instead of
opening the process to the LAN:

```
socat TCP-LISTEN:23001,fork,bind=172.29.42.1 TCP:127.0.0.1:23001
```

`172.29.42.1` is the gateway of the compose network from `compose.exapp.yml`, so the
listener is reachable for the containers of this topology and for nothing else.

Restart that process after every re-registration. `APP_SECRET` is handed out at registration
time, and a process that still holds the previous one answers 401 to everything while
Nextcloud rejects everything it sends.

## Known pitfalls

The first four were the ones that actually cost time in this setup; the fifth is named
here before it does.

**1. No reverse proxy in front of Nextcloud.** The heartbeat is fetched from
`<nextcloud_url>/exapps/<appid>/heartbeat`, so a container name in `nextcloud_url` is not
enough: that URL has to be served by something that knows the `/exapps/` prefix. Pass
`nextcloud_url` to `occ app_api:daemon:register` explicitly as well, because AppAPI silently
downgrades `https` to `http` when the field is missing.

**2. A non-root ExApp image needs a writable `/certs`.** HaRP installs the FRP client
certificate by running commands inside the running container, with the identity of that
container. As uid 10001 the `mkdir -p /certs/frp` fails with "Permission denied", the
certificate installation answers 500, the tunnel client falls back to a plaintext handshake,
the FRP server closes the connection and every heartbeat is answered with 503. The Dockerfile
therefore creates `/certs` owned by the unprivileged user. The same call also tries to run
`update-ca-certificates`, which stays impossible without root; that failure is logged by HaRP
and is harmless as long as the instance is not behind a private certificate authority.

Since WR-04 the container no longer accepts the fallback. `entrypoint.sh` waits up to
`FRP_CERT_WAIT_SECONDS` (60 by default) for the three certificate files in `/certs/frp`
(`client.crt`, `client.key`, `ca.crt`; the directory alone appears before the files and is
not enough, IN-02) and then refuses to start, because
the fallback writes `transport.tls.enable = false` and sends `HP_SHARED_KEY` over the wire in
the clear, which hands whoever reads that path the right to register their own tunnel. On a
trusted local network the downgrade can be taken deliberately with `ALLOW_PLAINTEXT_FRP=1`;
there is no way to take it by accident.

**3. The ExApp port has to be inside the FRP range.** The FRP server inside HaRP accepts
remote ports 23000 to 23999 only. A registration with any other port produces
`start error: port not allowed` in the container log and a 503 on every request, because
HAProxy then has no backend at all. AppAPI picks from the same range when the registration
carries no port.

**4. HaRP caches the app record.** After a failed registration the daemon keeps the old
host and port for a while, so a corrected re-registration can still fail with a 503 that
looks identical to the original error. Recreate the container to clear it:

```
docker compose -f compose.exapp.yml up -d --no-deps --force-recreate appapi-harp
```

`HP_LOG_LEVEL=info` in the environment makes the daemon log the line that says where a
request was actually routed, which is the fastest way to tell a cache problem from a
configuration problem.

**5. A deployment without `HP_SHARED_KEY` runs `/mcp` into a 421 trap** (IN-04, issue #4).
The DNS rebinding protection of the MCP transport stays armed whenever that variable is
absent, because the entrypoint only disarms it for the HaRP tunnel, and until issue #4 the
allowlist behind it was localhost and nothing else. The `Host` header that arrives is
neither: behind the PHP proxy it is the container name, and in Nextcloud AIO it is the
public custom domain. The lifecycle routes sit before that check, so the installation turns
green and every `/mcp` request afterwards answers 421 with the body `Invalid Host header`
and a single log line.

Since issue #4 the allowlist carries the addresses this deployment answers to without any
variable: the host of `NEXTCLOUD_URL` and the host of the public address of this app when
one is set. That is what makes AIO work out of the box, because AIO passes
`NEXTCLOUD_URL=https://<custom domain>` and its HaRP backend forwards the `Host` header
unchanged. `NC_MCP_ALLOWED_HOSTS` stays the way to name a host that is neither of the two,
for example a second proxy in front of the instance, and the process still logs a warning
at startup when it has no shared key, no allowlist and no address it could derive one from.

**Why AIO never takes the HaRP branch of the entrypoint.** AIO registers its HaRP daemon
with `exapp_direct => true`, and `DockerActions::buildDeployEnvs` skips `HP_SHARED_KEY`,
`HP_FRP_ADDRESS` and `HP_FRP_PORT` for a direct connect daemon. The container therefore
runs the plain TCP path with the host check armed, which is correct: it is reachable on a
port, so the check is the defence that belongs there.

## Security notes for production

**The Docker socket is mounted into HaRP, and that is root on the host.** A deploy daemon
that starts containers cannot work without it, so this is accepted for a local test topology
that listens on loopback only and is stopped afterwards (threat T-02-31). It is not a
recommendation for a server: there, run HaRP on a host that does nothing else, or use the
Kubernetes daemon, and never expose its port.

**The registry in this topology is unauthenticated and unencrypted** (threat T-02-32). It
exists because the image is not published before the store submission, it listens on
`127.0.0.1` only, and it holds exactly one image. Do not copy that part into anything that
is reachable from a network.

**`.env.exapp` carries working secrets** (app passwords, the HaRP shared key and the app
secret). It is git-ignored; `.env.exapp.example` documents the variable names and holds
placeholders only.

### A flood of invalid credentials is amplified against Nextcloud

This is the one abuse case that costs your Nextcloud rather than this app, and the numbers
below are measured, not estimated. Both runs sent 200 requests to
`/exapps/mcp_connector/mcp`, 20 in flight, on **2026-08-19** against Nextcloud 34.0.2 with
AppAPI 34.0.0 and HaRP:

```
uv run --no-sync pytest tests/integration/test_credential_flood.py -m integration -q -s
```

| 200 requests with | Answer | Nextcloud requests | Per attacker request | Brute force entries |
|-------------------|--------|--------------------|----------------------|---------------------|
| an invalid bearer | 200 x 401 | 200 | 1.00 | 0 |
| an invalid basic | 200 x 401 | 200 | 1.00 | 27 |
| no `Authorization` header | 20 x 401 | 0 | 0.00 | 0 |

**Every request that carries any `Authorization` header costs one full Nextcloud PHP round
trip**, and there is nothing this app can do about it: HaRP resolves the caller for each such
request with a `GET /index.php/apps/app_api/harp/user-info`, on public routes as well, and it
caches that answer for cookie sessions only. Our own token check adds nothing to Nextcloud, but
it does not save the round trip either, and it caches positive results only, so an invalid
bearer never becomes cheap. The last row is the useful part of the finding: a flood without
credentials costs Nextcloud nothing, so the rule you write only needs to look at requests that
carry credentials.

**An invalid basic password additionally throttles your instance for everybody.** Nextcloud
counts failed logins per source address, and in a HaRP topology that address is HaRP's, not the
attacker's: the measurement found the entries on the HaRP container address while the gateway,
the reverse proxy and the ExApp container all stayed at zero. Every user of every ExApp behind
that proxy therefore shares one brute force counter. The counter also explains the low number
in the table: once the guard has reached its maximum delay it refuses without checking, so 200
rejected logins produce 27 entries and the flood becomes cheaper for Nextcloud and more
expensive for your users at the same time.

**`/mcp` carries no throttle of its own, and that is deliberate.** Rate limiting the actual
work of this server would be a denial of service with our own name on it (D-37), and the
manifest declares no `bruteforce_protection` on that route because the OAuth discovery flow
begins with a rejected request by specification, so a throttle armed on that status would lock
out legitimate first connections (T-02-21). The authorization endpoints of this app do carry
their own limits (`oauth/throttle.py`), which is a different problem: those are the routes that
make this server start a Nextcloud login flow.

**The brake belongs in your reverse proxy**, as a rate limit rule on the
`/exapps/mcp_connector/` path: that is the only place that can refuse a request before HaRP
asks Nextcloud about it, and the only place that still knows the address of the client. Set the
ceiling far above one real session: a single assistant conversation can issue dozens of tool
calls, and each one is a legitimate request with a valid bearer.

Caddy, with the `rate_limit` module
(`xcaddy build --with github.com/mholt/caddy-ratelimit`, it is not part of a stock build):

```
route /exapps/mcp_connector/* {
	rate_limit {
		zone mcp_connector {
			match {
				header Authorization *
			}
			key {remote_host}
			events 120
			window 1m
		}
	}
	reverse_proxy appapi-harp:8780
}
```

nginx, with the HaRP upstream named `harp`, the same spelling
[spike-discovery.md](./spike-discovery.md) uses for its rules:

```
limit_req_zone $binary_remote_addr zone=mcp_connector:10m rate=2r/s;

location ^~ /exapps/mcp_connector/ {
    limit_req zone=mcp_connector burst=60 nodelay;
    limit_req_status 429;
    proxy_pass http://harp:8780;
    proxy_read_timeout 1800s;
}
```

The long read timeout is not optional in the nginx rule: MCP answers stream, and the default
60 seconds cuts a long tool call.

**Watch the counter and clear it.** Both commands are the ones
[client-setup.md](./client-setup.md) points a user at when a wrong app password locked an
address out:

```
docker compose -f compose.exapp.yml exec -T --user www-data nextcloud php occ security:bruteforce:attempts <ip>
docker compose -f compose.exapp.yml exec -T --user www-data nextcloud php occ security:bruteforce:reset <ip>
```

The address to ask about is the one Nextcloud sees, so on a HaRP topology start with the
address of the HaRP container rather than the address of whoever you suspect. Do not switch the
brute force protection off on a production instance; the throwaway topology of this document
does that on purpose because nobody can reach it.

## Nextcloud AIO

Success Criterion 1 of phase 2 names two smoke targets: the `docker compose` HaRP topology
above, and Nextcloud All-in-One. This section records the decision on the second one, because
D-31 requires it to be handed over with a reason rather than dropped in silence.

**Decision, phase 5, 2026-08-19: deliberately descoped, not run, and not silently dropped.**
The smoke stays unexecuted because its precondition cannot be produced here, and it goes into
the phase verification as a descoped line rather than as a finished one. What is missing is
named in one sentence: a publicly resolvable domain with a valid public TLS certificate and
inbound reachability on ports 80 and 443, which the AIO mastercontainer validates before it
starts any container an ExApp could be installed into. The six steps that would follow are
listed at the end of this section, unchanged, and step 3 still rests on the unverified
research assumption A6. Nothing on this page and nothing in the phase claims AIO coverage,
and no measurement of this project was taken on AIO.

**Decision of phase 2, for the record: not run on this development host.**

**Where it stops.** The AIO mastercontainer refuses to start the Nextcloud stack until its
setup step validates a domain: it wants a publicly resolvable domain name with a valid, public
TLS certificate and inbound reachability on ports 80 and 443, and it runs that check before it
will bring up any container the ExApp could be installed into. The abort boundary in D-31 names
exactly this, a step that demands a publicly resolvable domain, a public certificate or an
outward port forward, as disproportionate for a loopback development machine, so the smoke stops
at the domain validation and does not proceed to installing the app.

A second reason reinforces the same call on this specific host. The AIO mastercontainer drives
the Docker daemon through a mounted socket to create and manage its own containers. That daemon
also runs the owner's in-daily-use test instance (`nc-mcp-test` on `127.0.0.1:8080`), and the
standing instruction is to never touch it. Starting a socket-privileged mastercontainer next to
it is a risk not worth taking for a reachability smoke that is already blocked by the domain
requirement.

**What is still missing, for phase 5.** To run the AIO smoke, these steps remain, in order:

1. A host with a publicly resolvable domain and a valid TLS certificate, or the AIO Let's
   Encrypt path with inbound 80 and 443 open to that domain.
2. Start the AIO mastercontainer and complete its domain validation and initial setup.
3. Enable the optional AppAPI and HaRP container in the AIO interface. Research assumption A6
   is that this is the only AIO specific action needed, but it is unverified: it may also
   require registering the HaRP deploy daemon, which the compose bootstrap does explicitly.
4. Install this app as an ExApp through the AIO managed AppAPI, from a published image or the
   store, since the loopback registry of the compose topology is not present in AIO.
5. Repeat the permission fidelity smoke over the AIO topology: alice finds her own content and
   bob finds nothing of hers, over files, notes and unified search, the same proof
   `tests/integration/test_permission_fidelity_exapp.py` runs against the compose topology.
6. Record `occ app_api:app:list` from the AIO instance as the evidence for case A.

**Handoff.** This stayed an open item through phase 5 and is now a descoped one with a named
precondition, which is a different thing from a forgotten one: the work is described, the
blocker is a host property and not a code property, and nothing in the project claims the
result. It is recorded in the plan summary of 05-08 and in the project state, not only here.

## Nextcloud 34.0.2 has no interface for installing or removing an ExApp, 34.0.3 has

**Fixed upstream in Nextcloud 34.0.3, and measured here on 34.0.3.2 on 2026-08-20.** The
finding below is [nextcloud/app_api#971](https://github.com/nextcloud/app_api/issues/971) and
[nextcloud/server#61709](https://github.com/nextcloud/server/issues/61709), resolved by
[server PR 62276](https://github.com/nextcloud/server/pull/62276) and backported to 34.0.3.
On 34.0.2 and earlier everything below still applies, and occ remains the reliable path on
every version, which is why this page keeps describing it first.

What the interface does on **34.0.3.2** (`occ status`, not a Docker tag), signed in as an
account in the `admin` group, after the app store cache was invalidated by overwriting its
`timestamp` with `0`:

```
Your apps, one table row:   MCP Connector   0.1.2   Harp Proxy (Docker)   [Disable]  [...]
A not installed ExApp:      Context Chat Backend   5.4.1                  [Deploy and enable]
Row actions while enabled:  Limit to groups, Rate the app, Report a bug, Show details
Row actions while disabled: Limit to groups, Remove, Rate the app, Report a bug, Show details
```

![The Remove entry in the row actions of a disabled ExApp](screenshots/exapp-remove-button.png)

Three details are worth knowing before looking for the buttons:

- The **install button of an ExApp reads "Deploy and enable"**, next to the "Download and
  enable" of a PHP app. Where a normal app shows the "Featured" badge, an ExApp row shows the
  name of its deploy daemon.
- The **remove entry lives in the row actions and only while the app is disabled**. AppAPI
  computes it as `canUnInstall = !active && removable && ...`
  (`apps/app_api/lib/Controller/ExAppsPageController.php:213`), so an enabled ExApp offers
  Disable and no Remove. That is not a missing button, it is a two step removal.
- The `appstore` app itself still does not know about ExApps: its OCS route
  `/ocs/v2.php/apps/appstore/api/v1/apps` answers 2 650 705 bytes without a single
  `mcp_connector` in them, and `apps/appstore/lib/Controller/ApiController.php` still carries
  `'app_api' => false`. The page pulls the ExApps in itself over
  `/apps/app_api/apps/list`, and that request is exactly what 34.0.2 never made.

The fix is not visible as a new word in the bundle, which is why a file by file comparison of
the `appstore` app between the two images looks empty at first sight. Both images ship app
version 1.0.0 and, outside `l10n/`, only five files differ, of which one is the interesting
one:

```
dist/appstore-main.mjs   95762 bytes (34.0.2)  ->  95841 bytes (34.0.3)
34.0.2: no match for Promise.allSettled([ ... initialize ... ])
34.0.3: Promise.allSettled([V(),Y(),e.isEnabled?e.initialize():Promise.resolve()])
"exapp" in dist/AppstoreBrowse-*.chunk.mjs: 0 occurrences in both
```

`e` is the minified name of the `external-apps` store, so the merge title
`fix(appstore): initialize the exApps store when enabled` is literally what changed.
Full protocol, including the account, the cache step and the counter checks:
[06-07-MEASUREMENTS.md](../.planning/phases/06-h-rtung-eigennachweise-und-conference-reife/06-07-MEASUREMENTS.md).

The history below stays because it is what an administrator on 34.0.2 and earlier still sees.
Measured on **2026-08-19** against Nextcloud 34.0.2 with AppAPI 34.0.0, while looking for the
Install button of this app:

**No ExApp appears in the app list at all.** Not this app, and not `context_agent`,
`visionatrix` or `stt_whisper2` either. `OCS /apps/appstore/api/v1/apps` answers with 694 apps
and `exappCount=0`, while the AppAPI backend is healthy and answers
`GET /index.php/apps/app_api/apps/list` with `{"id": "mcp_connector", "version": "0.1.0",
"canInstall": true}`, and the app store cache in the instance contains the entry with
`platform >=32.0.0 <35.0.0`.

The break is in the frontend of the new `appstore` app 1.0.0:

```
apps/appstore/lib/Controller/ApiController.php:383   $apps = $this->appFetcher->get();
apps/appstore/lib/Controller/ApiController.php:459   'app_api' => false,
```

The bundle ships an external apps store with an `initialize` function, and that word occurs
exactly once in the whole bundle, in its own definition. A network trace of the page shows
`/apps/app_api/apps/list` is never requested. The older ExApp page of AppAPI is not a fallback:
its route is still declared while the method is gone, so `/index.php/apps/app_api/apps`
answers `500 Method ExAppsPageController::viewApps() does not exist`. An installed ExApp is
invisible to the list as well, because the core app manager never learns about it
(`occ app:list | grep -c mcp_connector` is `0` while the app is enabled and healthy).

**What that means for an administrator on 34.0.2 and earlier:** install with `occ` as
described in [Install the published app](#install-the-published-app-start-here) at the top
of this page, and remove with `occ` as described in [uninstall.md](./uninstall.md). Both
are the documented paths of AppAPI and work on 32, 33 and 34 alike; on those versions the
interface is the part that is missing, not the mechanism. Nothing about that changed on
34.0.3: the interface arrived, `occ` stayed the path that works on every version.

**And one thing to know before trying the store path anyway.** The wire call the Install
button would make was run by hand for the measurement:

```
POST /index.php/apps/app_api/apps/enable/mcp_connector/harp_proxy_docker  {"deployOptions": {}}
HTTP 500 after 106.5 s   {"data":{"message":"Failed to start ExApp installation"}}
```

No dialog and no question about environment variables, exactly as expected with a single
configured Docker daemon, which is also why nothing sets `NC_MCP_PUBLIC_URL` on that path.
The container was created and then restarted in a loop with exit code 2, because release
`0.1.0` refuses to start without that variable. The current code does not: it logs the
problem and shows a setup state on its own pages instead of exiting, which is what makes a
one click install viable at all. Until a release carries that change, a store install ends in
a crash loop, and the remedy is the `occ` registration this page describes.

## Related

- Turning on OAuth 2.1 on this topology: [oauth-setup.md](./oauth-setup.md)
- Manifest and routes: [../appinfo/info.xml](../appinfo/info.xml)
- Topology: [../compose.exapp.yml](../compose.exapp.yml), [../deploy/Caddyfile](../deploy/Caddyfile)
- Installation script: [../scripts/bootstrap_exapp.sh](../scripts/bootstrap_exapp.sh)
- Requirement `EXAPP-01`, decision D-31
