<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Lightning talk draft: MCP for Nextcloud, without the password paste

**Format:** lightning talk, five minutes. Eight slides, each with at most three bullets and a
written out speaker note. The speaker notes add up to 280 seconds, which leaves twenty for
the room.

**Status of the submission, without decoration.** The call for speakers of the Nextcloud
Community Conference 2026 closed on 2026-08-03. Accepted speakers hand in their slide draft
by 2026-09-09. The conference itself is 2026-09-19 and 2026-09-20 at CIC Berlin,
Lohmuehlenstrasse 65, and the Contributor Week from 2026-09-21 to 2026-09-25 is a different
format with a different tone.

So this file is a draft and reusable material: for conversations at the venue, for a later
submission window, and for the Prototype Fund application. **Whether and where anything is
submitted is the owner's decision.** Nothing was submitted with this draft, no form was
filled in, no mail was written and nobody was contacted.

**Every product claim below is measured, and the measurement is named on the slide.** Where
a claim depends on a version, the version is on the slide too. That is the whole style of
this talk: facts with a source, and no superlative without a number.

**The write promise since 0.8.0.** The slides were written for 0.1.2. Since 0.8.0 the promise
has one narrow exception: with the switch `NC_MCP_TASKS_UPDATE` on (it ships off),
`tasks_complete`, `tasks_update` and `tasks_move` change one existing task, only with the
ETag from `tasks_read`, and `tasks_move` is the one tool that moves anything. Nothing
deletes, a task included. Whoever gives this talk for 0.8.0 or later says so on slide 6.

## Slide 1, title

- MCP for Nextcloud: one click, real OAuth, per user control
- An ExApp, AGPL-3.0, in the Nextcloud App Store since 2026-08-19
- Version 0.1.2, one developer

**Speaker note (20 s).** Good morning. I am here for five minutes about a small app with one
job: it connects an AI assistant to your Nextcloud, so the assistant can read your files, your
calendar, your notes, and nothing else. It is in the app store, it is AGPL, and there is
exactly one person behind it, which is why I care so much about the maintenance cost of every
single feature.

## Slide 2, the problem

- The usual way in is an app password pasted into a config file
- That password is the whole account, forever, for whoever holds the file
- The person whose data it is has no page, no switch and no list

**Speaker note (35 s).** Here is how connecting an assistant to a Nextcloud usually works
today. You create an app password, you paste it into a configuration file of some assistant,
and you are done. Think about what you just handed over. That credential is your entire
account. It does not expire, it has no scope, and it lives in a file on a machine that syncs
somewhere. And the person whose data it is has no page that lists what is connected, no way to
pause it and no way to end one connection without ending all of them. Three problems, and they
are the three things this app does differently. Plus one thing it deliberately cannot do.

## Slide 3, one, it installs like an app

- Nextcloud App Store, `Deploy and enable`, no compose file, no reverse proxy rule
- Measured on Nextcloud 34.0.3.2, and only from 34.0.3 on
- On 34.0.2 the store interface showed no ExApp at all, an upstream bug

**Speaker note (40 s).** First, it installs like an app. You find it in the app store, you
press `Deploy and enable`, AppAPI pulls the image and it runs. No compose file to write, no
reverse proxy rule to add. And I want to be precise about that sentence, because it only
became true three weeks ago: on Nextcloud 34.0.2 the app store interface showed no external
app at all, which was a frontend bug in the server, fixed upstream in 34.0.3. I measured it on
34.0.3.2 on 2026-08-20, in the running interface and not in the changelog, and the measurement
is in the repository. If you are on anything older, `occ` is the reliable path, and it always
was.

## Slide 4, two, real OAuth, to the MCP specification

- Its own authorization server: PKCE S256, audience bound tokens, refresh rotation, revocation
- Two ways for a client to identify itself: dynamic registration, or its own metadata document
- Nextcloud does the sign in. This app never sees a password

