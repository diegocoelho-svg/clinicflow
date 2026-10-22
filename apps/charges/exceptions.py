from rest_framework.exceptions import APIException


class ChargeConflict(APIException):
    status_code = 409
    default_detail = "The operation conflicts with the current charge state."
    default_code = "charge_conflict"
