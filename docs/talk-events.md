# Experimental Talk events (opt-in)

This extension lets an OAuth MCP client subscribe to new messages in one Talk
conversation. Talk sends a signed webhook; the connector queues a minimal event
for the subscribed client. Reading a message or replying remains a separate,
permission-checked MCP tool call. No new tools or dependencies are added.

The default deployment is unchanged. Enabling this feature introduces background
delivery and a persistent queue: the default no-background-processing description
does not apply to an opted-in instance. This is an experimental, single-process
feature, not a promise of real-time or exactly-once replies.

## Requirements and setup

- ExApp deployment, one server process, persistent connector storage.
- Existing OAuth authorization backed by the user's Nextcloud app password.
  Delegated impersonation connections are not supported by this extension.
- A client supporting the [MCP Events extension](https://developers.openai.com/plugins/build/mcp-events).
- Administrator-enabled conversations and a dedicated Talk bot webhook secret.

Start on a disposable instance. Build the candidate using the repository's normal
ExApp build process. Generate the opt-in registration manifest with
`python scripts/events_manifest.py > events-info.xml`; use that manifest with
the existing AppAPI registration workflow. The released manifest is deliberately
unchanged, so installing the normal release does not publish the new route.
AppAPI must declare the environment variables or its deployment daemon can drop them.

| Variable | Meaning |
| --- | --- |
| `NC_MCP_TALK_EVENTS_ENABLED` | `true` enables events; otherwise disabled |
| `NC_MCP_TALK_EVENTS_ROOMS` | 1–10 comma-separated exact conversation tokens |
| `NC_MCP_TALK_EVENTS_SECRET` | Dedicated random shared bot secret, at least 32 characters |
| `NC_MCP_TALK_EVENTS_MAX_TTL_MS` | Maximum lease, 60000–3600000 ms; default one hour |

Register a Talk bot with the connector's externally routed `/events/talk` endpoint
and the same secret, then attach it only to the enabled conversations. Use the
[Talk bot documentation](https://nextcloud-talk.readthedocs.io/en/latest/bots/)
for the commands supported by the installed Talk version. Keep secrets outside
source control and logs. The route is public at AppAPI but authenticates the Talk
signature and exact configured backend origin; it is not an anonymous event injector.
When disabled, the route, queue, worker and additional HTTP clients are not created.

Authorize the MCP client as an ordinary conversation participant and subscribe to
`nextcloud.talk.message.created` with `arguments.conversation` set to that token.
The client supplies its HTTPS callback and signing secret and must answer a signed
verification challenge. `events/subscribe` also renews an existing subscription;
`events/unsubscribe` removes it. Discovery advertises the event while preserving
the existing tools. Clients must honor `refreshBefore`; indefinite leases are not granted.

## Permissions, delivery and storage

- Subscription and each delivery recheck the OAuth authorization, account access
  switch, client policy and conversation membership/exclusion rules as that user.
- Uncertain permission checks send nothing and consume the bounded retry budget.
  Explicit invalid/revoked OAuth access removes the subscription.
- Only local-user comment messages qualify. Own messages, guests, bot actors and
  system events are excluded. Another AI using a local-user account is still a user:
  multi-agent loop prevention is the receiving application's responsibility.
- Outgoing data contains only the conversation token and message ID, not message text.
- Callback hosts are restricted to `chatgpt.com`, `api.openai.com` and
  `connectors.api.openai.com`, HTTPS/default port only. Public IP resolution is pinned
  while preserving TLS server-name validation. Redirects, environment proxies and
  cross-name connection reuse are disabled. Other client callback hosts are unsupported.
- Callback URLs/secrets are encrypted with the existing installation data key.
  The queue stores authorization references, user/room/message IDs and delivery state;
  it does not duplicate the Nextcloud app password or message content.
- One serial worker, at most five attempts per delivery; HTTP 410 removes the subscription.
  Transient HTTP failures retry with bounded backoff. Failed deliveries are not replayed
  automatically by an operator interface. An HTTP 2xx means accepted, not that a reply ran.
- Up to ten subscriptions per authorization, 10000 queued/deduplication rows globally,
  and 24-hour row retention while the subscription exists. A full queue returns 503.
- Event IDs remain stable across retries and database reopen. A crash after receiver
  acceptance but before the local commit can redeliver: receivers must deduplicate.
- Unsubscribe waits for an in-flight send and fences later sends after acknowledgement;
  it cannot recall accepted events. Removing a subscription deletes its queue/history.

## Operational limits and rollback

There is no historical catch-up during a webhook outage or expired subscription,
no multi-process queue claiming, and no guarantee of exactly-once effects. Talk HMAC
authenticates the request but does not establish freshness; retained event IDs only
bound replay protection to the queue's retention/subscription lifetime. Durable inbound
replay policy, a delivery-status interface and audit-log integration remain follow-ups.

Stop the client subscription, verify that no delivery remains, detach the bot from
the pilot room, and disable the event switch before reverting the candidate image.
Preserve existing OAuth storage and its data key; do not overwrite newer authorizations
with a stale backup. Turning off this extension does not require reauthorizing tools.

Start with one conversation. Abort the pilot on out-of-scope delivery, duplicate
effects, lost tool access, failed renewal or unexpected resource pressure. Client-side
batching, queueing and reasoning can delay replies independently of connector acceptance.
No response-time service level is claimed.

See [validation evidence and remaining gaps](talk-events-validation.md).