**Speaker note (45 s).** Second, authorization is the specification, not a workaround. The app
is its own OAuth 2.1 authorization server, to the MCP authorization spec: dynamic client
registration, proof key for code exchange, tokens bound to one audience, refresh rotation with
reuse detection. Claude.ai and ChatGPT walk it end to end. Claude Code does not even register:
its client identity is the URL of its own metadata document, and I measured that live on
2026-08-20 against version 0.1.2. Two numbers from that run, because they are the interesting
part. With dynamic registration switched off, the instance sent exactly zero packets to
anthropic, counted against a positive control that saw four. And the loopback port that client
came back on was a different one in every single one of three consecutive runs, which is why
this server compares everything about a return address except its port. That is a MUST in
RFC 8252, and it is the difference between a spec compliant server and one that works for the
client you happened to test.

## Slide 5, three, the switch belongs to the account

- One page per account: what is connected, pause everything, disconnect one app
- Pause is a refusal with a reason, not a disconnection. Nothing is revoked
- Measured 2026-08-20: paused answers 403, resumed answers 200, no token reissued

**Speaker note (45 s).** Third, and this is the one I have not seen anywhere else. Every
account gets a page, linked from Nextcloud under Settings, Security. It lists which assistants
can reach that account, it has one switch that pauses all of them, and it has one button per
row that ends exactly that connection. Not the administrator's page. The account's own page.
I walked it yesterday with a real client connected: press pause, and the next call is refused
with a 403 that says why. Press it back on, and the same token works again, because nothing
was revoked and nothing was reissued. Press disconnect, and the assistant gets a 401 and its
attempt to refresh gets a 400, because the refresh token went with the connection. Every one
of those numbers is in a measurement file in the repository.

## Slide 6, four, it cannot destroy anything

- Sixteen tools in the released 0.1.2, twenty in the development tree. No delete, no share,
  and no move except one task behind a switch that ships off (0.8.0)
- Upload creates, and refuses a path that exists
- The assistant sees exactly what the signed in account sees, checked against a read-only share

**Speaker note (40 s).** Fourth, and this one is about what is missing. A store install of
0.1.2 lists sixteen tools, and the development tree has twenty; take the number from
whichever version you install. There is no delete and there is no share. In 0.1.2 there is
no move either; from 0.8.0 on an administrator can allow moving a single task, and that
switch ships off.
Upload creates a file and
refuses a path that already exists. This is not a setting you can turn off, it is the tool set,
and a test in the repository fails if that ever stops being true. The other half of the same
promise is permission parity: the assistant reaches Nextcloud as the account that signed in,
so it sees what that account sees. I test that with a folder shared read only between two
accounts, and the interesting assertion is not that the second account is refused the private
file. It is that the second account can read the shared file and still cannot write into that
folder, although my upload tool is create only. Nextcloud draws that line, not me.

## Slide 7, the demo

- Four stations: connect, read, pause and resume, disconnect
- Runbook in the repository: `docs/conference-demo.md`
- Walked once end to end, with the time of every step written down

**Speaker note (30 s).** I am not going to run the demo in a lightning talk, because five
minutes and a conference network are two reasons not to. It is in the repository instead, as a
runbook: four stations, every command to copy, what has to be visible at each step, what it
takes, and a recovery table for the step that fails. I walked the whole thing once and wrote
down what it actually took, including the four places where my own runbook was wrong. Come and
find me afterwards and I will run it on my laptop.

## Slide 8, take it

- `github.com/street1983nk/nextcloud-mcp-connector`, AGPL-3.0
- In the store as `mcp_connector`, min Nextcloud 32, max 35
- Issues, review and a maintainer with an opinion are all welcome

**Speaker note (25 s).** That is it. It is AGPL, it is in the store, it works on 32 to 35. If
you run a Nextcloud for other people, the page in slide five is the part I would like you to
look at, because I built it from a guess about what users want and I would rather have your
opinion than my guess. And if anybody from the server or AppAPI side wants to tell me that I
did the ExApp part wrong, that is the most useful five minutes I can have today. Thank you.

## Timing

