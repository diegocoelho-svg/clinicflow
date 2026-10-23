from django.db import IntegrityError, transaction

from apps.core.exceptions import BusinessRuleViolation, ResourceNotFound
from apps.encounters.exceptions import EncounterItemsLocked
from apps.encounters.locking import lock_encounter
from apps.encounters.models import Encounter, EncounterItem
from apps.procedures.models import Procedure


def _lock_editable_encounter(encounter_id: int) -> Encounter:
    encounter = lock_encounter(encounter_id)
    if encounter.charges.active().exists():
        raise EncounterItemsLocked()
    return encounter


def _get_item(encounter: Encounter, item_id: int) -> EncounterItem:
    try:
        return EncounterItem.objects.get(pk=item_id, encounter=encounter)
    except EncounterItem.DoesNotExist as error:
        raise ResourceNotFound() from error


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
                raise BusinessRuleViolation(
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
            raise BusinessRuleViolation(
                {"procedure": ["This procedure is already present in the encounter."]}
            ) from error
        raise


def update_encounter_item(
    *, encounter_id: int, item_id: int, quantity: int | None = None
) -> EncounterItem:
    with transaction.atomic():
        encounter = _lock_editable_encounter(encounter_id)
        # Re-read under the parent lock; a stale serializer cannot restore a deletion.
        item = _get_item(encounter, item_id)
        if quantity is not None:
            item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])
        return item


def delete_encounter_item(*, encounter_id: int, item_id: int) -> None:
    with transaction.atomic():
        encounter = _lock_editable_encounter(encounter_id)
        _get_item(encounter, item_id).delete()
