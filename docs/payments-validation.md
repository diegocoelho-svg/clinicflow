# Payment delivery validation — 2026-10-22

Branch: `diegocoelho-svg/clinicflow-payments`, based on the unmerged charges
branch from PR #10. No merge was used to build this delivery.

- Django system check and migration consistency passed.
- Ruff lint/format checks passed.
- Full PostgreSQL-backed suite: **597 passed in 38.60s**, including **76 payment
  tests** in addition to the existing 521 checks.
- Payment cases cover signed input, clock skew, malformed/duplicate JSON keys,
  exact decimal types, body limits, event replays/conflicts, clinic isolation,
  database constraints, worker limits, uncertain simulator responses and rollback.
- Parallel database tests cover repeated event receipt/processing, one payment
  identity across multiple charges, multiple payment identities for one charge,
  and cancellation racing against reconciliation.
- **30 HTTP assertions passed** through the running frontend proxy to the actual
  API, including valid/invalid/stale signatures, persisted receipt acknowledgement,
  current-state replay, conflicting replay, reconciliation, discrepancy records,
  paid-charge cancellation rejection and cross-clinic read rejection.
- The real simulator command posted a signed HTTP event and the separate worker
  command reconciled it. Replaying a provider payment under another event UUID
  reused the existing payment.

## Fictional review records

Clinic #8 contains patient #6 and procedure #6 labelled QA pagamentos 22-10.
Encounter #9 produced charge #9 for BRL 46.90 and payment #1. Encounter #10
produced charge #10 for BRL 23.45. Both charges became PAID after reconciliation.
The intentionally wrong amount remains as discrepancy event #2, even after the
second charge subsequently received a matching simulated notification.

The existing frontend shows charge statuses from the same API. The API image
was built from this worktree using the frontend Compose build-context override.
The local webhook key is stored only in the ignored frontend environment file
and forwarded only to the API; it was not committed or emitted in tool output.

This delivery uses persisted receipts and a separate local polling worker.
Pub/Sub transport, an outbox, retry scheduling/dead letters, refunds and a
frontend event-investigation screen remain outside this PR; see payments.md.