| Slide | Seconds |
|-------|---------|
| 1, title | 20 |
| 2, the problem | 35 |
| 3, one click | 40 |
| 4, real OAuth | 45 |
| 5, the account's switch | 45 |
| 6, cannot destroy | 40 |
| 7, the demo | 30 |
| 8, take it | 25 |
| **Total** | **280** |

## Where each claim on a slide comes from

| Slide | Claim | Source |
|-------|-------|--------|
| 1 | In the store since 2026-08-19, currently 0.1.2 | `docs/store-submission.md`, proof table |
| 3 | The store interface lists this ExApp and the install button reads `Deploy and enable`, on 34.0.3.2 | `06-07-MEASUREMENTS.md`. The button was read on a neighbouring ExApp that was not installed, because this one is installed and therefore shows `Disable` |
| 3 | On 34.0.2 the store interface showed no ExApp | `docs/exapp-install.md`, with the upstream issue and the pull request that fixed it |
| 4 | Claude.ai and ChatGPT walk the flow end to end | `docs/oauth-setup.md` |
| 4 | Claude Code identifies itself by its metadata document and calls a tool with content | `06-09-MEASUREMENTS.md` |
| 4 | Zero packets with registration switched off, against four in a positive control | `06-09-MEASUREMENTS.md`, counted in the container |
| 4 | Three runs, three different loopback ports | `06-09-MEASUREMENTS.md`: 45157, 47608, 41977, plus 34567 with the override |
| 5 | Paused answers 403 with a reason, resumed answers 200, no token reissued | `06-10-MEASUREMENTS.md`, sections 5.1 and 5.2 |
| 5 | Disconnect answers 401, and the refresh attempt answers 400 | `06-10-MEASUREMENTS.md`, section 6 |
| 6 | Sixteen tools in 0.1.2 and twenty in the development tree, no delete, no share, no move except `tasks_move` behind `NC_MCP_TASKS_UPDATE` (0.8.0, off by default) | `scripts/check_tool_budget.py`, the tool table contract test and `tests/contract/test_write_promise_truth.py` |
| 6 | Upload refuses a path that exists, and the read-only share boundary | `tests/integration/test_permission_parity_share.py` and the phase 5 measurements |
| 7 | The runbook was walked once, with times | `docs/conference-demo.md` and `06-10-MEASUREMENTS.md` |

## What this draft does not say, on purpose

- **Nothing about Nextcloud AIO.** No installation path of AIO has been measured here.
- **Nothing that claims the connector recognises a named program.** A client metadata
  document proves control over a URL. The consent page shows the host of that URL for exactly
  that reason.
- **Nothing about Cursor working over OAuth.** It registers and is then refused at the
  authorization step, because it insists on a private use return address. Measured in
  `06-08-MEASUREMENTS.md`. It works over the stdio transport with an app password, and that is
  the honest answer if the question comes up.
- **No claim about a store release beyond 0.1.2.** A release needs the owner's approval.

## Prepared submission text, not submitted

**Draft only. The owner sends, or does not.** Nothing below was entered into a form, sent as a
mail or handed to anybody. It is here so that a future submission window costs an afternoon
and not a rewrite.

```
Title: MCP for Nextcloud: one click, real OAuth, and a switch that belongs to the user

Format: Lightning talk (5 minutes)

Abstract:
Connecting an AI assistant to a Nextcloud usually means pasting an app password into a
configuration file. That credential is the whole account, it never expires, and the person
whose data it is gets no page, no switch and no list. This talk shows a small AGPL ExApp that
does it the other way around: installable from the app store, its own OAuth 2.1 authorization
server to the MCP authorization specification, and one page per account that lists every
connected assistant, pauses all of them and ends any single one. It also shows what the tool
set deliberately cannot do: there is no delete and no share, nothing moves except a single
task when an administrator allows it, and the assistant sees
exactly what the signed in account sees. Every number in the talk comes from a measurement
in the repository, including the two places where the measurement contradicted what I
expected.

Audience: administrators and developers who run Nextcloud for other people.

Speaker: street1983nk, author and sole maintainer of the mcp_connector ExApp.
```
