# Removing this app, and proving what is gone and what stays

**Status:** measured in both directions on a local HaRP topology
**Measured on:** 2026-08-19, against Nextcloud 34.0.2 with AppAPI 34.0.0 and HaRP
**Scope:** removing this app from a Nextcloud instance so that no credential it created
stays valid, and checking command by command what is gone afterwards and what is still
there: the audit log outlives the purge and goes only with the data volume.

Read the one sentence that makes this page necessary: **removing the app in the Nextcloud
interface does not delete its data, and every Nextcloud app password it created keeps
working.** That is not a suspicion, it is measured below, twice, with the numbers.

## The order, and why it is not a preference

```
# 1. While both halves still exist: the data volume AND the encryption key
occ mcp_connector:purge --force

# 2. Only then remove the app, together with its volume
occ app_api:app:unregister mcp_connector --rm-data
```

**Do not swap those two.** The encryption key lives in Nextcloud, the encrypted app
passwords live in the app's volume, and one is useless without the other. `--rm-data`
deletes the volume, and with it the only record of which Nextcloud app password belongs to
which connection. Every one of those credentials stays valid in Nextcloud afterwards, and
nothing is left that knows they exist. There is no repair for that state other than each
user going through Settings, Security, Devices and sessions and deleting entries by hand,
without knowing which ones.

If the app is currently disabled, enable it first. That is step 0 and it is not optional:

```
occ app_api:app:enable mcp_connector
```

Disabling the app removes its occ command with it. Measured: after
`occ app_api:app:disable`, `occ list | grep -c mcp_connector` answers `0`, so the one
command that could clean up is unavailable exactly when an administrator reaches for it.

## What each Nextcloud version does with a Remove click

Our dependency is `min-version 32`, `max-version 34`, so all three are supported, and they
do not behave alike.

| Version | What the interface offers | What it does to the data |
|---------|---------------------------|--------------------------|
| Nextcloud 32, 33 | The ExApp appears in the app management of `apps/settings`, with a "Delete data on remove" checkbox in the app details | Uninstall with the checkbox ticked calls the uninstall path with `removeData=true`; the volume goes. Nextcloud app passwords this app created are still not touched: they are not part of any AppAPI uninstall path. The volume is where `audit.sqlite3` lies, so this path removes the audit log with it, the same as `--rm-data` below. |
| Nextcloud 34 | Nothing. Measured on 34.0.2: no ExApp appears in the app list at all, so there is no Install button and no Remove button for this class of app | The path the frontend used to call for an ExApp is `disableExApp`: the container stops, and the app stays registered with its volume, its key and every app password intact |
| all three | `occ mcp_connector:purge --force` then `occ app_api:app:unregister mcp_connector --rm-data` | Every app password handed back, the seven tables of `oauth.sqlite3` emptied, the key deleted, then the volume with `audit.sqlite3` in it, the container and the registration removed |

The last row is the only one that is the same on every supported version, which is why this
page describes it as the way and everything else as background.

### The Nextcloud 34 finding in detail

On 34.0.2 the app management moved into a new app, `appstore` 1.0.0, and its API controller
fills the list from the core app fetcher only, with the external app flag hardcoded:

```
apps/appstore/lib/Controller/ApiController.php:383   $apps = $this->appFetcher->get();
apps/appstore/lib/Controller/ApiController.php:459   'app_api' => false,
```

The shipped frontend bundle does define an external apps store with an `initialize`
function, and that word appears exactly once in the whole bundle: in its definition.
Nothing calls it, and a network trace of the page confirms that
`/index.php/apps/app_api/apps/list` is never fetched, although that endpoint answers
correctly with `{"id": "mcp_connector", "canInstall": true}`. The older ExApp page of AppAPI
is not a way out either: the route is still declared and the method behind it is gone, so
`/index.php/apps/app_api/apps` answers `500 Method ExAppsPageController::viewApps() does not
exist`. An installed ExApp is invisible to that list as well, because the core app manager
never knows about it (`occ app:list | grep -c mcp_connector` answers `0` while the app is
enabled and healthy).

