# Evidence for files_create_folder against real Nextcloud

**Date:** 2026-11-12
**Subject:** `files_create_folder` measured against real Nextcloud under AppAPI impersonation
**Status:** measured on Nextcloud 35.0.0, the run on Nextcloud 32 follows; one finding fixed during the
run, one finding open, two statuses not reproducible

Unit tests say what the code does with an answer. They cannot say which answer a real
Nextcloud gives. This page records what was run against two running instances, the lower and
the upper end of the supported version window, so the claims about the tool can be checked
rather than believed. Every quoted line is copied from a raw protocol:

- Nextcloud 35: [raw/nc35-ordner.txt](../.planning/phases/31-ordner-anlegen/raw/nc35-ordner.txt),
  earlier runs of the same day in
  [raw/nc35-ordner-vorlaeufe.txt](../.planning/phases/31-ordner-anlegen/raw/nc35-ordner-vorlaeufe.txt)
- Nextcloud 32: [raw/nc32-ordner.txt](../.planning/phases/31-ordner-anlegen/raw/nc32-ordner.txt)
- the test that wrote the lines:
  [tests/integration/test_files_create_folder_live.py](../tests/integration/test_files_create_folder_live.py)

## Instances

| | Nextcloud 35 | Nextcloud 32 |
|---|---|---|
| `occ status` | versionstring 35.0.0, version 35.0.0.10 | not run yet |
| Topology | `compose.nc35.yml`: `nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector` | not run yet |
| AppAPI | 35.0.0 | not run yet |
| Registered app | `mcp_connector` 0.3.2, enabled | not run yet |
| Measured accounts | alice, and bob for the read-only share | not run yet |

Only one instance ran at a time. The instance was stopped afterwards and keeps its volumes.

## Method

- **Impersonation only.** Every measured call builds its credentials with the mode `appapi`:
  the app secret plus a user id inside the AppAPI header. No app password is a credential of
  a measured call.
- **The code under test is this repository.** The test calls the tool function of the working
  tree in its own process and sends the requests straight to Nextcloud. The app registered in
  the instance supplies the secret and the identity AppAPI accepts, not the code.
- **Two controls come first.** Control 1 asserts that the measuring process holds no app
  password and no static bearer of the connector. Control 2 repeats a call with 64 zeros as
  the secret: every answer is a 401 and the file system holds nothing. Without them a green
  row could have been carried by something other than the secret.
- **Counter checks use another pattern than the tool.** Each "nothing was created" and each
  "was created" is read in the file system of the Nextcloud container (`docker exec <nc>
  test -d` below `/var/www/html/data/<user>/files`). Ids and permissions are read with a
  PROPFIND that authenticates with the app password of the account, not by impersonation.
- **The calls are logged, not assumed.** A response hook on the measured client notes method
  and status of every answer; the `status=` field of a line is that list. A request outside
  the files endpoint carries its area in front, for example `systemtags.PROPFIND:207` for
  the tag lookup of the exclusion guard.
- **One prefix per run, removed afterwards.** Everything a run creates lies below
  `/ordner31-<stamp>` of the measured account and is deleted by the harness with the app
  password, never through the connector, which cannot delete. The `BASELINE` lines compare
  the files, the trash bin, the quota, the tag assignments and the shares of the account
  before and after.

A line reads `ORDNER <case> nc=<version> nutzer=<account> status=<calls> ergebnis=<ok|befund>
| <raw values>`. `befund` means the tool did not keep its promise in that case.

## Nextcloud 35

