# LinkPlease — Features

## 1. Webhook Reception & Security

- Receives `comment.created` and `comment.deleted` webhooks through a FastAPI endpoint.
- Reads the exact raw HTTP request body before parsing JSON.
- Verifies `X-PseudoGram-Signature` using HMAC-SHA256 and constant-time comparison.
- Derives the production signing key from the Base64-encoded prefix of the PseudoGram API key.
- Rejects missing, malformed, unsupported, or invalid signatures.

## 2. Event Processing & Idempotency

- Persists verified webhook events in PostgreSQL.
- Supports both comment creation and comment deletion events.
- Uses `event_id` uniqueness to prevent the same event from being processed repeatedly.
- Handles duplicate webhook deliveries without creating duplicate processing work.

## 3. Keyword-Based Automation Rules

- Allows users to create keyword → DM message rules.
- Stores a normalized version of each keyword for case-insensitive matching.
- Matches incoming comment text against active rules.
- Creates a delivery job when a comment matches a rule.

## 4. Durable Delivery Queue

- Stores delivery jobs in PostgreSQL rather than relying only on in-memory state.
- Tracks delivery states including queued, sent, delivered, failed, and cancelled.
- Uses database row locking and leases when claiming jobs.
- Allows expired leases to be reclaimed after worker interruption.
- Persists retry state and scheduled retry times.

## 5. DM Delivery & Idempotency

- Sends matched DMs through the PseudoGram API.
- Uses a deterministic idempotency key based on the rule, recipient, and comment.
- Prevents duplicate delivery jobs for the same rule/user/comment combination.
- Tracks the external PseudoGram DM ID for reconciliation.

## 6. Retry & Reconciliation

- Retries temporary delivery failures using exponential backoff.
- Enforces the configured maximum delivery-attempt limit.
- Moves permanently unsuccessful deliveries to `FAILED`.
- Reconciles accepted outbound DMs against the PseudoGram DM status API.
- Updates delivery state when the provider reports delivery success or failure.

## 7. Comment Deletion Handling

- Processes `comment.deleted` events.
- Cancels eligible queued deliveries associated with deleted comments.
- Prevents a cancelled queued delivery from being sent by the worker.

## 8. Rate Limiting

- Uses a PostgreSQL-backed rate-limit bucket.
- Locks the rate-limit record while reserving capacity.
- Prevents concurrent workers from independently exceeding the configured request limit.
- Supports a configurable request count and time window.

## 9. Monitoring APIs

The backend exposes APIs for inspecting application state:

- `GET /health` — application/database health information.
- `GET /stats` — aggregate delivery statistics.
- `GET /rules` — configured automation rules.
- `POST /rules` — create a new automation rule.
- `GET /deliveries` — delivery history and current delivery states.

## 10. Web Dashboard

The React frontend provides:

- Delivery statistics.
- Rule creation and management.
- Delivery history/status information.
- Application activity/log information.
- Integration with the deployed FastAPI backend.

## 11. Persistence & Recovery

- Uses PostgreSQL for events, rules, delivery jobs, and rate-limit state.
- Delivery state survives application restarts.
- Worker leases allow abandoned jobs to become eligible for processing again.
- Delivery attempts and errors remain available for inspection through the backend APIs.

## 12. Tested Production Behavior

The final deployed implementation was tested against the live PseudoGram simulator.

The final 500-event simulator run produced:

- 500 events generated.
- 536 webhook delivery attempts, including simulator redeliveries.
- 536/536 webhook requests accepted with HTTP 200.
- Zero unexpected webhook-signature rejections.
- The simulator reported zero expected recipients because the active production rule was `TEST` while the generated simulator comments did not contain `TEST`.

The final production implementation was also verified with the backend test suite before deployment.
