from apps.core.exceptions import Conflict


class EncounterItemsLocked(Conflict):
    default_detail = "Cancel the encounter's charge before changing its items."
    code = "encounter_items_locked"