| Case | What was asked | Answer of Nextcloud | Answer of the tool |
|------|----------------|---------------------|--------------------|
| frei | a path that is free | MKCOL 201 | `created` true, the id equals the `oc:fileid` of an independent PROPFIND, taken from the `oc-fileid` answer without a further read |
| vorhanden | the same path again | MKCOL 405, PROPFIND 207 | `created` false, the same id |
| datei | a path where a file lies; a chain below that file | MKCOL 405, PROPFIND 207; below the file PROPFIND 404 | conflict "A file, not a folder", the file is unchanged, no MKCOL below it |
| eltern-fehlt | a folder below a missing parent, without `parents` | MKCOL 409 | exactly the sentence of a missing parent folder, nothing created |
| kette | four missing folders with `parents` | four MKCOL 201 | `created_folders` lists all four, top down |
| deckel | eleven missing folders with `parents` | twelve PROPFIND, no MKCOL | refused with the counted number 11 and the cap 10, nothing created |
| teilabbruch-wettlauf | a chain while another writer puts a file in its way | MKCOL 201, MKCOL 405, PROPFIND 207 | conflict that ends with what this call created and left in place |
| teilabbruch-name | a chain with `.htaccess` as a link | PROPFIND 500 while counting | the sentence of a refused folder name, nothing created (see the first finding) |
| namen | six names, one call each | 400, 405, 400, 201, 201, 201 | a named refusal or a real folder, never an unnamed status |
| geteilt-nur-lesen | a folder inside a share received without the create right, without and with `parents` | MKCOL 403 twice | "No permission to create a folder", reason `permission_denied`, nothing created at the owner |
| kein-ki | a folder inside a folder tagged `kein-ki`, without and with `parents` | no request to the files endpoint | the sentence of a missing parent folder, equal to the answer for an invented parent |
| sandbox | the root, a folder below it, and a root that does not exist | no request; MKCOL 201; PROPFIND 404 twice | the root is refused, `/a` lands below the root, a missing root is never created |
| sperre-423 | a folder inside a locked folder, three ways to lock | LOCK 200 each time, MKCOL 201 | folder created; 423 not reproducible |
| mkcol-404 | a chain whose parent is deleted after the count | MKCOL 409 | the sentence of a missing parent folder; 404 not reproducible |
| kontingent-knapp | a folder with 4096, 1024 and 1 free bytes of quota | MKCOL 201, 507, 507 | created, then "Not enough space in Nextcloud" twice |

The two controls:

```text
KONTROLLE 1 nc=35.0.0.10 nutzer=alice ergebnis=ok | mode=appapi NC_MCP_APP_PASSWORD or NC_MCP_STATIC_BEARER set in the process=no; the credential is APP_SECRET and no app password
KONTROLLE 2 nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:401,MKCOL:401 ergebnis=ok | tool: ToolError reason=guard_tripped message='The exclusion check (tag kein-ki) could not be answered, so entries that may carry file content are withheld.'; dav.make_folder: ToolError reason=unspecified message='Nextcloud rejected the app password.'; file system has /ordner31-e25b1473/kontrolle-falsch=no
```

Control 2 shows two sentences on purpose. The first request of the tool is the tag lookup of
the exclusion guard, so with a rejected secret the tool stops there and says that the
exclusion check could not be answered: nothing is written while the check is open. The bare
folder request of the client answers with the sentence for rejected credentials.

The fifteen cases:

