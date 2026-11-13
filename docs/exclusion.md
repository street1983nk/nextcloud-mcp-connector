# Keeping folders away from the assistant: the kein-ki tag

**Languages:** English | [Deutsch](exclusion.de.md) | [Français](exclusion.fr.md)

A folder or file that carries the collaborative tag `kein-ki` is invisible to the assistant,
and so is everything below it. The comparison ignores case and surrounding blanks, so `Kein-KI`
counts as well, but another spelling such as `Kein KI` or `keinki` does not. The tag is the
list: there is no second list of folders in the settings and no admin switch that turns the
filter off; if no `kein-ki` tag exists, nothing is filtered
([26-CONTEXT.md, D-26-01 and D-26-02](../.planning/phases/26-guard-kern/26-CONTEXT.md)).

This page describes the two ways to run the tag, the setup with occ, the check command and
every limit that was measured or decided. Each command below ran against Nextcloud 35.0.0 on
2026-10-01 and stands with its output in the raw evidence
([raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt),
[raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt),
[raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt), repeat run with the current code).

<a id="operating-modes"></a>
## Operating modes

| | Self service (collaborative) | Organisation mode (restricted tag with group delegation) |
|---|---|---|
| Access level of the tag | `public` | `restricted` |
| Who can set and remove `kein-ki` | every user who can see the file | administrators and members of the delegated groups |
| Measured on Nextcloud 35 | a normal account sees the tag and may assign it (M1b) | a member of `ki-verantwortung` assigns it (201), a non-member gets 403 (M8) |

