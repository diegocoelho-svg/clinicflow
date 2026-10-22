from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.charges.exceptions import ChargeConflict
from apps.charges.models import Charge
from apps.encounters.models import Encounter, EncounterItem
from apps.procedures.models import Procedure


def _lock_editable_encounter(encounter_id: int) -> Encounter:
    encounter = get_object_or_404(
        Encounter.objects.select_for_update(), pk=encounter_id
    )
    if encounter.charges.exclude(status=Charge.Status.CANCELLED).exists():
        raise ChargeConflict("Cancel the encounter's charge before changing its items.")
    return encounter


def create_encounter_item(
    *, encounter_id: int, procedure_id: int, quantity: int
) -> EncounterItem:
    try:
        with transaction.atomic():
            encounter = _lock_editable_encounter(encounter_id)
            # Lock order is always encounter, then catalog procedure.
            procedure = (
                Procedure.objects.select_for_update()
                .filter(pk=procedure_id, clinic_id=encounter.clinic_id)
                .first()
            )
            if procedure is None or not procedure.is_active:
                raise ValidationError(
                    {"procedure": ["An active procedure from this clinic is required."]}
                )
            return EncounterItem.objects.create(
                encounter=encounter,
                procedure=procedure,
                procedure_name=procedure.name,
                unit_price=procedure.unit_price,
                quantity=quantity,
            )
    except IntegrityError as error:
        constraint = getattr(
            getattr(error.__cause__, "diag", None), "constraint_name", None
        )
        if constraint == "unique_encounter_procedure_item":
            raise ValidationError(
                {"procedure": ["This procedure is already present in the encounter."]}
            ) from error
        raise


def update_encounter_item(
    *, encounter_id: int, item_id: int, changes: dict
) -> EncounterItem:
    with transaction.atomic():
        encounter = _lock_editable_encounter(encounter_id)
        # Re-read under the parent lock so a stale serializer cannot restore
        # an item that another request has already deleted.
        item = get_object_or_404(EncounterItem, pk=item_id, encounter=encounter)
        if "quantity" in changes:
            item.quantity = changes["quantity"]
        item.save(update_fields=["quantity", "updated_at"])
        return item


def delete_encounter_item(*, encounter_id: int, item_id: int) -> None:
    with transaction.atomic():
        encounter = _lock_editable_encounter(encounter_id)
        item = get_object_or_404(EncounterItem, pk=item_id, encounter=encounter)
        item.delete()