```text
ORDNER frei nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,MKCOL:201 ergebnis=ok | {"created": true, "id": "file:23590", "path": "/ordner31-e25b1473/frei"}; oc:fileid by app password PROPFIND=23590; one MKCOL 201; id from oc-fileid, no read; file system test -d /ordner31-e25b1473/frei
ORDNER vorhanden nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,MKCOL:405,PROPFIND:207 ergebnis=ok | {"created": false, "id": "file:23590", "path": "/ordner31-e25b1473/frei"}; oc:fileid by app password PROPFIND=23590; MKCOL 405; PROPFIND 207
ORDNER datei nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,MKCOL:405,PROPFIND:207,systemtags.PROPFIND:207,PROPFIND:404,PROPFIND:404,PROPFIND:207 ergebnis=ok | ConflictError reason=unspecified message='A file, not a folder, already exists at /ordner31-e25b1473/datei.txt.'; sentence of a file at the path; chain below the file: ConflictError reason=unspecified message='A file, not a folder, already exists at /ordner31-e25b1473/datei.txt.'; A5 PROPFIND below the file: PROPFIND /datei.txt/x/y:404, PROPFIND /datei.txt/x:404, PROPFIND /datei.txt:207; no MKCOL below the file; file unchanged (GET with app password); file system test -f /ordner31-e25b1473/datei.txt
ORDNER eltern-fehlt nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,MKCOL:409 ergebnis=ok | ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/fehlt of /ordner31-e25b1473/fehlt/kind does not exist.'; one MKCOL 409; file system without /ordner31-e25b1473/fehlt
ORDNER kette nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:207,MKCOL:201,MKCOL:201,MKCOL:201,MKCOL:201 ergebnis=ok | {"created": true, "created_folders": ["/ordner31-e25b1473/k", "/ordner31-e25b1473/k/a", "/ordner31-e25b1473/k/a/b", "/ordner31-e25b1473/k/a/b/c"], "id": "file:23595", "path": "/ordner31-e25b1473/k/a/b/c"}; created_folders top down; oc:fileid by app password PROPFIND=23595; four MKCOL 201; file system: all four folders
ORDNER deckel nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='Creating /ordner31-e25b1473/d/1/2/3/4/5/6/7/8/9/10 needs 11 new folders; one call creates at most 10.'; names the cap of 10; no MKCOL; twelve PROPFIND of the count; file system without /ordner31-e25b1473/d
ORDNER teilabbruch-wettlauf nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,PROPFIND:404,PROPFIND:404,PROPFIND:404,PROPFIND:207,MKCOL:201,MKCOL:405,PROPFIND:207 ergebnis=ok | ConflictError reason=unspecified message='A file, not a folder, already exists at /ordner31-e25b1473/w/x. Already created in this call and left in place: /ordner31-e25b1473/w.'; the addition names what was created; file system test -d /ordner31-e25b1473/w; file system test -f /ordner31-e25b1473/w/x; file system without /ordner31-e25b1473/w/x/y
ORDNER geteilt-nur-lesen nc=35.0.0.10 nutzer=bob status=systemtags.PROPFIND:207,MKCOL:403,systemtags.PROPFIND:207,PROPFIND:404,PROPFIND:404,PROPFIND:207,MKCOL:403,systemtags.PROPFIND:207,MKCOL:201 ergebnis=ok | ToolError reason=permission_denied message='No permission to create a folder at /mcp-share-a6cd5d25e3/neu-e25b1473.'; reason permission_denied; without the addition Already created; ToolError reason=permission_denied message='No permission to create a folder at /mcp-share-a6cd5d25e3/k-e25b1473.'; reason permission_denied; without the addition Already created; two MKCOL 403; oc:permissions of /mcp-share-a6cd5d25e3 by app password PROPFIND: bob=SGDN alice=RGDNVCK; positive control in the own home: {"created": true, "id": "file:23598", "path": "/eigen-e25b1473"}; file system of alice without neu-e25b1473 and k-e25b1473
ORDNER kein-ki nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207,MKCOL:409,systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | tagged: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/gesperrt of /ordner31-e25b1473/gesperrt/neu does not exist.'; invented: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/erfunden of /ordner31-e25b1473/erfunden/neu does not exist.'; equal once the folder is renamed; tagged chain: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/gesperrt/a of /ordner31-e25b1473/gesperrt/a/b does not exist.'; tagged calls without MKCOL and PROPFIND on files (systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207); file system without gesperrt/neu, gesperrt/a and erfunden; positive control offen/neu: {"created": true, "id": "file:23601", "path": "/ordner31-e25b1473/offen/neu"}
ORDNER sandbox nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201,systemtags.PROPFIND:207,REPORT:207,PROPFIND:404,PROPFIND:404 ergebnis=ok | ToolError reason=unspecified message='The folder path is the root folder, which always exists.'; root refusal without a single request; /a is on the file system at /ordner31-e25b1473/root/a: {"created": true, "id": "file:23603", "path": "/ordner31-e25b1473/root/a"}; missing root: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/root-fehlt of /ordner31-e25b1473/root-fehlt/a does not exist.'; no MKCOL with a missing root; file system without /ordner31-e25b1473/root-fehlt; file system without /a above the root
ORDNER teilabbruch-name nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,PROPFIND:404,PROPFIND:500 ergebnis=ok | ToolError reason=unspecified message='Nextcloud does not accept the folder name in /ordner31-e25b1473/n/ok/.htaccess/x.'; the sentence of a refused folder name, for the target; file system holds nothing of the chain, and the sentence says so; no .htaccess on disk
ORDNER namen nc=35.0.0.10 nutzer=alice status=MKCOL:400,MKCOL:405,MKCOL:400,MKCOL:201,MKCOL:201,MKCOL:201 ergebnis=ok | '.htaccess': named refusal or real folder; 'x.part': named refusal or real folder; 'x.filepart': named refusal or real folder; 'con': named refusal or real folder; 'ende-leer ': named refusal or real folder; 'ende-punkt.': named refusal or real folder; file system ls -1A /ordner31-e25b1473/namen: ['con', 'ende-leer', 'ende-punkt.']
ORDNER sperre-423 nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201,systemtags.PROPFIND:207,REPORT:207,MKCOL:201,systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | bob-via-share: LOCK 200, MKCOL [201]; alice-own-token: LOCK 200, MKCOL [201]; alice-x-user-lock: LOCK 200, MKCOL [201]; 423 not reproducible on this instance
ORDNER mkcol-404 nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,PROPFIND:404,PROPFIND:207,MKCOL:409 ergebnis=ok | ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/geloescht-e25b1473 of /ordner31-e25b1473/geloescht-e25b1473/kind does not exist.'; MKCOL after the parent was deleted: [409]; file system without /ordner31-e25b1473/geloescht-e25b1473; 404 not reproducible on this instance
ORDNER kontingent-knapp nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201,systemtags.PROPFIND:207,REPORT:207,MKCOL:507,systemtags.PROPFIND:207,REPORT:207,MKCOL:507 ergebnis=ok | used 65184233 B, quota before: The setting does not exist for user "alice".; quota used plus 4096 B: {"created": true, "id": "file:23618", "path": "/ordner31-e25b1473/q-e25b1473/knapp"}; on disk; quota used plus 1024 B: MKCOL [507] ToolError reason=unspecified message='Not enough space in Nextcloud to create /ordner31-e25b1473/q-e25b1473/eng.'; nothing on disk; quota 1 B: MKCOL [507] ToolError reason=unspecified message='Not enough space in Nextcloud to create /ordner31-e25b1473/q-e25b1473/voll.'; nothing on disk; quota back to: The setting does not exist for user "alice".
```

