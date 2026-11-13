# Provenance of the fixtures in this directory

Every `.ics` file here is an object the Nextcloud Tasks app wrote. Nothing was edited: each
file is a byte for byte copy of a raw file of the measuring spike of phase 30 (plan 30-02,
browser session; plan 30-04, block `fixtures` of `scripts/tasks_spike.py`), CRLF line ends
included.

- Nextcloud: 35.0.0 (`occ status` of the running instance, raw file `raw/nc35-aendern.txt`)
- Tasks app: 0.18.1 (`occ app:list` of the running instance, raw file `raw/nc35-aendern.txt`;
  every object also names it in its `PRODID`)
- Database: SQLite
- Date of the session: 2026-11-11
- Account: `spike30ui`, a measuring account that existed only for this session; language
  German, browser time zone Europe/Berlin
- Raw files: `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-a/` (state before
  the changes of round B) and `raw/ui-b/` (state after them)

| File | Kind | State | Raw file | sha256 |
|------|------|-------|----------|--------|
| `all_day.ics` | ganztag | a | `raw/ui-a/4EA29582-E2DB-4C8D-AAB9-7D57EABD83BA.ics` | `8800a16c0426b15472659092e07bfbf4d98cb86d885df870527ba878723c187e` |
| `with_time.ics` | uhrzeit | a | `raw/ui-a/FEC4C13F-9381-4D0F-8348-F6D2643BDE32.ics` | `693350c5ead0939acea0693c598a25d6382e95d8eb0f06ffcd0c58f3a32de034` |
| `subtask.ics` | unteraufgabe | a | `raw/ui-a/7CB0DDE8-C2D1-4640-B1D0-808CA11B3E2E.ics` | `04636818f69b036c9989a9af49c3dda37b7dd5eb67e4c27153f6777b74f97f3e` |
| `subtask_parent.ics` | unteraufgabe | a | `raw/ui-a/231A6117-89EA-417C-952A-9BB4A2AE9A60.ics` | `f8130a8ddc2d2228cbd617286c8df64f37e48bb7dbda8c96ce813f69d3018b8f` |
| `recurring.ics` | wiederkehrend | a | `raw/ui-a/7B483532-932E-4791-B363-DD0F4E3C8FEF.ics` | `3781d31ae75218e775c0c8ed359460f7cccac33d8f2b96d7dc4afe410bcdd7a1` |
| `tags.ics` | tags | a | `raw/ui-a/F2771C57-9EFA-4F40-9558-DA8132B79147.ics` | `a275be382b3b7366fa62381a47c4a3ddf88d824d3e056abb1d3c641071e66311` |
| `completed.ics` | abgehakt | b | `raw/ui-b/4BFE626B-9A78-493B-9A99-78CC0FFC7D38.ics` | `407596b89ba646c35d24ddb8d50e51eb3e899e5698d95084ad22be66ab665ee5` |
| `reopened.ics` | wieder-geoeffnet | b | `raw/ui-b/2D4850EC-8E4C-4BDF-A1E5-58559950667D.ics` | `dc20515aed07b18f4c92b4a2fa8d9d5390f849d96372cc15dbd93a0b405b849d` |

`subtask.ics` and `subtask_parent.ics` belong together: `RELATED-TO` of the first is the
`UID` of the second, and both lay in the same list.

Kinds without a file here were not written by the app in that session and were not rebuilt
by hand: none.

The discovery answers next to this directory (`caldav_home_fresh_account.xml`, `caldav_home_task_lists.xml`) are unchanged answers of a throwaway Nextcloud 35.0.2 (raw file `raw/discovery-35.txt`), asked for by the accounts `fresh30` and `alice`.

## Phase 33, plan 33-01b: clearing fields and cancelled tasks

The files below are byte for byte copies of objects the Tasks app wrote in the browser
session of plan 33-01b, CRLF line ends included. The raw states were read by
`scripts/tasks_modify_measure.py snapshot` (GET under impersonation, cross-checked with a
REPORT, `SNAPSHOT gleich_appapi_basic=ja` in every state) and kept outside the repository;
the protocol lines are in `.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt`.
Step numbers refer to `.planning/phases/33-aufgaben-aendern/33-01-BROWSER-SCHRITTE.md`.

- Nextcloud: 35.0.0 (`version.php` of the running instance nc35), SQLite
- Tasks app: 0.18.1 (`TASKSAPP nc35 messung=0.18.1`; every object names it in its `PRODID`)
- Date of the session: 2026-11-13
- Account: a measuring account that existed only for this session (deleted afterwards);
  language German, browser time zone Europe/Berlin

The fields of `p3301 felder` were removed one after the other, so each `cleared_*` file is
the state after its step and still lacks the fields removed in the steps before it.

| File | Step | Prior state | Raw object | sha256 |
|------|------|-------------|------------|--------|
| `cleared_due.ics` | 10 (due date removed) | DUE, DTSTART, DESCRIPTION, PRIORITY:3, two CATEGORIES (state b2) | `ui-m2-due/952018B2-DB3C-4DF7-9F02-7D0499E50EDD.ics` | `dfb03a8c7a88918772300ab5cac329fd30c4a649014fbd150d89524ee59fdd86` |
| `cleared_start.ics` | 11 (start date removed) | `cleared_due.ics` | `ui-m2-start/952018B2-DB3C-4DF7-9F02-7D0499E50EDD.ics` | `05cbaafdc803a5818725128d2d1782ffaa3adcfb40855772558b40502439f948` |
| `cleared_description.ics` | 12 (note text deleted) | `cleared_start.ics` | `ui-m2-description/952018B2-DB3C-4DF7-9F02-7D0499E50EDD.ics` | `1654b3644228b6be90fec3ee9de3ef3a9737b86b3e0924ca77ca00f44070360f` |
| `cleared_priority.ics` | 13 (priority set to none) | `cleared_description.ics` | `ui-m2-priority/952018B2-DB3C-4DF7-9F02-7D0499E50EDD.ics` | `2cbf32caf1903daa8f63fab57e9533521107c925a03fe46e5db30aa332c994c5` |
| `cleared_tags.ics` | 14 (both tags removed) | `cleared_priority.ics` | `ui-m2-tags/952018B2-DB3C-4DF7-9F02-7D0499E50EDD.ics` | `fdd46ba80e05693d79128132948e4dc2fee234711035b3ae706b72d6db4ae0d7` |
| `cleared_parent.ics` | 15 (subtask dragged to the top level) | subtask of `p3301 felder` with `RELATED-TO` (state a) | `ui-m2-parent/C0AEF484-248A-4495-98FA-39119F39C567.ics` | `71aa62b7cf596e24f13c5fc917d0ac9de3f2935402993dab0b583b1b5e96961c` |
| `cancelled.ics` | 6 (status set to cancelled) | new task | `ui-a/B31727DD-3746-4DFD-BDEF-EDE805C734EE.ics` | `9f42a433e670861f9f3513693d591032d268086a469357a715cee57fab69096b` |
| `cancelled_completed.ics` | 17 (cancelled task checked) | `cancelled.ics` | `ui-c-direkt-ab/B31727DD-3746-4DFD-BDEF-EDE805C734EE.ics` | `08629761f6c22487414f406f07085514ab4bc28a95b0659a8f5994f0d2cf6896` |

The app removes a line for every cleared field except the description: there it writes
an empty `DESCRIPTION:` line. Every case of the plan was offered by the app, so no file is
missing.
