<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Changelog

All notable changes to this app are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.12] - 2026-09-11

The record of tool calls that 0.1.11 announced is usable now: an
administrator switches it on in the admin settings and reads it with an occ command, and every
sentence this app publishes about storage, about the purge and about what is planned says what
the code does. An installed instance sees none of it before the next release, because the store
reads the manifest at upload time and an installed app keeps the code it was installed with.

### Fixed

- Nextcloud AIO with a custom domain answered every `/mcp` request with `421 Misdirected
  Request` and the body `Invalid Host header`, reported as
  [#4](https://github.com/street1983nk/nextcloud-mcp-connector/issues/4). The host allow
  list of the transport layer knew localhost and nothing else unless an operator set
  `NC_MCP_ALLOWED_HOSTS`, and an installation from the app store gets no environment
  variable to set it with. It now always carries the addresses this deployment answers to:
  the host of `NEXTCLOUD_URL`, which AIO sets to the public custom domain, and the host of
  the public address of this app when one is configured. The installation looked green
  while this happened, because the lifecycle routes sit in front of the check.
  The protection itself stays armed and every other host name is still refused with the
  same 421; nothing about this widens the check beyond the deployment's own names.

### Added

- The content hit permission fidelity test: alice uploads a document whose unique marker exists
  only in the content, alice finds it over `unified_search` through the full ExApp chain, bob
  never does, and the file name provably carries no marker. It runs in CI against a real
  Nextcloud with Findling installed from the store, and it is the measurement the synergy
  banner of the READMEs points at.
- An occ command that reads the record: `occ mcp_connector:audit:read` prints the entries of one
  account or of the instance, newest first, one line per entry, and never a parameter value.
  `--user` takes an account name, or the word `instance` for the chain that belongs to no
  account; `--since` takes whole days; `--limit` takes a count; `--json` gives the same entries as
  one machine readable document, in the order the hash chain has them. Without `--limit` the
  output stops at 200 entries and says in its first line that it did, and a count above 5000 is
  brought back to 5000. The command reaches this app the way `occ mcp_connector:audit:verify`
  does, so the manifest declares no route for it and the surface reachable from outside is the
  one 0.1.11 published.
- The three environment variables of the record are declared in the manifest:
  `NC_MCP_AUDIT_LOG`, `NC_MCP_AUDIT_RETENTION_DAYS` and `NC_MCP_AUDIT_MAX_BYTES`. They are a
  convenience for an installation set up by hand; the admin settings of this app stay the way an
  administrator switches the record on, and nothing needs an environment variable.
- A fifth check in [docs/uninstall.md](docs/uninstall.md) reads the number of rows in
  `audit.sqlite3` out of the data volume, so what stays behind after a removal is a number an
  administrator can see rather than a sentence on a page.

### Changed

- The store description is a short fact list now, owner directive of 2026-09-07: what the
  connector does, what it will never do, the audit line, and the requirements, in all three
  languages. It carries one new paragraph: together with Findling this connector forms the
  retrieval layer for your own RAG, search hits include document contents with exactly the
  rights of the asking user. The measurement behind that sentence is
  tests/integration/test_content_hit_fidelity.py.
- The note of a `unified_search` answer describes the answer instead of the installation: with a
  content provider answering it says that file contents were searched and by whom, without one it
  keeps the old sentence, and the tool description points at the note instead of claiming
  anything. Before this, an instance with Findling told every client in the same payload that
  contents are not indexed while handing over content hits.
- The wording of the audit switch in the admin settings names the three things the short version
  left out: the names of the parameters, never their values, a fixed identifier of the reason
  where a call was refused, and how long a call took. It also says what a later check of the
  record does not show, that a record which ties calls to named accounts can come under the
  codetermination of a works council in Germany and in Austria, and how long rows are kept: 180
  days by default, the record stops growing at 100 MB where the oldest rows give way, and an
  account removed in Nextcloud takes its own rows with it.
- [docs/privacy.md](docs/privacy.md), [docs/uninstall.md](docs/uninstall.md) and
  [docs/faq.md](docs/faq.md) describe two databases instead of one. `occ mcp_connector:purge`
  empties the seven tables of the OAuth database and leaves the record standing, because a record
  that one command removes records nothing. All three automatic deletions are named with their
  numbers, the retention window of 180 days by default, the ceiling of 100 MB, and the removal of
  an account in Nextcloud, and deleting the data volume of this app stays the one way that takes
  the whole record with it.
- The enterprise paragraph of the store description and of all three READMEs no longer calls the
  record of tool calls planned. It is part of this app, in the open, and planned now means two
  things: policies per group, and sign in through the identity provider an organisation already
  runs.
- An installation that already runs this app sees neither the new command nor the new wording
  until an administrator has it disable and enable once, because both registrations happen on the
  path that enables the app.

### Fixed

- The three separate cleaners for names that come from outside are one rule. A name that carries
  a formatting character, such as U+202E, can no longer turn the reading direction of a line of
  output around: a character that cannot be printed becomes a space instead of falling away, so
  two parts of a name do not melt into one word.
- A `content-length` header carrying a digit that is not an ASCII digit no longer ends in a server
  error, and neither does a run of digits no integer can hold. The check command answers such a
  call the way it answers any other.

## [0.1.11] - 2026-08-28

A release without a code change. The same twenty one tools answer the same questions they
answered in 0.1.10, and an instance that updates keeps every behaviour it had. What changed is
text in the manifest, and text is the one kind of change that only a release carries to the
people who read the store page, because the store reads the manifest at upload time and at no
other moment.

### Changed

- The paragraph about reading text written by strangers, in all three store descriptions, is
  three short sentences instead of four nested ones. It still names the same four things: that
  an assistant reads foreign text next to your data, that a Talk message is the only direct way
  out, that an administrator can switch that way off, and that newly created files, cards or
  rows send nothing to anyone but can land somewhere the account shares. The last of those four
  is one general phrase now, anywhere the account shares, where the longer version listed a
  folder, a board and a table one by one.
- The author contact in the manifest moved from k.cherif@outlook.de to admin@infranode.dev, so
  the private address leaves the public store entry. The enterprise contact inside the
  description already moved with 0.1.10; this is the `authors` field the store shows next to it.

## [0.1.10] - 2026-08-28

A release without a code change. The same twenty one tools answer the same questions they
answered in 0.1.9, and an instance that updates keeps every behaviour it had. What changed is
text, and text is the one kind of change that only a release carries to the people who read it.

### Changed

- The enterprise section of the store description and of all three READMEs is a few sentences
  now instead of a page, and the contact address in it moved from k.cherif@outlook.de to
  admin@infranode.dev. The three things that section names, an audit log over every tool call,
  policies per group, and sign in through the identity provider an organisation already runs,
  exist in this version in no form and behind no setting: the section describes a plan and not
  a feature. The short wording carries that in one word, planned, where the long one spelled it
  out in a sentence of its own. The texts travel
  with this release because the store reads the manifest only at upload time, so a corrected
  text in the repository reaches nobody until the next release; 0.1.5, 0.1.6 and 0.1.9 were
  all releases for exactly that reason.

### Fixed

- Three wordings in the translated READMEs. The main heading of README.fr.md is French now and
  no longer English. The invented word "confidemment", which is not a French word, is replaced
  at both of its places in README.fr.md by a real formulation carrying the meaning the English
  text has at the same two places. README.de.md writes the product term the way the German
  store summary writes it. These are word corrections in the reading versions; no tool, no
  answer and no setting behaves differently because of them.

## [0.1.9] - 2026-08-25

A maintenance release, and not a new family of tools. The same twenty one tools 0.1.8
published answer the same questions, and an instance that updates keeps the behaviour it
had. What changed is one key of one answer that carried two meanings, and one example in
the documentation that named a provider which never existed.

### Added

- The READMEs and the store description now name a commercial add-on that is planned and
  does not exist: an audit log over every tool call, policies per group, and sign in through
  the identity provider an organisation already runs. Not one of the three is implemented in
  this release, and each of the four texts says so in a sentence of its own; the description
  travels with this release because the store reads the manifest only at upload time, so a
  corrected text in the repository reaches nobody until the next release; 0.1.5 and 0.1.6
  were both releases for exactly that reason.

### Changed

- A change of the answer format, named here because a reader of the old key has to be
  updated: in an answer of `talk_browse` on the message level, the key `truncated` of a
  single entry is now called `message_truncated`. The same word meant two things in the
  same answer, and only one of them was about the entry: on the answer level `truncated`
  says that the window of messages was cut and that there may be a next one, on a single
  entry it says that the text of that message was cut and that there is no next one for it.
  The answer level keeps `truncated` unchanged, the conversation level keeps it as well,
  and no other tool is affected. A client that stores the tool list of a connection reads
  the new description only after its next refresh, so the first answer after the update can
  arrive before the description that explains it.

### Fixed

- The `unified_search` example in the READMEs named `spreed`, which was never a provider
  id; it now names `talk-conversations`. What the example shows was right all along, an
  unknown provider answering with a URL that nothing resolves further, and only the name in
  it was wrong.

## [0.1.8] - 2026-08-25

Mail is the newest family an assistant can reach, and it is the first one that only reads.
An assistant looks through the mail of the account and reads a single message, and there is
no way in this app to send one, so the family adds reach and deliberately no second way out.
Around it, this release is about one call and one id: the bundle that answers a question in
a single round trip now also says what is waiting in Talk and how much unread mail there is,
without a subject and without a line of mail content, and a Talk message or a table found by
a search can be read where it was found.

### Added

- `prepare_context` now also carries what is waiting in Talk: at most three conversations
  with something unread or a mention, each with a preview of the last message cut at 200
  bytes. The Talk part has its own time budget and its own `degraded` entry, so a slow Talk
  or an instance without it shortens the bundle by one sentence and never delays the answer.

- `prepare_context` now also carries the unread mail counts, for at most three accounts and
  the inbox of each, and nothing else about the mail. That restriction is the point of it:
  the standard bundle contains no subject and no line of message content, only numbers. A
  count the instance does not report stays a missing field plus one sentence, never a zero.
  Measured against a running instance: the bundle answers in under two seconds with all four
  sources present, and it costs one extra pair of requests for the mail counts.

- `fetch` resolves two more kinds of id, so a search hit can be read where it was found. The
  id `message:<token>:<messageId>` is one single Talk message, read over the same context
  route that leaves no trace, and a message that cannot be read in that conversation is a
  refusal and never a neighbouring message. The id `table:<tableId>` is the title of a table,
  the number of rows it really holds and the first of them. A view is not a table, so a view
  stays a URL, and a mail search hit stays a URL as well: resolving its deep link to the id
  the full text route needs is untested, and an id that is right most of the time is an
  answer about somebody else's mail the rest of the time.

- An assistant can walk Mail on three levels, with one tool called `mail_browse`: the mail
  accounts of the account, the mailboxes of one account with their unread count, and the
  message envelopes of one mailbox, newest first. Neither the account nor the mailbox is
  ever guessed, because a right looking answer about somebody's mail is worse than a
  question.

- The envelopes can be filtered by the state of a message, by sender, by subject, by tag and
  by a time window in Unix seconds. A filter condition this connector does not know is
  refused with the list of the ones that work, instead of being dropped in silence the way
  the Mail app itself would drop it, which would answer with the unfiltered list and look
  exactly like a correct result.

- The full text of a single message travels through the existing fetch entry point, with
  the id mail:<databaseId> that every envelope carries. The body is always converted to
  text, it is cut at 32 KiB with a marker that promises no continuation, and what Nextcloud
  itself knows about the sender travels beside the text and never inside it: whether the
  sender is trusted, the DKIM and signature verdicts, and any phishing checks that fired.

- All three families degrade in one sentence on an instance without the Mail app, the same
  way Notes, Deck, Tables and Talk have done since they were added.

### Changed

- A change of the answer format, named here because a reader of the old key has to be
  updated: in an answer of `mail_browse` on the message level, the key `truncated` of a
  single entry is now called `preview_truncated`. The same word meant two things in the same
  answer, and only one of them was about the entry: on the answer level `truncated` says that
  the page of messages was cut and that there may be a next one, on a single entry it says
  that the preview text of that message was cut. The answer level keeps `truncated`
  unchanged, and no other tool is affected.

- The descriptions an assistant reads when it connects are 157 bytes shorter for exactly the
  same information, and the limit that guards them stands on a measurement of this release
  for the first time: 15612 bytes across 21 tools, so the gate came down from 18500 to 18000
  instead of up. Every byte of that surface is context an assistant does not spend on the
  question it was asked.

- The PayPal donation button of the store page points at a paypal.me address now. It carried
  a mail address in plain text on a public page before, which is a harvesting target and not
  a payment detail anybody needs. Same recipient, same account, and the store reads the
  manifest at upload time, which is why the correction becomes visible with this release.

### Security

- Mail is read only. There is no way in this app to send a mail, to create a draft, to move,
  flag or delete a message, and no attachment is downloaded, and a contract test asserts it
  against the source of the two mail modules on every run. That matters because reading mail
  completes a combination: private data, text written by strangers, and one channel out. The
  documentation names it and names the countermeasure with it, the administration switch
  NC_MCP_TALK_SEND, which closes the outgoing Talk channel for the whole instance while
  reading stays untouched. See [docs/privacy.md](docs/privacy.md).

## [0.1.7] - 2026-08-22

Another release about being found, and again not a line of the server changed. The app was
in one category and reachable under one spelling of its own subject, which is why people
looking for the thing it is did not find it.

### Changed

- The app is now in the AI and Tools categories as well, not only in Integration. Anyone
  browsing the AI category could not see it before.
- The summary now names what the app is, an MCP server, and the assistants it connects,
  because that is what people type into the search field. Measured on 2026-08-22 against
  the store search: a search for "mcp" found this app first, a search for "mcp server"
  did not find it at all, and neither did a search for "chatgpt". All three describe this
  app, and all three are now in its text.

## [0.1.6] - 2026-08-22

A release about the app store page and nothing else. No line of the server changed, the
tool set is the same twenty tools 0.1.4 published, and an instance that updates gets the
same behaviour it had before.

### Changed

- The store description is now a short list of what an assistant can do, one line per
  family, next to what it deliberately cannot do and what an account controls itself. The
  long form lives in [docs/faq.md](docs/faq.md) and
  [docs/privacy.md](docs/privacy.md), which the description links.

### Added

- The store page now carries a homepage link and both documentation links, the client setup
  for a user and the installation guide for an administrator, so a reader does not have to
  find the repository first.

## [0.1.5] - 2026-08-22

The release that put the current store page in place, and the first of two about it. No line
of the server changed here either. The second one, 0.1.6, carried the same change again
because it was not visible on the store page one minute after the upload, and that was a
mistake and not a failed release: the store serves the app page, the catalogue and the search
index from caches that refresh minutes apart. The note that says so is in
[docs/store-submission.md](docs/store-submission.md), so it does not have to be learned a
third time.

### Changed

- The store description became what it is today: one line of what this app is, one line per
  family of what an assistant can do, then what it deliberately cannot do and who holds the
  switch. The store page carries the homepage link, both documentation links and both
  donation buttons since this release. Measured on the store page on 2026-08-22 at 11:00Z,
  the proof row is in [docs/store-submission.md](docs/store-submission.md).

## [0.1.4] - 2026-08-21

The Tables app and Talk are now part of what an assistant can reach: the tables of the
account can be looked through and a row can be added to one of them, and conversations can
be read and one message can be sent into one of them. Talk is the first family in which an
assistant can put something in front of other people, so it is also the first one an
administrator can close for the whole instance with a single switch, and reading a
conversation deliberately leaves no trace in the account.

### Added

- An assistant can look through Tables on three levels: the tables the account may see,
  the columns of one table with their types and limits, and the rows themselves. A row read
  never returns a whole table. It answers with 25 rows unless a larger window is asked for,
  at most 200, and it says how many rows the table really holds, that the answer was cut
  and where the next page starts.

- A row can be added by naming the column titles, not the internal column numbers nobody
  sees in the app. A title the table does not have, a title that exists twice, a missing
  mandatory column and a table the account may read but not write to are all refused before
  anything is written, each with the next step to take. Existing rows are never changed and
  never removed, here as everywhere else in this app.

- An assistant can read the conversations of the account and the history of one of them, and
  that reading leaves no trace in the account: no read marker is moved, no notification is
  acknowledged and the online status stays as it was. The history answers the newest messages
  first, says when it was cut, and offers the way further into the past.

- An assistant can send one message into a conversation. It is addressed only by a token the
  read tool reported, so a made up address never reaches Nextcloud, and a conversation the
  account may not write in is refused before anything is sent. A sent message is never edited
  and never removed, and a message that mentions everybody, a whole group or a whole team at
  once is not sent at all: each of those turns one tool call into a notification for every
  participant or every member. A mention of a single account, of a guest or of a federated
  user is sent as written.

- An administrator can switch the sending of Talk messages off for the whole instance, in the
  settings of this app, whatever an account is allowed to do in Talk itself. Reading
  conversations and their history is not affected by that switch.

### Fixed

- Asking for something that does not exist now says so. When Nextcloud answers such a
  request with a bare error page instead of a message, the assistant used to be told that
  its app password might be wrong, which sent it looking in the wrong place. It is now told
  that the id is unknown to this instance, so it can search for the right one.

## [0.1.3] - 2026-08-21

This release adds a second way for an assistant to identify itself: by a metadata
document it publishes, instead of registering with this app first. That is the way the
current specification prefers, it is the way Claude Code connects, and an administrator
can switch it off. Next to it, a locally running assistant may now come back on the
port it actually got, which is the other half of what kept Claude Code out, and the
page a refused desktop app lands on now names the way that works for it.

### Fixed

- The version this app names in the MCP handshake is now the version that is installed.
  It was a fixed string that stayed at the first release, so a connected assistant was
  told 0.1.0 whatever version answered. The handshake now derives it from the package
  version, the single string every release raises.

- The switch for the way an app identifies itself by its own published document can now be
  set in the administration settings of this app, next to the switch for self registration.
  It was only ever a deploy variable, and an installation from the app store never receives
  one, so on exactly that kind of installation the switch could not be reached at all. Both
  switch descriptions now say what they do to each other: with self registration off, both
  ways are closed whatever the second switch says, while switching the second one off leaves
  self registration exactly as it is.

### Changed

- The page a user sees when an assistant app asks to be returned to an address it did not
  register now names the way in that works for such apps: an app password from the Nextcloud
  security settings. Nothing is shared in that case, as before, and the page still says
  nothing about which check refused the request or which address was asked for. This closes
  what was left open for apps of that shape: the sign in stays refused, and the reader is no
  longer left with a refusal and no way forward. The documentation for Cursor and the OAuth
  setup carries the same way out and the reason behind it.

- The documentation now says what a real Claude Code does with this server, because it was
  measured against Claude Code 2.1.233: it connects without registering, by publishing its
  own metadata document, and it calls tools with the account that signed in. The port it
  comes back on was measured too, over four runs, and it was a different one every time,
  which is why this app no longer compares that port. What is not new: an administrator who
  switches client registration off closes this way with it, and an administrator who keeps a
  list of allowed clients keeps it for this way as well. Both were measured on a running
  instance, and with registration off the app makes no outbound request at all.

- The documentation now says what a real Cursor does with this server, because it was
  measured against Cursor 3.2.16: the registration goes through since 0.1.2, and the sign
  in is still refused, because Cursor asks to be returned to its `cursor://` address, which
  this app does not register. Nothing is shared in that case and no password page is shown.
  Cursor users are pointed at the app password path, and the earlier reading that a client
  of this shape is no longer kept out is corrected to what it really is: the attempt now
  fails at the sign in instead of at the registration.

- The documentation now says what Nextcloud 34.0.3 really does with an external app,
  because it was measured there: the apps management lists it with its deploy daemon, its
  install button reads "Deploy and enable", and "Remove" appears in the row actions once
  the app is disabled. On 34.0.2 and earlier the apps management lists no external app at
  all, and the occ commands stay the path that works on every version. No promise of a one
  click install without the version it was measured on.
- A locally running assistant may now come back on the port it actually got. A native
  client publishes a return address without a port and takes whatever free port the
  operating system hands it at the moment of the request, and the app used to refuse
  that as a mismatch. Scheme, host, path and query are still compared exactly and only
  loopback addresses are affected, so `localhost` still does not stand in for
  `127.0.0.1` and a hosted connector gains no freedom at all. This is what kept Claude
  Code out.

### Added

- An assistant can now connect by publishing its own metadata document instead of
  registering with this app first. The address of that document is the name the client
  goes by, the app reads it once and keeps the answer for as long as the answer asks for
  and at least five minutes. It reads the document again when that window is over, and it
  does so while a connection is being made and at no other moment: a running connection,
  a token exchange and every single tool call use the information as it was read, so an
  app you connected keeps working while the site that publishes its document is
  unreachable, and nothing your assistant does can make this app wait on that site. The
  other side of that trade, said plainly: a document that was withdrawn or changed does
  not reach a connection that already exists. Ending access is a disconnect on the
  connections page of this app, or an administrator who removes the app, and both take
  effect on the very next request. Everything that holds for a registration holds here
  too: only `https` return addresses and loopback ones, an inadmissible address is dropped
  and the rest kept, the client list of an administrator decides in exactly the same
  place, and a client of this kind never holds a shared secret. The app reads such a document from public addresses only, never
  from an address inside a network, never more than five kilobytes of it, never longer than
  five seconds, never after a redirect and never an image out of it, and a failed read is
  not remembered. This is the way the current specification prefers, and it is the way
  Claude Code identifies itself.
- The approval page now names the host of the address a client goes by, and it carries a
  second warning when the app can only be reached on the computer you are using. The
  reason for the warning is worth reading once: an address of that kind says who publishes
  the information about an app, and it does not say which program on your own computer
  answers on that port. So the page says both of those things, and it does not claim that
  anybody confirmed the app.
- A new administrator switch, `NC_MCP_OAUTH_CIMD`, for the way a client identifies
  itself by the address of its own published metadata document instead of registering.
  It is on unless it is switched off, and switching off client registration switches
  this off with it: a closed door cannot be walked around through the other spelling.
- A runbook for showing this app to other people, `docs/conference-demo.md`: the one time
  setup, four stations with every command to copy and what has to be visible at each of
  them, a checklist for the ten minutes before, the things it deliberately does not show,
  and a recovery table. It was walked once end to end and it carries the measured time of
  every step, including the two answers a paused and a disconnected account really get.
  Next to it, `docs/conference-talk.md`, a five minute talk draft whose every claim names
  the measurement it comes from.

## [0.1.2] - 2026-08-20

A maintenance release with no new feature. It opens the app to clients that register a
return address of their own scheme, which is what kept Cursor out, and it tightens four
places where the app trusted what a request said about itself instead of what it sent.

### Changed

- A client that registers several return addresses at once is no longer refused
  because one of them is inadmissible. The inadmissible entries are dropped and the
  registration keeps the allowed ones, and the answer names the addresses that were
  actually registered. This is what kept Cursor out: it registers a `cursor://` scheme
  next to two acceptable addresses. The rule itself is unchanged, `https` on any host
  and `http` on loopback only, a dropped address is never a redirect target, and a
  registration whose every address is inadmissible is still refused.
- An excerpt of a document now reads only what it keeps. The bundling tool keeps two
  kilobytes per hit and used to fetch up to 512 kilobytes to do it, so one call with
  three excerpts could move one and a half megabytes through the instance. The answer
  is the same one as before, the transfer behind it is a fraction of it.
- A pause that has nothing behind it is cleaned up after 90 days. The switch a user
  sets for their own account was stored forever, also for accounts that no longer
  exist, and on setups that reuse account names a new account could inherit the pause
  of an old one and start switched off without anybody having done that. A pause with
  a connection behind it is untouched, whatever its age.
- The app's database does less work per request. The table setup ran on every single
  open of the file, including the account switch check that sits on every request of a
  connected assistant, and it now runs when a process opens the file for the first
  time. A store file that is removed while the app runs is still recreated.
- The public address is stored in one spelling. An address typed with capital letters
  in the administration settings became the name this app publishes about itself, and a
  client that was given the same address in lower case failed a comparison nothing
  explained. The scheme and the host name are levelled now, which changes nothing about
  the address itself; a path is left exactly as it was typed, because there capital
  letters do mean something.
- The administration form of a fresh installation links to the documentation instead of
  to a page that cannot exist. Before an address is set, the app does not know where it
  can be reached, and the link of the form pointed at the administrator's own machine.
- The log line an administrator gets when no usable public address is set now says
  which of the two cases it is: none is stored, or one is stored and was refused. The
  line that reports a refused address names both places it can be corrected, the deploy
  variable and the form, and which of the two wins. Neither line ever contains the
  address itself.

### Fixed

- A paused account no longer sees a consent screen it cannot use. If the access switch
  was pulled in another tab while a consent screen stood open, a reload still showed
  approve and deny. Nothing could be granted, the click was already refused, but the
  page said the opposite of the switch. It now shows the same note as everywhere else.

### Security

- The uninstall command reads only as much of a request as it is willing to read. Its
  size limit trusted the length a request announced, and a request that announces none
  was read into memory whole. The path is an internal one and needs the app's own
  credentials, so nothing was reachable from outside; the limit now counts what actually
  arrives, and the command behaves exactly as before.
- The connections page has the same limit on the same terms. Its size check also read the
  length a request announced, so a submission that announced none was read whole and
  carried out, although the page says it refuses a body larger than its four short fields
  unread. The check now counts what arrives, both places share one implementation, and an
  ordinary submission is answered exactly as before.
- The hidden value that protects the consent screen and the connections page against
  forged form submissions now expires. It used to be the same value for an account for
  the whole lifetime of the installation, and the only way to change it would have been
  to replace the data key, which makes every stored connection unreadable. It is bound
  to a one hour window now, and the previous window is accepted as well, so a page that
  was open across a full hour still submits. A page older than that is refused the way a
  forged one is: it shows itself again, and the action has to be repeated.
- A document can no longer imitate the note this app writes into a text. When a file is
  too large to be read at once, or when a document is shortened to a short excerpt, the
  answer says so in the text itself, so an assistant that reads only the text can tell a
  whole document from the beginning of one. A document that contained that exact
  sentence could pretend the excerpt of the server ended there and that what followed
  was a message of the system, or claim to be complete where it was cut. The sentence is
  now removed from the content of a document before the app writes its own, so it can
  only come from the app. What an assistant receives is otherwise unchanged.

## [0.1.1] - 2026-08-19

A maintenance release that makes the listed version installable with one click, and
removable without a leftover. Everything the store listed as 0.1.0 needed an
environment variable an administrator had no place to set.

### Added

- Administrator settings in Nextcloud for the public address of this app and for the
  three OAuth switches (client self registration, allowlist only, allowed clients).
  Administration settings, Security, MCP Connector, no environment variable and no
  shell.
- A new administrator command `occ mcp_connector:purge --force` ends every MCP
  connection of the instance: it hands every Nextcloud app password this app created
  back to Nextcloud, empties its database and deletes its data key. Run it before
  removing the app, see [docs/uninstall.md](docs/uninstall.md).
- Setup guides for Open WebUI and MUCGPT, in
  [docs/client-setup.md](docs/client-setup.md).
- Frequently asked questions, including how a user switches the app off for their own
  account and how an administrator removes it together with its data, in
  [docs/faq.md](docs/faq.md).

### Changed

- An installation whose public address is not set yet now starts and reports its setup
  state instead of stopping with an error. Before this release, a one click install
  from the store ended in a container that restarted forever, because that address can
  only be set after the install.
- The per account switch now also prevents new connections from being created. Before,
  it stopped requests of existing connections but a paused account could still connect
  another assistant.
- The store description now answers, in all three languages, the one question users
  ask: whether they can switch the app off for themselves without their administrator.
- The tool count in the readme is now correct: 16 tools, not 15, and a contract test
  reads it from the live tool registry instead of trusting the text.

### Fixed

- The `--force` option of the purge command is now accepted by the command wrapper, so
  the command can actually be run.
- Deleting the data key now passes its key name in the shape AppAPI expects, so a purge
  leaves no key behind.

## [0.1.0] - 2026-08-17

First release, submitted to the Nextcloud App Store.

### Added

- MCP server for Nextcloud, deployed as an AppAPI External App behind HaRP.
- A curated, read first set of tools for files, calendar, notes, deck and
  contacts, plus `prepare_context`, which bundles a search and the coming week
  into a single call.
- OAuth 2.1 sign in, so a hosted assistant such as Claude.ai or ChatGPT connects
  through a Nextcloud browser sign in instead of a pasted app password. Dynamic
  client registration, PKCE, and an administrator allowlist for clients.
- App password sign in for clients that cannot do OAuth.
- A per account switch and a connections page: every user pauses or resumes their
  own access and disconnects any connected assistant, on the app's own
  `/connections` page.
- Every request runs under the identity of the signed in user, so an assistant
  never sees more than that user sees in the web interface.
- A privacy and data flow description, see [docs/privacy.md](docs/privacy.md).

[0.1.12]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/street1983nk/nextcloud-mcp-connector/releases/tag/v0.1.0