The names, one line each:

```text
NAME '.htaccess' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:400 ergebnis=ok | ToolError reason=unspecified message='Nextcloud does not accept the folder name in /ordner31-e25b1473/namen/.htaccess.'; file system has it=no
NAME 'x.part' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:405,PROPFIND:207 ergebnis=ok | ConflictError reason=unspecified message='A file, not a folder, already exists at /ordner31-e25b1473/namen/x.part.'; file system has it=no
NAME 'x.filepart' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:400 ergebnis=ok | ToolError reason=unspecified message='Nextcloud does not accept the folder name in /ordner31-e25b1473/namen/x.filepart.'; file system has it=no
NAME 'con' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | {"created": true, "id": "file:23605", "path": "/ordner31-e25b1473/namen/con"}; file system test -d of the answered path
NAME 'ende-leer ' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | {"created": true, "id": "file:23606", "path": "/ordner31-e25b1473/namen/ende-leer"}; file system test -d of the answered path
NAME 'ende-punkt.' nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | {"created": true, "id": "file:23607", "path": "/ordner31-e25b1473/namen/ende-punkt."}; file system test -d of the answered path
```

The account after the run:

```text
BASELINE dateien_alice vorher=158 nachher=158 gleich=ja
BASELINE papierkorb_alice vorher=1 nachher=1 gleich=ja
BASELINE kontingent_alice vorher=The setting does not exist for user "alice". nachher=The setting does not exist for user "alice". gleich=ja
BASELINE tag_zuordnungen vorher=tags=keine zuordnungen=0 nachher=tags=keine zuordnungen=0 gleich=ja
BASELINE freigaben_alice vorher=3 nachher=3 gleich=ja
```

The read-only share is measured as bob. On this instance alice owns the shared folder and bob
received it without the create right, so bob is the account the case is about; alice is the
owner whose file system is checked.

The canary and the live pair ran on this instance with `NC_MCP_REQUIRE_LIVE=1`, which turns a
missing prerequisite into a failure instead of a skip. Both passed. In each of the four modes
(normal state and three forced outages of the tag lookup) the canary called
`files_create_folder` twice inside the tagged folder, without and with `parents`, and both
calls were refused; the live pair compared the answer for a tagged target with the answer for
an invented one and found them equal in every mode. Their lines stand in section (3) of the
raw protocol.

