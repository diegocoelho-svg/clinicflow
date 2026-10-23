import hashlib
import hmac
import re
import time

from django.conf import settings

from apps.payments.exceptions import InvalidWebhookSignature, WebhookUnavailable

MAX_BODY_BYTES = 65536
SIGNATURE_TOLERANCE_SECONDS = 300


def webhook_secret() -> bytes:
    secret = getattr(settings, "SIMULATED_PAYMENT_WEBHOOK_SECRET", "")
    if not isinstance(secret, str) or len(secret.encode()) < 32:
        raise WebhookUnavailable()
    return secret.encode()


def signature_headers(body: bytes, *, timestamp: int | None = None) -> dict[str, str]:
    timestamp_text = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(
        webhook_secret(), timestamp_text.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return {
        "X-Webhook-Timestamp": timestamp_text,
        "X-Webhook-Signature": f"sha256={digest}",
    }


def verify_signature(body: bytes, timestamp: str, signature: str) -> None:
    secret = webhook_secret()
    if not re.fullmatch(r"[0-9]{1,12}", timestamp) or not re.fullmatch(
        r"sha256=[0-9a-f]{64}", signature
    ):
        raise InvalidWebhookSignature()
    if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
        raise InvalidWebhookSignature()
    expected = hmac.new(
        secret, timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.removeprefix("sha256=")):
        raise InvalidWebhookSignature()
