from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connections

from apps.charges.exceptions import ChargeConflict
from apps.charges.models import Charge
from apps.charges.services import cancel_charge
from apps.payments.exceptions import PaymentConflict
from apps.payments.models import Payment, PaymentEvent
from apps.payments.serializers import PaymentNotificationSerializer
from apps.payments.services import accept_event, reconcile_event

pytestmark = pytest.mark.django_db(transaction=True)


def race(first, second):
    barrier = Barrier(2)

    def run(operation):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return operation()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, operation) for operation in (first, second)]
        return [future.result(timeout=15) for future in futures]


def test_same_event_processing_has_one_effect(scope):
    event = scope.new_event()
    results = race(
        lambda: reconcile_event(event.pk).status,
        lambda: reconcile_event(event.pk).status,
    )
    assert results == ["RECONCILED", "RECONCILED"]
    assert Payment.objects.count() == 1


@pytest.mark.parametrize("same_reference", [True, False])
def test_two_events_for_one_charge_cannot_double_pay(scope, same_reference):
    first = scope.new_event(payment_reference="parallel-reference")
    second = scope.new_event(
        payment_reference="parallel-reference"
        if same_reference
        else "different-reference"
    )
    results = race(
        lambda: reconcile_event(first.pk).status,
        lambda: reconcile_event(second.pk).status,
    )
    assert results.count("RECONCILED") == (2 if same_reference else 1)
    assert Payment.objects.count() == 1
    scope.charge.refresh_from_db()
    assert scope.charge.status == Charge.Status.PAID


def test_same_provider_payment_cannot_reconcile_two_charges(scope):
    other = scope.new_charge()
    first = scope.new_event(payment_reference="same-global-reference")
    second = scope.new_event(
        payment_reference="same-global-reference", charge_id=other.pk
    )
    results = race(
        lambda: reconcile_event(first.pk).status,
        lambda: reconcile_event(second.pk).status,
    )
    assert sorted(results) == ["DISCREPANCY", "RECONCILED"]
    assert Payment.objects.count() == 1
    assert Charge.objects.filter(status="PAID").count() == 1
    assert Charge.objects.filter(status="PENDING").count() == 1


def test_cancellation_and_reconciliation_cannot_both_succeed(scope):
    event = scope.new_event()

    def cancel():
        try:
            cancel_charge(
                clinic_id=scope.clinic.pk,
                charge_id=scope.charge.pk,
                actor=scope.owner,
                reason="Concurrent cancellation",
            )
            return "CANCELLED"
        except ChargeConflict:
            return "CONFLICT"

    results = race(cancel, lambda: reconcile_event(event.pk).status)
    scope.charge.refresh_from_db()
    if scope.charge.status == "PAID":
        assert results == ["CONFLICT", "RECONCILED"]
        assert Payment.objects.count() == 1
    else:
        assert results == ["CANCELLED", "DISCREPANCY"]
        assert not Payment.objects.exists()


@pytest.mark.parametrize("conflict", [True, False])
def test_concurrent_event_receipts_have_one_identity(scope, conflict):
    first = PaymentNotificationSerializer(data=scope.payload)
    second = PaymentNotificationSerializer(
        data={**scope.payload, **({"amount": "24.69"} if conflict else {})}
    )
    first.is_valid(raise_exception=True)
    second.is_valid(raise_exception=True)

    def accept(data):
        try:
            return accept_event(data)[1]
        except PaymentConflict:
            return "CONFLICT"

    results = race(
        lambda: accept(first.to_notification()),
        lambda: accept(second.to_notification()),
    )
    assert PaymentEvent.objects.count() == 1
    assert results.count(True) == 1
    assert ("CONFLICT" in results) == conflict
