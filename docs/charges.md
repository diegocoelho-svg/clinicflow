# Charge issuance and cancellation

A charge records an immutable amount due for a completed encounter. Issuance is
explicit: register the encounter and its procedure items first, then issue its
charge. This delivery does not contact a payment provider or record payments.

## Business rules

- An encounter needs at least one item. A free item is valid; an empty encounter
  is not equivalent to an encounter with a zero total.
- The server totals the encounter's stored `unit_price * quantity` values using
  `Decimal`. Current catalog prices and client-supplied amounts are not used.
- Currency is always `BRL`. Totals must be finite, nonnegative, and within
  `0.00` through `99999999999999999999.99`.
- Positive totals start `PENDING`. Zero totals start `NO_PAYMENT_REQUIRED`,
  because no payment has occurred.
- There can be only one non-cancelled charge per encounter. This includes
  `NO_PAYMENT_REQUIRED` and, for future reconciliation, `PAID`.
- The issued total and each item snapshot are read-only through the API.
  Updating the procedure catalog does not change them.
- A non-cancelled charge blocks creation, updates, and deletion of encounter
  items. Clinical description and performed-time edits retain their existing
  rules; the encounter's patient remains fixed.
- Only an owner can cancel a charge. Cancellation requires a nonblank reason
  of at most 1,000 characters, stores the actor and time, and preserves the
  original amount, issuing user, UUID, and item snapshots.
- Cancellation unlocks the encounter items. Correct them and issue a new charge
  with a new key; the cancelled charge remains in the history.
- Repeating cancellation returns the already-cancelled charge and preserves its
  original cancellation reason, actor, and timestamp.
- A paid charge cannot use this cancellation flow. Refunds need a later workflow.

## Data types

All primary keys remain incremental `BIGINT` values. The operation UUID is a
separate identifier, rather than the charge's primary key.

| Charge field | PostgreSQL type | Meaning |
| --- | --- | --- |
| `id` | `BIGINT` | Incremental primary key |
| `clinic_id` | `BIGINT` FK | Derived from the encounter |
| `encounter_id` | `BIGINT` FK | Completed encounter |
| `amount` | `NUMERIC(22,2)` | Immutable issued total |
| `currency` | `VARCHAR(3)` | Always `BRL` |
| `status` | `VARCHAR(20)` | Financial state |
| `idempotency_key` | `UUID` | Issuance identifier, unique within its clinic |
| `created_by_id` | `BIGINT` FK | Issuing user |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | Creation and last state change |
| `cancelled_at` | Nullable `TIMESTAMPTZ` | Cancellation time |
| `cancelled_by_id` | Nullable `BIGINT` FK | Cancelling owner |
| `cancellation_reason` | Nullable `VARCHAR(1000)` | Required only after cancellation |

Cancellation fields are `NULL` until a cancellation occurs. An empty reason is
invalid for a cancelled charge. The patient is derived from the encounter.
Related users, clinics, encounters, and procedures use Django's `PROTECT` deletion
policy to retain referenced financial history.

Each `ChargeItem` has an incremental `BIGINT` ID, charge and procedure foreign
keys, a `VARCHAR(255)` procedure name snapshot, a positive integer quantity up to
`2147483647`, and a nonnegative `NUMERIC(12,2)` unit price. Its `total` is computed
for responses with 22 digits and two decimal places. It does not reference the
source `EncounterItem`, so cancelling and removing that source item does not
delete or block access to the historical snapshot.

The API represents foreign keys as `clinic`, `encounter`, `created_by`,
`cancelled_by`, and `procedure`, consistent with the existing endpoints. Decimal
amounts are JSON strings, timestamps use UTC, and responses include item snapshots.

## State transitions

| Operation | Starting condition | Result |
| --- | --- | --- |
| Issue | Nonempty encounter without a non-cancelled charge; total greater than zero | New `PENDING` charge |
| Issue | Same condition; total zero | New `NO_PAYMENT_REQUIRED` charge |
| Cancel | `PENDING` or `NO_PAYMENT_REQUIRED`; owner supplies a reason | `CANCELLED` |
| Cancel again | Already `CANCELLED` | Original cancellation audit is retained |
| Cancel | `PAID` | `409`; refund workflow required |

`PAID` is reserved for later payment reconciliation. These endpoints cannot
assign it, and zero totals are never labelled as paid. Discounts, installments,
due dates, payment confirmations, and refunds are outside this delivery.

## Idempotency contract

Send a UUID in `Idempotency-Key` on every issuance. A client-generated UUIDv4 is
recommended. Generate one key for the user's intended issuance and reuse it
for every retry, including after a connection timeout. Generating a new UUID for
each network attempt loses the operation identity. The key is not a credential;
normal Bearer authentication and clinic permissions still apply.

- First successful issuance: `201 Created`.
- Same clinic, key, and encounter: `200 OK` with the same charge and no extra
  snapshot. Another authorized clinic member can also retry it.
- Same clinic and key, different encounter: `409 Conflict`.
- New key, encounter already has a non-cancelled charge: `409 Conflict`.
- The same UUID can be used independently by a different clinic.
- Failed validation or a rolled-back issuance does not reserve the key.
- Keys remain attached to their charge; this delivery has no expiry or pruning.

