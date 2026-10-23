# Review fixes and validation

The pre-merge review found two payment defects: a trailing newline could bypass
provider-reference validation (and overflow the database column), and response
read/JSON failures in the simulator did not retain the recovery message.

Provider references now have a strict end anchor and an explicit 128-character
limit. Currency input also requires exactly three ASCII uppercase letters.
The simulator catches expected transport, truncated-body and JSON errors, reports
the original event UUID and sends no automatic retry.

Notifications cross the serializer/service boundary as an immutable typed
`PaymentNotification`. Canonical identity is defined in that type and is also
used by the simulator. Business exceptions live in `payments/exceptions.py`
and are mapped to HTTP through the shared handler. Read APIs use the same clinic
membership base as the other resources. Provider and encounter lock helpers state
the order explicitly; reconciliation retains its transaction and event-row lock.

Discrepancy codes use `PaymentEvent.Discrepancy`. Migration 0002 adds their
choices without rewriting the already-applied initial migration or event data.

Validation: **615 PostgreSQL-backed tests passed**, including 87 payment cases,
528 base/backend cases, concurrency/rollback, exact 128-character acceptance,
newline/overflow rejection, equivalent timestamp offsets and three uncertain
response-read paths. Django checks and migration consistency passed. Ruff checks
and formatting include the generated migration.

Pub/Sub, outbox, scheduled retry, refunds and an event-investigation UI remain
outside this delivery. No merge or auto-merge was performed.
