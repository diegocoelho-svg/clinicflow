from apps.core.exceptions import AccessDenied, Conflict, ServiceUnavailable


class PaymentConflict(Conflict):
    default_detail = "This event ID has already been used for different payment data."
    code = "payment_conflict"


class WebhookUnavailable(ServiceUnavailable):
    default_detail = "The simulated payment webhook is not configured."
    code = "webhook_unavailable"


class InvalidWebhookSignature(AccessDenied):
    default_detail = "Invalid webhook signature."
    code = "invalid_webhook_signature"
