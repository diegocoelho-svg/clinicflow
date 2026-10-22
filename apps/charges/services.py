from decimal import Decimal
from uuid import UUID

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.charges.exceptions import ChargeConflict
from apps.charges.models import MAX_CHARGE_AMOUNT, Charge, ChargeItem
from apps.encounters.models import Encounter


def _check_replay(charge: Charge, encounter_id: int) -> tuple[Charge, bool]:
    if charge.encounter_id != encounter_id:
        raise ChargeConflict("This idempotency key was used for another encounter.")
    return charge, False


def issue_charge(
    *, clinic_id: int, encounter_id: int, actor: User, idempotency_key: UUID
) -> tuple[Charge, bool]:
    try:
        with transaction.atomic():
            # Item writers and cancellation acquire this same parent lock first.
            encounter = get_object_or_404(
                Encounter.objects.select_for_update(),
                pk=encounter_id,
                clinic_id=clinic_id,
            )
            previous = Charge.objects.filter(
                clinic_id=clinic_id, idempotency_key=idempotency_key
            ).first()
            if previous is not None:
                return _check_replay(previous, encounter_id)
            if encounter.charges.exclude(status=Charge.Status.CANCELLED).exists():
                raise ChargeConflict(
                    "This encounter already has a non-cancelled charge."
                )

            items = list(encounter.items.all())
            if not items:
                raise ValidationError({"encounter": ["At least one item is required."]})
            amount = sum((item.total for item in items), start=Decimal("0.00"))
            if (
                not amount.is_finite()
                or not Decimal("0.00") <= amount <= MAX_CHARGE_AMOUNT
            ):
                raise ValidationError(
                    {"amount": ["The charge total exceeds its supported range."]}
                )

            charge = Charge.objects.create(
                clinic_id=clinic_id,
                encounter=encounter,
                amount=amount,
                currency="BRL",
                status=(
                    Charge.Status.NO_PAYMENT_REQUIRED
                    if amount == 0
                    else Charge.Status.PENDING
                ),
                idempotency_key=idempotency_key,
                created_by=actor,
            )
            ChargeItem.objects.bulk_create(
                [
                    ChargeItem(
                        charge=charge,
                        procedure_id=item.procedure_id,
                        procedure_name=item.procedure_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                    for item in items
                ]
            )
            return charge, True
    except IntegrityError as error:
        # A key can also race across two different encounter locks. Query only
        # after atomic has rolled back; unrelated database errors must propagate.
        constraint = getattr(
            getattr(error.__cause__, "diag", None), "constraint_name", None
        )
        if constraint == "unique_clinic_charge_key":
            previous = Charge.objects.get(
                clinic_id=clinic_id, idempotency_key=idempotency_key
            )
            return _check_replay(previous, encounter_id)
        if constraint == "unique_non_cancelled_encounter_charge":
            raise ChargeConflict(
                "This encounter already has a non-cancelled charge."
            ) from error
        raise


def cancel_charge(
    *, clinic_id: int, charge_id: int, actor: User, reason: str
) -> Charge:
    with transaction.atomic():
        original = get_object_or_404(Charge, pk=charge_id, clinic_id=clinic_id)
        get_object_or_404(
            Encounter.objects.select_for_update(),
            pk=original.encounter_id,
            clinic_id=clinic_id,
        )
        charge = Charge.objects.get(pk=original.pk)
        if charge.status == Charge.Status.CANCELLED:
            return charge
        if charge.status == Charge.Status.PAID:
            raise ChargeConflict(
                "A paid charge cannot be cancelled; it requires a refund."
            )
        charge.status = Charge.Status.CANCELLED
        charge.cancelled_at = timezone.now()
        charge.cancelled_by = actor
        charge.cancellation_reason = reason
        charge.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )
        return charge