Renaming or deleting a tag over WebDAV is reserved to administrators in both modes (Nextcloud
source, `SystemTagNode`, [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

**Self service** suits teams where everyone decides about their own folders. Anyone who can
see a file can also remove the tag again; that follows from the Nextcloud source
(`canUserAssignTag`, [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md))
and was not measured separately.

**Organisation mode** suits an organisation where a named group decides what stays away from
the assistant. In this mode, also set `restrict_creation_to_admin`: without it every account
may create new tags, so also look-alikes such as `Kein KI` that the connector does not honour.
Measured: without the setting a normal account created a tag (201), with it the same account
got 403 (M8).

Nextcloud refuses a new tag that differs from an existing one in case only
(`Tag KEIN-KI-M6 already exists`, exit 2, M6). Other spellings are accepted: `Kein KI`,
`keinki` and `kein` plus an en dash plus `ki` were created next to `kein-ki` as tags of their
own and stored unchanged (M6). The check command below finds them.

<a id="setup-self-service"></a>
## Setup: self service

1. Create the tag as `public`:

   ```
   php occ tag:add kein-ki public --output=json
   ```

   Measured output (M7): `{"id":"200","name":"kein-ki","access":"public"}`

2. Tag a folder. Users do this in the web interface (file details, tags). An administrator can
   do it with occ; the path is `<user>/files/<folder>` without a leading slash, as measured with
   the folder `KI-frei` of the account `alice`:

   ```
   php occ tag:files:add alice/files/KI-frei kein-ki public
   ```

   Measured output (M7): `public tag named kein-ki added.`

   The access level in this command has to match the level of the existing tag; with a
   different level Nextcloud does not find the tag and the command fails (pitfall P7 in
   [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

3. Check the result with the check command (see [below](#check-command)).

<a id="setup-organisation"></a>
## Setup: organisation mode

1. Create the group that decides and add its members:

   ```
   php occ group:add ki-verantwortung
   php occ group:adduser ki-verantwortung alice
   ```

   Measured output (M8): `Created group "ki-verantwortung"` and `user alice added`

2. Create the tag as `restricted`:

   ```
   php occ tag:add kein-ki restricted --output=json
   ```

   Measured output (M8): `{"id":"201","name":"kein-ki","access":"restricted"}`. The `id` is
   the `<tag-id>` of the next step.

3. Delegate the tag to the group. Nextcloud has no occ command for tag group delegation
   (checked against Nextcloud 35). There are two ways:

   - **Web interface:** the form of the systemtags app sits under
     *Administration settings > Basic settings > Collaborative tags* (menu path from the
     translation files of Nextcloud 35, M9).
   - **WebDAV as an administrator**, the property `oc:groups` set with PROPPATCH (measured
     207, M8):

     ```
     curl -u admin:<app-password> -X PROPPATCH "https://cloud.example.com/remote.php/dav/systemtags/<tag-id>" -H "Content-Type: application/xml" --data '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:set><d:prop><oc:groups>ki-verantwortung</oc:groups></d:prop></d:set></d:propertyupdate>'
     ```

     Several groups are separated with `|` (Nextcloud source, `SystemTagPlugin`,
     [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).
     Alternatively, steps 2 and 3 in one request with POST (measured 201, M8):

     ```
     curl -u admin:<app-password> -X POST "https://cloud.example.com/remote.php/dav/systemtags/" -H "Content-Type: application/json" -d '{"name":"kein-ki","userVisible":true,"userAssignable":false,"groups":"ki-verantwortung"}'
     ```

4. Restrict tag creation to administrators:

   ```
   php occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean
   php occ config:app:get systemtags restrict_creation_to_admin
   ```

   Measured output (M8): `Config value 'restrict_creation_to_admin' for app 'systemtags' is now
   set to '1', stored as boolean in fast cache`, then `1`.

5. Check the result with the check command.

<a id="check-command"></a>
## The check command

```
php occ mcp_connector:exclusion:check --admin=<uid>
php occ mcp_connector:exclusion:check --admin=<uid> --json
```

The command runs without a user session, only reads and changes nothing: in the live proof the
tables `systemtag`, `systemtag_object_mapping`, `systemtag_group` and the `systemtags` app
configuration were equal before and after each of 20 calls
([raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt)).
Without `--admin` it reads as real accounts of the instance, so the repeat run of 2026-10-01
also compared the account tables `preferences`, `storages`, `mounts` and `filecache`: equal
before and after each of 20 calls, and equal around a run whose first reader was a freshly
created account that had never logged in
([raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt),
[raw/29-REVIEW-FIX-live.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live.txt), WR-04).
Its output names counts, tag names and delegation groups, never a file, a path or an account.

It checks seven steps in this order:

1. `admin_identity`: the account named with `--admin` is an administrator (`not_checked` with
   `admin_unconfirmed` when it could not be confirmed, for example a mistyped uid).
2. `tag_listing_readable`: the tag listing of the instance can be read.
3. `tag_exists`: a tag named exactly `kein-ki` exists (case ignored, as the connector filters).
4. `tag_visible`: that tag is visible to users.
5. `no_variants`: no other spelling (`Kein KI`, `keinki`, dashes, underscores) is in use.
6. `operating_mode`: self service or organisation mode, with the delegated groups.
7. `assignment_count`: how many items carry the tag.

**Verdict.** No `kein-ki` tag at all is a hint, not a failure: `passed` stays true and the
output says how to create it. An invisible `kein-ki` tag, or only another spelling without the
exact tag, fails (`passed` false). The exact tag next to another spelling passes with a warning
that names the items under the other spelling as not excluded.

**Exit code.** Over AppAPI the exit code of the command is always 0, whatever the verdict.
A script or monitoring reads the key `passed` of the `--json` answer, never the exit code.

**Without `--admin`.** The command then reads as the first account of the user list of the
instance (sorted), on many instances an administrator, and evaluates only visible tags. It cannot check invisible tags or delegation groups this way, and the output says so.
Run it with `--admin=<uid>` for the full check.

**Counts.** The number counts assignments across the whole instance, including files in the
trash bin; on Nextcloud 35 it even stayed after `occ trashbin:cleanup` (measured 2 before,
2 in the trash bin, 2 after, M4 in
[raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt)).
It is therefore not the number of files a user can reach.

The command answers in English; the line "See docs/exclusion.md" points to the English page.

Measured output, self service (live proof, case B):

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  passed       no other spelling of kein-ki is in use
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

Measured output, exact tag next to another spelling (live proof, case F):

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  note         no other spelling of kein-ki is in use (variant_beside_exact)
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  Items tagged 'keinki' are NOT excluded: 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

The same proof covers no tag, organisation mode, an invisible tag, only another spelling and a
non-administrator named with `--admin`; the JSON form of case B reads
`{"checked":true,"passed":true,"mode":"self_service","assigned":1,"unprotected":0,...}`.

## Limits

A green check means the tag is set up correctly. It does not mean that nothing tagged can ever
show through. These are the limits, one sentence each, with the finding they rest on.

<a id="limit-share-boundary"></a>
### Share boundary

A tag on a folder above the root of a share is invisible to the recipient, so the shared folder
appears unprotected in the recipient's sessions; a tag on the shared folder itself works, so
tag the node you share.
Source: [25-MESSBERICHT.md, K5, Freigabe-Grenze](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-invisible-tag"></a>
### An invisible tag does not work

For an account that is not an administrator an invisible tag does not exist (the tag query
answers 412 and the listing leaves it out), so it filters only in administrator sessions; the
check command reports it as failed.
Source: [25-MESSBERICHT.md, K5, unsichtbares Tag](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md);
the administrator sees it: [raw/29-01-messungen.txt, M2](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt).

<a id="limit-app-disabled"></a>
### systemtags app disabled

After `occ app:disable systemtags` the tag query keeps answering with hits on Nextcloud 32 to
35, so the connector keeps filtering; gone are the systemtags search provider, the capability
(on 32 to 34 with APCu only after a web server restart) and the occ commands `tag:files:*`.
Source: [25-MESSBERICHT.md, K1](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-timing"></a>
### Timing

A tagged item costs one tag query more than a missing one, so the response time can tell them
apart; the connector adds no artificial delay (a known limit, deliberately
accepted).
Source: [28-CONTEXT.md, D-28-12](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-06](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-search-outage"></a>
### search during an outage

When the exclusion check cannot be answered, the ChatGPT tool `search` returns fewer hits
without saying so; nothing tagged gets through.
Source: [28-CONTEXT.md, D-28-13](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-08](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-notes-create"></a>
### notes_create

`notes_create` creates a category that does not exist and refuses one that is tagged, so the
refusal shows that a tagged folder of that name exists (deliberately accepted, pinned by a test).
Source: [28-CONTEXT.md, D-28-16](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-07](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-third-party-providers"></a>
### Search providers of third-party apps

A search provider that names files without a file id, a path or a `/f/<id>` link is not
screened and passes through unified search (at runtime the connector lets it through when in doubt, a deliberate design decision); the gate in
CI only sees the providers of the CI instance.
Source: [28-REVIEW.md, WR-02 and owner decisions](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

<a id="limit-tables-free-text"></a>
### Tables free text with `/f/<id>`

Tables cells with free text that contains a `/f/<id>` address stay untouched; only link
objects are screened.
Source: [28-REVIEW.md, WR-03](../.planning/phases/28-gates-und-beweise/28-REVIEW.md),
[28-CONTEXT.md, D-28-18](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-talk-file-room"></a>
### Talk file conversations during a failing path lookup

If the path lookup fails while a folder is tagged, Talk answers differently for a file
conversation than for an invented token, so a caller can tell that a token belongs to a file
conversation, also for a tagged file.
Source: [28-REVIEW.md, IN-02](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

## Further technical limits

<a id="tech-sqlite"></a>
### SQLite with many tag assignments

Measured: on SQLite a tag query with a single hit took about 240 s at 140,005 assignments
(240,298 ms, Nextcloud 35.0.0, measured 2026-09-26; PostgreSQL: 62 ms median at 110,005).
The connector waits at most 15 s for a tag query (`TAG_BUDGET` in
[exclusion.py](../src/mcp_connector/nextcloud/exclusion.py)), so the check ends there as not answerable, and entries
carrying files are withheld (fail-closed).
Source: [25-MESSBERICHT.md, G2 and owner decision E3](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="tech-upload-oracle"></a>
### Upload next to a tagged file

An upload to a tagged destination gets the refusal of a missing parent folder; for a tagged
file below a visible parent folder that refusal still shows that something is special there,
which cannot be avoided without writing.
Source: [27-SECURITY.md, A-27-03](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-SECURITY.md).

<a id="tech-folder-oracle"></a>
### Folder next to a tagged folder

Creating a folder inside a tagged folder or below it gets the refusal of a missing parent
folder; next to a visible parent folder that refusal still shows that something is special
there, which cannot be avoided without writing.
Source: [folder-evidence.md, Folder next to a tagged folder](folder-evidence.md#folder-next-to-a-tagged-folder).

<a id="tech-tables-talk-sandbox"></a>
### Tables and Talk without a sandbox

Tables and Talk get the tag check only, not the folder sandbox `NC_MCP_FILES_ROOT` of the file
tools.
Source: [28-SECURITY.md, A-28-04](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-foreign-text"></a>
### File names in foreign text

A file name typed into a message, rich text or a Deck description lies outside a check based
on file ids and is not screened.
Source: [28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-upload-staging"></a>
### Staging folder of a chunked upload

A chunked upload that stops early leaves its staging folder `uploads/<user>/nc-mcp-<sha256>`
behind; it reveals nothing and is a cleanup item.
Source: [28-CONTEXT.md, D-28-20](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-talk-conversations"></a>
### talk-conversations hits

Hits of the search provider `talk-conversations` follow two rules: a hit whose token is not in
the conversation list is withheld as soon as anything is tagged, and if the list cannot be
read, all of them are withheld with one degraded entry under the provider's name.
Source: [28-CONTEXT.md, D-28-21](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-one-wording"></a>
### One wording when the check cannot be answered

Every tool says the same when the check cannot be answered: "The exclusion check (tag kein-ki)
could not be answered, so entries that may carry file content are withheld."
Source: [27-CONTEXT.md, D-27-05](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-CONTEXT.md).

<a id="tech-mariadb"></a>
### MySQL and MariaDB not measured

The findings on spellings and all timings hold for SQLite and PostgreSQL; MySQL and MariaDB
were not measured.
Source: [25-MESSBERICHT.md, Grenzen der Messung](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).