For an administrator on 34 this means: install and remove this app with `occ`, not with the
web interface. The commands are in [exapp-install.md](./exapp-install.md) for the install
half and on this page for the removal half.

## What the Remove path leaves behind, with numbers

Because 34.0.2 has no button, the measurement used the route the button calls. The
equivalence is not assumed, it is read off the instance: the route
`ExAppsPage#disableApp` (`GET /apps/disable/{appId}`) calls
`$this->service->disableExApp($exApp)` in `ExAppsPageController.php:383`, and
`occ app_api:app:disable` calls the same method in `Command/ExApp/Disable.php:46`.

The starting point was two real connections, one for each of two accounts, created over the
full chain, plus the row counts of all seven tables of the app's OAuth database.

```
$ occ app_api:app:disable mcp_connector
ExApp mcp_connector successfully disabled.
```

Eight checks, run in this order, immediately afterwards:

```
1 $ docker volume ls --format '{{.Name}}' | grep '^nc_app_mcp_connector_data$'
  nc_app_mcp_connector_data

2 $ docker run --rm -v nc_app_mcp_connector_data:/d:ro alpine:3 sh -c '
      apk add --no-cache sqlite >/dev/null 2>&1
      cp /d/oauth.sqlite3 /tmp/x.db
      for t in $(sqlite3 /tmp/x.db "select name from sqlite_master where type = '"'"'table'"'"'"); do
        printf "%s: " "$t"; sqlite3 /tmp/x.db "select count(*) from $t"
      done'
  access_tokens: 2
  auth_codes: 2
  authorizations: 2
  clients: 2
  flows: 0
  refresh_tokens: 2
  user_access: 0

3 $ occ app_api:app:list
  mcp_connector (MCP Connector): 0.1.0 [disabled]

4 $ docker ps -a --format '{{.Names}} | {{.Status}}' | grep nc_app_mcp_connector
  nc_app_mcp_connector | Exited (0) 3 seconds ago

5 $ the ExApp configuration of this app, read out of the database
  oauth_data_key | value length 324 | sensitive=1

6 $ one request per app password created before the removal, with that password
  app password of alice -> HTTP 200, OCS 200, identity 'alice'
  app password of bob   -> HTTP 200, OCS 200, identity 'bob'

7 $ occ user:auth-tokens:list alice
  | 18 | MCP Connector: Count base one | permanent | filesystem |
  $ occ user:auth-tokens:list bob
  | 20 | MCP Connector: Count base two | permanent | filesystem |

8 $ occ list | grep -c mcp_connector
  0
```

Check 6 is the one that matters. The app is removed as far as the interface is concerned,
its container is stopped, and two accounts are still reachable with credentials this app
created. Nextcloud answers each request with the identity of that account, so these are not
stale strings, they are working credentials. No AppAPI path touches them, on any version.

Check 2 uses a throwaway container with the volume mounted read only and copies the file to
`/tmp` first, because sqlite3 cannot open a read-only mounted database.

Two details of that measurement are worth carrying:

* The row copies stay the way they were. Nothing in the disable path opens that database.
* `auth_codes` holds short lived rows and is emptied by the app's own housekeeping on the
  next request, not by anything on this page. A `0` there means nothing was removed.

## What the occ way leaves behind: the audit log, and nothing else

Same instance, same two connections, restored to the state above.

### Step 1, the purge

```
$ occ mcp_connector:purge --force
{"purged":true,"connections":2,"revoked":2,"revoke_failures":0,"tables_cleared":true,"key_deleted":true}
```

Every field of that answer is a number an administrator has to read:

| Field | Meaning | What to do about it |
|-------|---------|---------------------|
| `purged` | whether the command ran at all | `false` means `--force` was missing, the data of this app could not be opened, or not one app password could be handed back (see below). The answer then carries a `hint`, nothing was deleted, and step 2 must not follow. |
| `connections` | authorizations found, revoked ones included | the number of Nextcloud app passwords this is about |
| `revoked` | app passwords handed back to Nextcloud | equal to `connections` is the good case |
| `revoke_failures` | app passwords that could not be handed back | above zero means that many app passwords can still be valid. Each affected user has to remove the entry named `MCP Connector: <client>` under Settings, Security, Devices and sessions. |
| `tables_cleared` | whether all seven tables of `oauth.sqlite3` were emptied. `audit.sqlite3` is a second file beside it, it is not one of the seven, and it stays with every row it holds (see check 5 below) | `false` still allows step 2, which takes both files with the volume, but the finding belongs in your notes |
| `key_deleted` | whether the encryption key was removed from the ExApp configuration | `false` leaves a value behind. It is useless without the volume, but it is there: remove it with the AppAPI configuration API, or accept it and record it. |

#### When the purge stops on purpose

If connections exist and not one of their app passwords could be handed back, the command
deletes nothing and says so:

```
$ occ mcp_connector:purge --force
{"purged":false,"connections":2,"revoked":0,"revoke_failures":2,"hint":"Nothing was deleted.
Not one app password could be handed back to Nextcloud, ..."}
```

What it means: this container did not reach Nextcloud, or Nextcloud refused every attempt.
A single failed revocation does not stop anything, it is counted in `revoke_failures` and
the run continues; zero successful ones out of a non-empty list is a fault of the connection
and not of one stored connection.

What was changed: nothing. The tables are untouched and the encryption key is still in the
ExApp configuration, which is the point. Those tables are the only record of which Nextcloud
app password belongs to which connection, so emptying them while the credentials stay valid
would leave the manual clean up further down as the only way out.

What to do:

1. Check that the app is running and can reach Nextcloud, for example
   `docker logs --tail=50 nc_app_mcp_connector`, and that Nextcloud answers at all.
2. Run `occ mcp_connector:purge --force` again. Nothing was consumed by the stopped run, so
   the second one is a complete purge.
3. Only then continue with step 2 of the order at the top of this page.

Four counter-checks, all measured:

```
1 $ one request per app password that worked five minutes earlier
  app password of alice -> HTTP 401, OCS 997, identity 'none'
  app password of bob   -> HTTP 401, OCS 997, identity 'none'

2 $ all seven tables
  access_tokens: 0, auth_codes: 0, authorizations: 0, clients: 0,
  flows: 0, refresh_tokens: 0, user_access: 0

3 $ the ExApp configuration of this app
  no config row of mcp_connector left

4 $ occ user:auth-tokens:list alice ; occ user:auth-tokens:list bob
  no entry with the prefix "MCP Connector:" in either list
```

A fifth check belongs to the same step, and unlike the four above it is not a
measurement from 2026-08-19: the audit log did not exist in this app on that day. It is
the check to run, in the form of check 2, with the same throwaway container and the same
copy to `/tmp`, because sqlite3 cannot open a read-only mounted database:

```
5 $ docker run --rm -v nc_app_mcp_connector_data:/d:ro alpine:3 sh -c '
      apk add --no-cache sqlite >/dev/null 2>&1
      cp /d/audit.sqlite3 /tmp/a.db
      sqlite3 /tmp/a.db "select count(*) from entries"'
  either a row count of the audit log, for example 1284
  or     cp: can't stat '/d/audit.sqlite3': No such file or directory
```

Both answers are correct here and neither of them is a fault:

* **A number other than zero** is what an instance answers that had the record switched
  on. `audit.sqlite3` is the second database of this app, the purge does not empty it,
  and a record that one command removes records nothing. Those rows stay until the
  retention window of 180 days runs out for them, until the bound of 100 MB pushes the
  oldest ones out, until the account they belong to is removed in Nextcloud, or until
  the data volume goes in step 2.
* **A missing file** is what an instance answers that never had the record on. The file
  is written the first time the record is switched on, so before that there is nothing
  to read, and [privacy.md](./privacy.md) says the same in its storage table.

### Step 2, removing the app with its data

```
$ occ app_api:app:unregister mcp_connector --rm-data
ExApp mcp_connector successfully disabled.
ExApp mcp_connector successfully removed
ExApp mcp_connector successfully unregistered.
```

`--rm-data` is not decoration. The help text of its counterpart says so itself: "Keep ExApp
data (volume) [deprecated, data is kept by default]." Without the flag the volume stays.

