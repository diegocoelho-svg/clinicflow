"""Translate business failures at the HTTP boundary."""

from typing import Any

from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import (
    AccessDenied,
    BusinessRuleViolation,
    Conflict,
    DomainError,
    ResourceNotFound,
    ServiceUnavailable,
)

DOMAIN_STATUS = {
    ResourceNotFound: 404,
    Conflict: 409,
    AccessDenied: 403,
    ServiceUnavailable: 503,
}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, BusinessRuleViolation):
        exc = ValidationError(detail=exc.detail, code=exc.code)
    elif isinstance(exc, DomainError):
        for error_type, status_code in DOMAIN_STATUS.items():
            if isinstance(exc, error_type):
                mapped = APIException(detail=exc.detail, code=exc.code)
                mapped.status_code = status_code
                exc = mapped
                break
    return drf_exception_handler(exc, context)


class RequestTooLarge(APIException):
    status_code = 413
    default_detail = "Request body exceeds the supported size."