This replays the original charge identity and returns its current representation;
it does not cache the original HTTP response bytes. For example, retrying an old
key after cancellation returns that cancelled charge, even if the encounter now
has another active charge. A new issuance after cancellation requires a new key.

The issuance body must be an empty JSON object. Extra parameters are rejected,
so the supported request identity is its clinic, encounter, and key. Future
request parameters must be included in the replay compatibility check before
being added to this contract.

## HTTP contract

All URLs begin with `/api/v1/clinics/{clinic_id}` and require `Authorization:
Bearer <token>`. Owners and members may issue and read; only owners may cancel.
Unrelated clinics and mismatched clinic/encounter or clinic/charge references
return `404` for otherwise authorized operations.

| Method | URL suffix | Body | Success |
| --- | --- | --- | --- |
| POST | `/encounters/{encounter_id}/charges/` | `{}` plus UUID header | `201` new; `200` replay |
| GET | `/charges/` | None | `200`, ordered list including cancelled charges |
| GET | `/charges/{id}/` | None | `200`, charge and snapshots |
| POST | `/charges/{id}/cancel/` | `{"reason":"Incorrect quantity"}` | `200` |

An issuance response has this shape; IDs and timestamps are illustrative:

```json
{
  "id": 1,
  "clinic": 1,
  "encounter": 1,
  "amount": "24.68",
  "currency": "BRL",
  "status": "PENDING",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
  "created_by": 1,
  "created_at": "2026-10-20T12:00:00Z",
  "updated_at": "2026-10-20T12:00:00Z",
  "cancelled_at": null,
  "cancelled_by": null,
  "cancellation_reason": null,
  "items": [
    {
      "id": 1,
      "procedure": 1,
      "procedure_name": "Original consultation",
      "quantity": 2,
      "unit_price": "12.34",
      "total": "24.68"
    }
  ]
}
```

`400` covers missing/invalid UUIDs, nonempty issuance bodies, empty encounters,
amount overflow, and missing/invalid cancellation reasons. `409` covers key
reuse for another encounter, an existing non-cancelled charge, frozen item
writes, and cancellation of a paid charge. A member's cancellation attempt
returns `403`; missing or invalid Bearer credentials return `401`.
Charge PATCH, PUT, and DELETE are unavailable. Cancellation is a state change
with history, rather than deletion.

## Transactions and concurrency

Issuance uses `transaction.atomic()` and locks the encounter with
`select_for_update()` before checking replay state, reading its items, and
creating the charge and snapshots. Item creation, quantity updates, deletion,
and cancellation acquire that same encounter row lock. Item creation then locks
the catalog procedure; this keeps the lock order consistent.

Item updates re-read the source item after acquiring the parent lock. A
serializer validated before a concurrent deletion cannot recreate the deleted
row or bypass a newly issued charge.

PostgreSQL enforces unique `(clinic_id, idempotency_key)` values and a conditional
unique encounter index for non-cancelled charges. The key constraint also covers
concurrent reuse across different encounter locks. Expected uniqueness errors are
handled outside the failed atomic block; unrelated database errors propagate,
and a snapshot failure rolls back the charge as well.

Database checks enforce valid amounts, BRL currency, status/amount consistency,
cancellation audit consistency, and snapshot quantity/name/price validity.
Cross-row total calculations, same-clinic selection, immutable snapshots, and
the shared lock protocol are service/API rules. Direct ORM or SQL writes do not
automatically execute those rules. Future reconciliation must follow the same
parent lock protocol when changing charge state.

## Validate manually with Insomnia

Start this backend checkout following the root README. Use fictional records,
the configured `API_PORT`, and the actual returned IDs.

1. Register/sign in, then create a clinic, patient, completed encounter, and an
   active procedure priced at `"12.34"`. Add it to the encounter with quantity 2.
2. POST `/api/v1/clinics/{clinic_id}/encounters/{encounter_id}/charges/` with
   Bearer auth, `Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000`, and `{}`.
   Expect `201`, amount `"24.68"`, currency `BRL`, and status `PENDING`.
3. Repeat with the same key. Expect `200` and the same charge ID. Repeat with
   another UUID while the charge is active; expect `409`.
4. GET the clinic's charge list and the charge detail. Change the catalog price
   or name; its issued snapshot and total must remain the same.
5. Attempt to add, change, or delete encounter items; expect `409`.
6. POST `/charges/{id}/cancel/` under the same clinic with
   `{"reason":"Incorrect quantity"}`. Expect `CANCELLED` and populated audit fields.
   Repeat with a different reason; the original audit fields must remain.
7. PATCH the original encounter item to quantity 3. Issue again using a new UUID,
   for example `550e8400-e29b-41d4-a716-446655440001`. Expect a new charge ID and
   amount `"37.02"`, using the encounter item's original price.
8. Retry the first UUID. Expect the original cancelled charge, original amount
   `"24.68"`, and original quantity 2. Both charges remain in the list.
9. For another encounter, use an item with unit price zero. Issuance must return
   `NO_PAYMENT_REQUIRED` and `"0.00"`. An encounter with no items returns `400`.
10. Repeat reads with an unrelated account; expect `404`. A clinic member can
    issue/read but receives `403` when attempting cancellation.

The automated PostgreSQL suite additionally exercises rollback and concurrent
requests, including observed row-lock waits in separate database connections.