Counter-checks, all measured, all empty:

```
$ docker volume ls --format '{{.Name}}' | grep '^nc_app_mcp_connector_data$'   # no line
$ occ app_api:app:list | grep mcp_connector                                    # no line
$ docker ps -a --format '{{.Names}}' | grep '^nc_app_mcp_connector$'           # no line
$ occ user:setting alice | grep -c 'MCP Connector:'                            # 0
$ occ list | grep -c mcp_connector                                             # 0
```

The audit log goes with the volume, because the file lies in it. This is the one
deletion path of this app that takes `audit.sqlite3` whole: the purge leaves it
standing, `--rm-data` removes the volume it lives in, and the "Delete data on remove"
checkbox of Nextcloud 32 and 33 does the same by the same route. An instance that has to
keep the record beyond the removal copies the file out of the volume before this command
runs, because afterwards there is nothing left to copy.

One thing does stay, and it is the only one:

```
$ docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep mcp_connector
ghcr.io/street1983nk/mcp_connector:0.1.0 330MB
```

AppAPI never deletes a pulled image. It holds no instance data, so this is a disk space
question, not a privacy one. Remove it when you want the space back:

```
docker rmi ghcr.io/street1983nk/mcp_connector:0.1.0
```

## Known pitfalls

**1. Removing first and cleaning up afterwards.** `--rm-data` before the purge destroys the
mapping between a stored connection and the Nextcloud app password behind it. The
credentials stay valid, and nothing knows about them any more. Measured side effect of a run
that did it in the wrong order: two app passwords left in Nextcloud named after this app,
with no record anywhere that explains them.

**2. Cleaning up after the app is disabled.** The occ command disappears with the disable
(check 8 above). Enable the app, purge, then remove.

**3. Continuing to use the app after a purge.** The purge deletes the encryption key while
the running process still holds the copy it read at startup. Connections created after a
purge, in the same process, are encrypted with a key Nextcloud no longer stores, and they
become unreadable at the next restart. The purge is the last step before removal. If you
purged and want to keep the app, disable and enable it once, which makes it read or create
its key again.

**4. Looking for the key in the wrong table.** The encryption key is an ExApp configuration
value, so it lives in `oc_appconfig_ex`, not in `oc_appconfig`.
`occ config:app:get mcp_connector oauth_data_key` prints nothing even while the key is
there. It also survives `--rm-data`: measured, 324 bytes, still present after the volume was
gone. Only the purge deletes it.

**5. Expecting the web interface to do any of this on Nextcloud 34.** See the version table
above. There is no button, and the absence is silent.

**6. Reading `docker compose` errors as installation problems.** Every `docker compose`
command against `compose.exapp.yml` needs `HP_SHARED_KEY` in the environment, so a command
run without it fails at interpolation, not at Nextcloud. All `occ` calls on this page work
without that variable when they are run as
`docker exec -u www-data nc-mcp-exapp-nc php occ ...`.

## Security notes

**Every connection of this app is one Nextcloud app password.** That is the design, and it
is what makes the purge necessary: a credential Nextcloud issued cannot be invalidated by
deleting a file somewhere else. It is handed back over
`DELETE /ocs/v2.php/core/apppassword`, authenticated with that very password, which is why
it has to be decrypted first and why the order on this page is the order in the code.

**The purge takes revoked authorizations with it too.** The question it answers is not which
connection is alive, it is which Nextcloud app password can still be valid, and a revoked
row answers that with yes.

**Nothing in this process prints a credential.** The command answers with counts and two
booleans, and the log lines carry counts as well. The measurements on this page were made
the same way: statuses and identities, never a password.

## Related

- Installing the app and the topology used here: [exapp-install.md](./exapp-install.md)
- What the app stores and for how long: [privacy.md](./privacy.md), section
  "Deletion and user control", which points at this runbook
- The OAuth half and the one deploy variable an administrator has to set:
  [oauth-setup.md](./oauth-setup.md)
- Questions users ask about switching the app off for themselves: [faq.md](./faq.md)
