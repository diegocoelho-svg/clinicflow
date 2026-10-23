from django.db import transaction
from django.utils import timezone

from apps.charges.models import Charge
from apps.clinics.models import Clinic
from apps.core.exceptions import BusinessRuleViolation
from apps.encounters.locking import lock_encounter
from apps.payments.exceptions import PaymentConflict
from apps.payments.locking import lock_payment_reference
from apps.payments.models import Payment, PaymentEvent
from apps.payments.types import PaymentNotification


def accept_event(data: PaymentNotification) -> tuple[PaymentEvent, bool]:
    digest = data.fingerprint()
    previous = PaymentEvent.objects.filter(event_id=data.event_id).first()
    if previous is not None:
        if previous.payload_hash != digest:
            raise PaymentConflict()
        return previous, False
    if not Clinic.objects.filter(pk=data.clinic_id).exists():
        raise BusinessRuleViolation({"clinic_id": ["Unknown clinic reference."]})
    event, created = PaymentEvent.objects.get_or_create(
        event_id=data.event_id,
        defaults={
            "clinic_id": data.clinic_id,
            "charge_reference": data.charge_id,
            "payment_reference": data.payment_reference,
            "amount": data.amount,
            "currency": data.currency,
            "paid_at": data.paid_at,
            "payload_hash": digest,
        },
    )
    if event.payload_hash != digest:
        raise PaymentConflict()
    return event, created


def _finish(
    event: PaymentEvent,
    *,
    payment: Payment | None = None,
    discrepancy: PaymentEvent.Discrepancy | None = None,
) -> PaymentEvent:
    event.payment = payment
    event.discrepancy_code = discrepancy or ""
    event.status = (
        PaymentEvent.Status.DISCREPANCY
        if discrepancy
        else PaymentEvent.Status.RECONCILED
    )
    event.processed_at = timezone.now()
    event.save(update_fields=["payment", "discrepancy_code", "status", "processed_at"])
    return event


def reconcile_event(event_pk: int) -> PaymentEvent:
    with transaction.atomic():
        event = PaymentEvent.objects.get(pk=event_pk)
        lock_payment_reference(event.payment_reference)

        charge = Charge.objects.filter(
            pk=event.charge_reference, clinic_id=event.clinic_id
        ).first()
        if charge is not None:
            # Cancellation and item writes use this same parent lock.
            lock_encounter(charge.encounter_id, clinic_id=event.clinic_id)
        event = PaymentEvent.objects.select_for_update().get(pk=event_pk)
        if event.status != PaymentEvent.Status.RECEIVED:
            return event
        if charge is None:
            return _finish(event, discrepancy=PaymentEvent.Discrepancy.CHARGE_NOT_FOUND)
        charge = Charge.objects.get(pk=charge.pk)
        existing = Payment.objects.filter(
            payment_reference=event.payment_reference
        ).first()
        if existing is not None:
            if (
                existing.charge_id == charge.pk
                and existing.clinic_id == event.clinic_id
                and existing.amount == event.amount
                and existing.currency == event.currency
                and existing.paid_at == event.paid_at
            ):
                return _finish(event, payment=existing)
            return _finish(
                event, discrepancy=PaymentEvent.Discrepancy.PAYMENT_REFERENCE_CONFLICT
            )
        if charge.status != Charge.Status.PENDING:
            return _finish(
                event, discrepancy=PaymentEvent.Discrepancy.CHARGE_NOT_PENDING
            )
        if event.currency != charge.currency:
            return _finish(
                event, discrepancy=PaymentEvent.Discrepancy.CURRENCY_MISMATCH
            )
        if event.amount != charge.amount:
            return _finish(event, discrepancy=PaymentEvent.Discrepancy.AMOUNT_MISMATCH)
        payment = Payment.objects.create(
            clinic_id=event.clinic_id,
            charge=charge,
            payment_reference=event.payment_reference,
            source_event=event,
            amount=event.amount,
            currency=event.currency,
            paid_at=event.paid_at,
        )
        charge.status = Charge.Status.PAID
        charge.save(update_fields=["status", "updated_at"])
        return _finish(event, payment=payment)
