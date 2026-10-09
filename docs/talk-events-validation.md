# Talk event validation

## Reproducible tests

With the locked development environment, run the contribution gates in
`CONTRIBUTING.md`. Focused behavior tests are:

```sh
uv run pytest tests/unit/test_talk_events.py tests/unit/test_talk_events_resilience.py
```

Coverage includes signature verification, callback restrictions and IP pinning,
authorization ownership, default-off behavior, real MCP SDK discovery alongside
tools, persistence, queue deduplication, own-message exclusion, expiry, revocation,
bounded retry, HTTP 410, failed renewal and acknowledgement of unsubscribe during
an in-flight delivery. The manifest test checks the separately generated opt-in
route and all required deployment variables.

Renewal tests simulate 144 half-hour renewals over three days. These are mock-clock
tests, not three days of live observation. The crash-after-acceptance test deliberately
receives the same event ID twice: it demonstrates the need for receiver deduplication.

## Historical live evidence (5–7 October 2026)

These observations concern the pre-contribution candidate based on release 0.5.0;
they do not replace CI or live validation of later changes in this PR.

- On a separate Nextcloud instance, OAuth discovery exposed the existing 23 tools
  and one event. The first wakeup needed a manual diagnostic to recover an unknown
  Talk tool; it is not counted as autonomous success.
- A subsequent Talk message received an autonomous reply in 46 seconds. A signed
  replay added no delivery. Own replies did not create new events.
- Short two-minute leases showed six automatic renewals over approximately ten
  minutes, including a connector restart. A post-restart message received an
  autonomous reply in 77 seconds. Unsubscribe and rollback were exercised.
- A one-conversation production pilot received an autonomous reply in 52 seconds,
  preserved OAuth access and verified signed-replay deduplication and stopping.
- Later close-message tests exposed host-side failures despite accepted delivery:
  one read failed with conflicting MCP metadata, and a grouped host run withheld
  the source-app reply. Neither issue is claimed fixed by this connector.
- A receiving-task prompt change let it answer already-visible close messages
  together. Two subsequent second-message delays were 30 and 23 seconds, compared
  with 163 and 147 seconds before. This is a small client-side observation, not a
  server change, an upstream default, or a response-time guarantee.

The contribution contains no customer credentials, room tokens, live databases,
deployment certificates or customer task prompts. No public release version is assigned.

## Local contribution checks (2026-10-08)

Rebased on upstream `3d38f33` (0.5.1), Windows/Python 3.13, frozen project
dependencies; pytest-xdist 3.8.0 was added only to the local test environment.

- Unit/contract suite with four workers: 5478 passed, 35 skipped, one unchanged
  DOCX speed test failed at 2.41 seconds against a two-second bound. The same
  test passed on an isolated rerun; the parallel run is not reported as all green.
- All 29 focused event, resilience and manifest tests passed.
- Ruff lint/format, Pyright 1.1.411, Vulture and the tool budget passed: 23 tools,
  15440 bytes against an 18000-byte limit.
- Transport matrix: four passed, one legacy-client skip, three failures with
  `RemoteProtocolError`. All three reproduce against unmodified upstream
  `3d38f33` in the same environment. The underlying cause is not established;
  the subsequent Linux CI run below passes all eight transport checks.
- Nextcloud 34/35 Docker integration and image builds were not run locally.

## Independent Linux CI (2026-10-09)

A private validation mirror ran the upstream workflows on GitHub-hosted Ubuntu
runners. On the original contribution base, all five CI jobs passed: unit/contract,
transport matrix, Nextcloud integration, HaRP ExApp integration, Nextcloud 35
canary checks and the combined amd64/arm64 image build (without publishing).
The unit/contract suite passed 5514 tests and the transport matrix passed eight.

After merging upstream `138c256`, including its new coverage gate and dependency
updates, the unit/contract suite passed 5518 tests with 94.15% line coverage,
above the unchanged 93% threshold. The eight transport checks passed again.
Ruff, formatting, Pyright, Vulture and the 15440-byte tool budget also passed.
These Linux results supersede the local Windows failures above; they do not
establish the cause of those environment-specific failures.

The private mirror retains CodeQL SARIF as an artifact because GitHub Code
Security is not enabled there; its Code Scanning upload is not a product test.
Public Scorecard publishing is disabled in that mirror. These mirror-only
workflow adaptations are excluded from the upstream contribution.

## Review boundaries

The feature is default-off, ExApp-only, single-process and restricted to configured
callback hosts. A general release still needs maintainer agreement on the event
extension, deployment exposure, audit/status interfaces and long-term replay policy.
CI integration against supported Nextcloud versions is independent of the historical
pilot. The unrelated Context Agent memory investigation is outside this change.
