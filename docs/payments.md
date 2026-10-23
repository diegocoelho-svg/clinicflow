# Simulated payments and reconciliation

This local-only provider accepts signed fictional payment notifications. The API
persists a receipt before acknowledging it. A separate database-backed worker
reconciles each receipt; accepting a webhook does not mark a charge paid.

## HTTP contract

- POST `/api/v1/payment-webhooks/simulated/` uses the provider signature below,
  independently of browser Bearer authentication.
- GET `/api/v1/clinics/{clinic_id}/payment-events/` and `/{event_pk}/` expose
  receipts, processing status and discrepancy codes.
- GET `/api/v1/clinics/{clinic_id}/payments/` and `/{payment_pk}/` expose only
  successfully reconciled payments.
- Read endpoints require an actual owner/member relationship with the clinic.
  Staff/superuser flags do not bypass that relationship. Cross-clinic IDs return
  404. These resources cannot be posted, patched or deleted through the API.

The notification is a UTF-8 JSON object with exactly these fields:

| Field | Representation |
| --- | --- |
| event_id | Provider event UUID, globally unique for this simulated provider |
| clinic_id | Positive JSON integer; the clinic must exist |
| charge_id | Positive JSON integer, stored as a reference until reconciliation |
| payment_reference | Provider payment identity, 1-128 letters/digits or `_.:-` |
| amount | Nonnegative decimal string, exactly two decimal places, at most 20 integer digits |
| currency | Three uppercase ASCII letters; a non-BRL claim becomes a discrepancy |
| paid_at | ISO 8601 timestamp, normalized to UTC |

Amounts are exact decimal strings, never JSON numbers. Unknown fields, duplicate
JSON keys, non-finite numbers and malformed bodies return 400. The maximum body
size is 64 KiB (413); other content types return 415.

### Authentication and replay

Set a separate random `SIMULATED_PAYMENT_WEBHOOK_SECRET` of at least 32 bytes.
It is never derived from Django's secret key or exposed to the frontend.
An absent/short key disables ingestion with 503.

Send:

- `X-Webhook-Timestamp`: current Unix seconds.
- `X-Webhook-Signature`: `sha256=<lowercase HMAC-SHA256 hex digest>`.

Sign the exact bytes `timestamp + "." + raw_request_body`. Verification uses
constant-time comparison and permits a five-minute clock difference in either
direction. Incorrect, missing or stale signatures return 403 before parsing JSON.

A new event returns 202 with its persisted receipt. Repeating its UUID and the
same normalized claims returns 200 with the current receipt, including after
processing. JSON whitespace/key order do not change that identity. Reusing a UUID
for different claims returns 409 without replacing the original event. Provider
retries should re-sign the same event/claims with a fresh transport timestamp.

No signature, raw body, key or payload hash is included in receipt responses.
Responses are marked non-cacheable.

## Reconciliation rules

The worker accepts a payment only when the charge exists in the stated clinic,
is PENDING, and has the same amount and currency. It creates the payment and
changes the charge to PAID in the same transaction as the event result.

A repeated provider payment identity with the same charge, amount, currency and
payment timestamp links to the existing payment. A different event UUID does not
create a second payment. Repeated worker delivery preserves processing/audit time.

| Discrepancy code | Meaning |
| --- | --- |
| CHARGE_NOT_FOUND | The charge does not exist in the event's clinic |
| CHARGE_NOT_PENDING | Charge is cancelled, already paid or requires no payment |
| CURRENCY_MISMATCH | Notification and charge currencies differ |
| AMOUNT_MISMATCH | Notification and charge amounts differ |
| PAYMENT_REFERENCE_CONFLICT | Provider identity was already reconciled for different claims |

Discrepancies retain their notification data for investigation and never mark
the charge paid. They are terminal in this delivery; correction/retry resolution
requires a later explicit audited workflow. A technical processing exception rolls
back payment, charge and event together; the receipt remains RECEIVED for retry.

Database constraints enforce one payment per charge, unique provider payment
identity, valid amounts/currencies and consistent receipt result fields.
Cross-row clinic/amount relationships are service rules, not automatic validation
of arbitrary ORM/SQL writes.

### Locking

A transaction-level PostgreSQL advisory lock serializes one provider payment
reference even across different charges. The encounter parent row is locked
before the event row and before reading the final charge state. Charge issuance,
cancellation and item changes already lock that same encounter row, so concurrent
payment and cancellation cannot both win. Hash collisions in the advisory-lock
key only serialize unrelated work; identities are still compared in full.

## Run locally

Copy the environment example and fill the existing database/Django settings.
Generate a separate random webhook key locally and store it only in ignored
`.env`. Do not send it to the browser or commit it.

```sh
docker compose --profile payments up -d --build --wait
docker compose exec api python manage.py simulate_payment CHARGE_ID
docker compose exec api python manage.py reconcile_payments --limit 100
```

The optional `payments-worker` profile runs the reconciler continuously. Without
the profile, the one-shot command is useful to inspect RECEIVED before processing.
Use a pending fictional charge. The simulator posts a signed HTTP request to this
container's loopback API and prints the receipt. It does not blindly retry after
an uncertain response; inspect the reported event UUID before sending another.

### Delivery boundary

This delivery uses persisted database receipts and a separate polling worker.
The Pub/Sub Emulator transport, publication outbox, per-event retry scheduling,
dead-letter handling, real providers, partial payments and refunds remain planned.
No cloud account or paid service is required. The existing frontend already
displays PAID after charge refresh; event investigation has read APIs, not a new
frontend screen in this delivery.

Implementation references: [Python HMAC](https://docs.python.org/3.13/library/hmac.html)
and [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).
