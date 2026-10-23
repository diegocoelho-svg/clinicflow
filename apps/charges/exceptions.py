from apps.core.exceptions import Conflict


class ChargeConflict(Conflict):
    default_detail = "The operation conflicts with the current charge state."
    code = "charge_conflict"
