"""Parent lock shared by item writes, issuance, cancellation and payments."""

from apps.core.exceptions import ResourceNotFound
from apps.encounters.models import Encounter


def lock_encounter(encounter_id: int, *, clinic_id: int | None = None) -> Encounter:
    # Call inside transaction.atomic(), before reading or writing dependent rows.
    queryset = Encounter.objects.select_for_update()
    if clinic_id is not None:
        queryset = queryset.filter(clinic_id=clinic_id)
    try:
        return queryset.get(pk=encounter_id)
    except Encounter.DoesNotExist as error:
        raise ResourceNotFound() from error
