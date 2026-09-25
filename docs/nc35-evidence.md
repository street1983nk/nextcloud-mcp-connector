# Evidence for the Nextcloud 35 version window

**Date:** 2026-09-16, end-to-end run added 2026-09-17
**Subject:** why `appinfo/info.xml` declares `max-version="35"` since this date
**Status:** all five checks done against a running 35.0.0 instance

Nextcloud 35 ("Hub 26 Summer") was released on 2026-09-15. Until the window was raised,
this app declared `max-version="34"` and Nextcloud 35 refused to install it. That refusal
is not a warning, it blocks the app outright, including for people who already run it and
upgrade their server. This file records what was actually run before the window moved, so
the claim can be checked rather than believed.

## The instance the evidence comes from

At the time of the test the official Docker image for Nextcloud 35 did not exist yet:
`latest`, `stable` and `production` on Docker Hub all still resolved to 34.0.4 on
2026-09-16. The instance was therefore built from the released source package:

- `nextcloud-35.0.0.zip` from `download.nextcloud.com`
- SHA-256 `552b13b3ee32ba8892aa02578c2ff10ea46cbd83d3bfcfbc4317a26d359aa39a`,
  verified against the published checksum file
- laid over the official `nextcloud:34-apache` image, which carries PHP 8.5.9.
  Nextcloud 35 requires PHP 8.3 or newer and refuses 8.6 or newer
  (`lib/versioncheck.php`), so 8.5.9 is inside the supported range.

`occ status` on that instance reports:

```
  - installed: true
  - version: 35.0.0.10
  - versionstring: 35.0.0
```

The instance was isolated: its own container, its own volume, no published port. It did
not touch the throwaway topology from `compose.exapp.yml`.

## Check 1: AppAPI exists for Nextcloud 35

`app_api` version `35.0.0` ships with the release and is enabled. Upstream declares it for
this server generation only (`<nextcloud min-version="35" max-version="35"/>` on the
`stable35` branch). Without AppAPI no ExApp can run at all, so this is the precondition for
everything below.

## Check 2: the old window is refused (the user-facing blocker)

With the manifest as it stood, `max-version="34"`:

```
$ occ app:enable mcp_connector
App "MCP Connector" cannot be installed because it is not compatible with this version of the server.
```

## Check 3: the new window is accepted

Same instance, same app, the single value changed to `max-version="35"`:

```
$ occ app:enable mcp_connector
mcp_connector 0.1.13 enabled
```

## Check 4: the coupling to AppAPI is unchanged

This app is a manifest plus a container: it contains no PHP at all (zero `.php` files in
the repository). It therefore cannot break on a changed server PHP API. What it does depend
on is AppAPI, at exactly five points, and all five were read out of the running 35.0.0
instance rather than out of a changelog:

| What the app uses | Where it is in this repo | Present in AppAPI 35.0.0 |
|---|---|---|
| header `authorization-app-api` | `src/mcp_connector/exapp/auth.py` | yes, `lib/Middleware/AppAPIAuthMiddleware.php` |
| header `ex-app-id` | `src/mcp_connector/exapp/auth.py` | yes, `lib/Service/AppAPIService.php` |
| header `ex-app-version` | `src/mcp_connector/exapp/auth.py` | yes, same file |
| route `/ocs/v2.php/apps/app_api/ex-app/status` | `src/mcp_connector/exapp/status.py` | yes, `appinfo/routes.php` |
| route `/ocs/v2.php/apps/app_api/api/v1/ex-app/config` | `src/mcp_connector/oauth/crypto.py` | yes, same file |

## Check 5: the end-to-end run through HaRP

Done on 2026-09-17, the day after the four checks above. This was the open half: it needs
the full topology, and the machine had only one, occupied. `compose.nc35.yml` is the second
one, and `scripts/bootstrap_exapp.sh --nc35` installs this app into it the way AppAPI
installs it anywhere, through the HaRP deploy daemon.

```
$ export HP_SHARED_KEY="$(openssl rand -hex 32)"
$ docker compose -f compose.nc35.yml up -d --wait
$ bash scripts/bootstrap_exapp.sh --nc35
...
exapp mcp_connector: registered and deployed
exapp mcp_connector: enabled
mcp_connector (MCP Connector): 0.1.13 [enabled]
```

What then answered, over the whole chain (client, Caddy, HaRP, ExApp container, Nextcloud):

This table records the historical 21-tool run. The current tool count is held by
`tests/contract/test_tool_surface.py`.