## Nextcloud 32

Filled by the run on the Nextcloud 32 route.

## Folder next to a tagged folder

A folder tagged `kein-ki` is invisible to the connector, and `files_create_folder` keeps it
that way: a target inside a tagged folder is refused before any request reaches the files
endpoint, with the sentence Nextcloud gives for a parent folder that does not exist. The
answer for the tagged folder and the answer for an invented folder are equal once the folder
name is replaced:

```text
ORDNER kein-ki nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207,MKCOL:409,systemtags.PROPFIND:207,REPORT:207,MKCOL:201 ergebnis=ok | tagged: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/gesperrt of /ordner31-e25b1473/gesperrt/neu does not exist.'; invented: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/erfunden of /ordner31-e25b1473/erfunden/neu does not exist.'; equal once the folder is renamed; tagged chain: ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/gesperrt/a of /ordner31-e25b1473/gesperrt/a/b does not exist.'; tagged calls without MKCOL and PROPFIND on files (systemtags.PROPFIND:207,REPORT:207,systemtags.PROPFIND:207,REPORT:207); file system without gesperrt/neu, gesperrt/a and erfunden; positive control offen/neu: {"created": true, "id": "file:23601", "path": "/ordner31-e25b1473/offen/neu"}
```

There is one limit, and it cannot be removed without writing. Seen next to a parent folder
that the assistant can list, "the parent folder does not exist" is a sentence that does not
fit what the listing shows. It does not confirm a folder, it does not name one and it does
not say why, but it does tell that something is special at that place. Every possible refusal
differs from the answer a free name gets, so some difference always remains; one wording for
every refused write is the most uniform choice. The same holds for a folder next to a tagged
folder: creating it works, and creating inside the tagged neighbour answers as above.

## Group folder with ACL

The group folder with an ACL rule was not built again for this run (decision D-31-07). The
evidence is the measurement of the preceding phase on Nextcloud 35.0.0 with `groupfolders`
23.0.1, under impersonation and with an app password:

- [spike-tasks.md, section 2.2](spike-tasks.md#22-messung): a rule that takes write, create
  and delete from one account makes the MKCOL answer 403 and nothing is created; an account
  without the rule creates in the same folder, and so does the measured account once the rule
  is removed.
- [spike-tasks.md, section 2.4](spike-tasks.md#24-a8-je-speicherart-und-was-phase-31-übernimmt):
  the same 403 with an empty message for an ACL rule, a read-only group, a read-only external
  storage and a share without the create right. The server does not say which of them it was,
  so the tool has one general sentence for all four.
- [spike-tasks.md, section 12.2](spike-tasks.md#122-rawnc35-gruppenordnertxt): the raw answers.

What this run adds is the tool on top of that status: the share without the create right
above answers 403, and the tool turns it into "No permission to create a folder" with the
reason `permission_denied`.

## What the run found

1. **A blocked name inside a chain was reported as a server error (fixed).** With `parents`
   the tool counts the missing folders with one PROPFIND each. Nextcloud 35.0.0 answers that
   read for `.htaccess` with a 500 that carries `OCP\Files\ForbiddenException` and
   `Invalid path`, not with the 400 the MKCOL gives. The first run therefore ended in "server
   error (500)" and the advice to retry later. The folder client now reads exactly that body
   as a refused name; every other 500 stays a server error. Unit tests first, then the run
   above. Nothing was created in either state.
2. **Nextcloud asks for 4096 free bytes before it creates a folder.** With the quota set to
   the used bytes plus 1024, MKCOL answers 507; with plus 4096 it answers 201
   (`QuotaPlugin.php` of the dav app: a fixed size of 4096 bytes, because MKCOL carries no
   length). A quota that is tight but not exhausted can therefore already refuse a folder,
   and the tool says "Not enough space in Nextcloud".
3. **`x.part` is answered as if a file were there.** MKCOL answers 405, and the read that
   follows answers 207 with a node that is not a folder and has the file id -1, while the
   file system holds nothing of that name. The tool says "A file, not a folder, already
   exists". Nothing is created and the advice to choose another name is right, but the
   sentence names a file that does not exist.
4. **Open: a folder name ending in a space, as a link of a chain.** Every path is trimmed at
   both ends before a request is built. Inside a chain the tool builds the path of each link,
   so a link named `mitte-leer ` is created as `mitte-leer`, and the next link below the name
   with the space answers 409. The sentence then names a folder as created under a name the
   file system does not hold. Recorded, not asserted and not changed in this plan: whether to
   refuse such a name or to support it is a decision for the owner.

```text
ZUSATZ name-mit-leerzeichen-in-kette nc=35.0.0.10 nutzer=alice status=systemtags.PROPFIND:207,REPORT:207,PROPFIND:404,PROPFIND:404,PROPFIND:207,MKCOL:201,MKCOL:409 befund=ja | ToolError reason=unknown_id message='The parent folder /ordner31-e25b1473/zusatz/mitte-leer  of /ordner31-e25b1473/zusatz/mitte-leer /kind does not exist. Already created in this call and left in place: /ordner31-e25b1473/zusatz/mitte-leer .'; named as created: ['/ordner31-e25b1473/zusatz/mitte-leer ']; file system ls -1A /ordner31-e25b1473/zusatz: ['mitte-leer']
```

5. **Assumption A5 holds.** A PROPFIND below a file answers 404, see the case datei.
6. **A folder deleted on its own stands in the trash bin under its base name.** The cleanup of
   the canary relies on that, and it had never run against an instance. Measured with the
   harness of the canary: line `PAPIERKORB` in section (4) of the raw protocol.

## Not reproducible or not measured

- **423 (lock).** Three ways to lock a folder were tried: a WebDAV LOCK by a second account
  through a share with all rights, a WebDAV LOCK by the account itself, and the lock of the
  `files_lock` app. Each LOCK answered 200, and each MKCOL below the locked folder answered
  201. The 423 branch of the tool is covered by unit tests only.

```text
SPERRE versuch=bob-via-share nc=35.0.0.10 LOCK status=200 token=yes UNLOCK status=204 tool status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 | LOCK answer: <?xml version="1.0"?> <d:prop xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"> <d:lockdiscovery> <d:activelock> <d:lockscope> <d...; tool: {"created": true, "id": "file:23613", "path": "/ordner31-e25b1473/lock-e25b1473-a/kind"}
SPERRE versuch=alice-own-token nc=35.0.0.10 LOCK status=200 token=yes UNLOCK status=204 tool status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 | LOCK answer: <?xml version="1.0"?> <d:prop xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"> <d:lockdiscovery> <d:activelock> <d:lockscope> <d...; tool: {"created": true, "id": "file:23614", "path": "/ordner31-e25b1473/lock-e25b1473-b/kind"}
SPERRE versuch=alice-x-user-lock nc=35.0.0.10 LOCK status=200 token=no UNLOCK status=200 tool status=systemtags.PROPFIND:207,REPORT:207,MKCOL:201 | LOCK answer: <?xml version="1.0"?> <d:prop xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"> <d:getetag>6af5fefbefdd8</d:getetag> <nc:lock>1</...; tool: {"created": true, "id": "file:23615", "path": "/ordner31-e25b1473/lock-e25b1473-c/kind"}
UNGEMESSEN sperre-423 grund=no LOCK on this instance made the MKCOL answer 423 (three attempts, raw output in the SPERRE lines); the 423 branch is covered by unit tests only
```

- **404 on MKCOL.** With the parent deleted between the count and the write, MKCOL answers
  409. The MKCOL handler of sabre hands the path to `createCollection` and has no line of its
  own that answers 404. The 404 branch is covered by unit tests only.

```text
QUELLE mkcol-404 nc=35.0.0.10 CorePlugin.php httpMkcol exit=0 lines with NotFound, Conflict or createCollection: 560: $result = $this->server->createCollection($path, $mkcol);
UNGEMESSEN mkcol-404 grund=the MKCOL below a parent that was just deleted answers [409], not 404; httpMkcol in CorePlugin.php: 560: $result = $this->server->createCollection($path, $mkcol);; the 404 branch is covered by unit tests only
```

- **Network failures inside a chain.** A timeout or a dropped connection while a folder
  request is on the wire is covered by unit tests only; it was not forced against an
  instance.
- **Group folders, external storage.** Not rebuilt, see the section above.
- **Versions between 32 and 35.** Not measured.
