"""Business failures independent of Django REST Framework."""

type ErrorDetail = str | dict[str, list[str]]


class DomainError(Exception):
    default_detail = "The operation could not be completed."
    code = "domain_error"

    def __init__(self, detail: ErrorDetail | None = None) -> None:
        self.detail = self.default_detail if detail is None else detail
        super().__init__(str(self.detail))


class ResourceNotFound(DomainError):
    default_detail = "Not found."
    code = "not_found"


class BusinessRuleViolation(DomainError):
    code = "invalid"


class Conflict(DomainError):
    code = "conflict"


class AccessDenied(DomainError):
    code = "permission_denied"


class ServiceUnavailable(DomainError):
    code = "service_unavailable"