| What was run | Result |
|---|---|
| `scripts/oauth_flow_check.py` | all seven steps, including the refusals: a decision without an independent identity is a 400, the credential of a connect page is shown once and the second read is a 400, and eleven token attempts end in a 429 with `Retry-After: 300` |
| `scripts/oauth_flow_check.py --measure` | success criteria 3 and 5 |
| `scripts/acceptance_all_tools.py` | all 21 tools of the registry answered |
| `pytest tests/integration -m integration` | 160 cases, one skip, one failure whose cause is the age of the local instance (see below) |

The suite needs two runs and not one, which is a property of the app and not of this
instance: `test_http_tool_call.py` starts a standalone HTTP server, and that entry point
refuses to start while `APP_ID` and `APP_SECRET` are set, because those two select the ExApp
credential mode and the server would then wait for a header it never gets. So the ExApp
cases run with the deploy environment and that one file runs without it. Both runs are green.

One case was red in this run, and the way it was read first is worth keeping, because it
is a mistake this document almost published. `test_an_account_without_an_addressbook_gets_the_occ_hint`
expects the "this account has no address book" refusal. It was red on the 35 instance and
red on the 34 one, and an account created fresh on either of them did not get the refusal
either: the search answers with an empty list, and `occ dav:list-addressbooks` shows the
default `contacts` book appearing during the call. That looked like proof that the refusal
had become unreachable, and the case was rewritten to assert the empty list.

It was not proof. Both local instances had been running for days with the Contacts app
enabled. The CI job builds its Nextcloud from scratch for every run, and there the refusal
happens exactly as the case expects; the rewritten version went red in CI within the minute
and was taken back. What the two local instances measured is their own age, not a behaviour
of Nextcloud 34 or 35, and the case now says so in its docstring: red here means recreate
the instance, not rewrite the case.

The lesson for this document is narrower than it looks. Two instances agreeing is not a
control when both are old in the same way, and the throwaway instance of CI was the third
opinion that settled it.

## Three defects this run found, all in the proof and none in the app

They are written down because each of them produced a wrong answer that looked like a right
one, which is the only kind worth recording.

1. **Four integration files addressed one topology by name.** `NC_CONTAINER`,
   `EXAPP_CONTAINER` and the compose file were constants pointing at the 34 topology. Run
   against the 35 instance, those cases created accounts, stopped apps and counted
   bruteforce entries in the 34 instance while asserting against the 35 one. Nothing failed
   loudly: `test_a_deleted_account_is_gone_from_the_list` simply reported a product defect
   that did not exist. The names now live in `tests/integration/topology.py` and are read
   from the environment, with the 34 values as the defaults.
2. **The first Nextcloud 35 bootstrap was a copy of `bootstrap_exapp.sh`** with two
   constants changed. The three it did not change, the loopback port, the HaRP container and
   the compose network, produced exactly the same crossing: every HTTP step went to the 34
   instance, every `occ` step to the 35 one, the daemon was registered with the shared key of
   the wrong HaRP, and the deployed container was attached to the wrong network, where
   `NEXTCLOUD_URL=http://caddy` resolved to the wrong server. The copy is gone; `--nc35` is a
   flag of the one script, next to `--staging`.
3. **The instance came up without the pretty URL rewrite.** Because Nextcloud 35 was laid
   over a 34 image, `.htaccess` and `htaccess.RewriteBase` were the ones of the older tree:
   `POST /login` answered 200 with the login page while `POST /index.php/login` answered 303.
   Every headless sign in of the proof failed, which reads like a changed login API and is a
   stale rewrite. `occ config:system:set htaccess.RewriteBase --value=/` followed by
   `occ maintenance:update:htaccess` fixes it, and a topology built from an official image
   never has it.

## One change in Nextcloud 35 that operators should know about

`OC\Core\Controller\LoginController::tryLogin` checks the `Origin` header against the
trusted domains since this release; Nextcloud 34 has no such check. An instance reached under
a host **and a port** therefore needs that port in `trusted_domains`, or its login form
refuses every sign in with an invalid origin. This app is not affected, it never posts that
form, but Login Flow v2 runs in the browser of the person connecting, so their sign in is.

## What stays as it was

- **The store release remains its own decision**, taken after this run and not before it.
- **`compose.exapp.yml` and `compose.staging.yml` still pin a 34 image.** Docker Hub carries
  Nextcloud 35 tags since 2026-09-16, but they resolve to nothing: `docker pull
  nextcloud:35.0.0-apache` answers `no matching manifest for linux/amd64` and the tag's
  image list on the registry API is empty. `compose.nc35.yml` therefore still names the
  locally built image. Point all three at the official tag on the day it resolves.
