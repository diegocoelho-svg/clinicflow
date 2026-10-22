from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.charges.exceptions import ChargeConflict
from apps.charges.models import Charge
from apps.charges.services import cancel_charge
from apps.payments.models import Payment, PaymentEvent
from apps.payments.services import reconcile_event

pytestmark = pytest.mark.django_db


def test_matching_payment_atomically_marks_charge_paid(scope):
    event = scope.new_event()
    result = reconcile_event(event.pk)
    payment = Payment.objects.get()
    scope.charge.refresh_from_db()
    assert result.status == PaymentEvent.Status.RECONCILED
    assert result.payment_id == payment.pk
    assert payment.amount == Decimal("24.68")
    assert payment.charge_id == scope.charge.pk
    assert payment.source_event_id == event.pk
    assert scope.charge.status == Charge.Status.PAID
    first_time = result.processed_at
    assert reconcile_event(event.pk).processed_at == first_time
    assert Payment.objects.count() == 1
    with pytest.raises(ChargeConflict):
        cancel_charge(
            clinic_id=scope.clinic.pk,
            charge_id=scope.charge.pk,
            actor=scope.owner,
            reason="A paid charge needs a refund.",
        )


def test_new_event_for_same_payment_reuses_record(scope):
    first = scope.new_event(payment_reference="same-provider-payment")
    second = scope.new_event(payment_reference="same-provider-payment")
    reconcile_event(first.pk)
    replay = reconcile_event(second.pk)
    assert replay.status == PaymentEvent.Status.RECONCILED
    assert replay.payment_id == Payment.objects.get().pk
    assert Payment.objects.get().source_event_id == first.pk


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"amount": "24.69"}, "AMOUNT_MISMATCH"),
        ({"amount": "0.00"}, "AMOUNT_MISMATCH"),
        ({"currency": "USD"}, "CURRENCY_MISMATCH"),
        ({"charge_id": 9223372036854775807}, "CHARGE_NOT_FOUND"),
    ],
)
def test_mismatches_remain_available_for_investigation(scope, changes, reason):
    event = scope.new_event(**changes)
    result = reconcile_event(event.pk)
    assert result.status == PaymentEvent.Status.DISCREPANCY
    assert result.discrepancy_code == reason
    assert not Payment.objects.exists()
    scope.charge.refresh_from_db()
    assert scope.charge.status == Charge.Status.PENDING


def test_cross_clinic_charge_reference_does_not_reconcile(scope):
    event = scope.new_event(clinic_id=scope.other.pk)
    assert reconcile_event(event.pk).discrepancy_code == "CHARGE_NOT_FOUND"
    assert not Payment.objects.exists()


def test_cancellation_after_receipt_wins_safely(scope):
    event = scope.new_event()
    cancel_charge(
        clinic_id=scope.clinic.pk,
        charge_id=scope.charge.pk,
        actor=scope.owner,
        reason="Cancelled before provider processing.",
    )
    assert reconcile_event(event.pk).discrepancy_code == "CHARGE_NOT_PENDING"
    assert not Payment.objects.exists()
    scope.charge.refresh_from_db()
    assert scope.charge.status == Charge.Status.CANCELLED


def test_free_charge_is_never_converted_to_paid(scope):
    Charge.objects.filter(pk=scope.charge.pk).update(
        amount=0, status="NO_PAYMENT_REQUIRED"
    )
    event = scope.new_event(amount="0.00")
    assert reconcile_event(event.pk).discrepancy_code == "CHARGE_NOT_PENDING"
    assert not Payment.objects.exists()


def test_second_payment_for_paid_charge_is_a_discrepancy(scope):
    reconcile_event(scope.new_event().pk)
    event = scope.new_event()
    assert reconcile_event(event.pk).discrepancy_code == "CHARGE_NOT_PENDING"
    assert Payment.objects.count() == 1


def test_provider_reference_cannot_pay_a_second_charge(scope):
    reconcile_event(scope.new_event(payment_reference="provider-reused").pk)
    other_charge = scope.new_charge()
    event = scope.new_event(
        payment_reference="provider-reused", charge_id=other_charge.pk
    )
    assert reconcile_event(event.pk).discrepancy_code == "PAYMENT_REFERENCE_CONFLICT"
    other_charge.refresh_from_db()
    assert other_charge.status == Charge.Status.PENDING


def test_failure_rolls_back_payment_charge_and_event_then_can_retry(scope, monkeypatch):
    event = scope.new_event()
    original_save = PaymentEvent.save

    def fail_save(*args, **kwargs):
        raise RuntimeError("Synthetic persistence failure")

    monkeypatch.setattr(PaymentEvent, "save", fail_save)
    with pytest.raises(RuntimeError):
        reconcile_event(event.pk)
    assert not Payment.objects.exists()
    scope.charge.refresh_from_db()
    event.refresh_from_db()
    assert scope.charge.status == Charge.Status.PENDING
    assert event.status == PaymentEvent.Status.RECEIVED
    monkeypatch.setattr(PaymentEvent, "save", original_save)
    assert reconcile_event(event.pk).status == PaymentEvent.Status.RECONCILED


def test_worker_limit_and_repeat_runs(scope):
    first = scope.new_event()
    second = scope.new_event(charge_id=scope.new_charge().pk)
    output = StringIO()
    call_command("reconcile_payments", limit=1, stdout=output)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == PaymentEvent.Status.RECONCILED
    assert second.status == PaymentEvent.Status.RECEIVED
    call_command("reconcile_payments", stdout=output)
    assert Payment.objects.count() == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": -1},
        {"currency": "brl"},
        {"charge_reference": 0},
        {"status": "RECONCILED"},
        {"status": "DISCREPANCY"},
    ],
)
def test_database_event_constraints(scope, changes):
    event = scope.new_event()
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentEvent.objects.filter(pk=event.pk).update(**changes)


def test_database_payment_is_unique_per_charge(scope):
    event = scope.new_event()
    reconcile_event(event.pk)
    payment = Payment.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        Payment.objects.create(
            clinic=scope.clinic,
            charge=scope.charge,
            source_event=scope.new_event(),
            payment_reference="another-reference",
            amount=payment.amount,
            currency="BRL",
            paid_at=payment.paid_at,
        )
