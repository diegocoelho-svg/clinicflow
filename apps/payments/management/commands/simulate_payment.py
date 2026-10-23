import json
from http.client import HTTPException
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.charges.models import Charge
from apps.payments.exceptions import WebhookUnavailable
from apps.payments.signatures import signature_headers
from apps.payments.types import PaymentNotification


class Command(BaseCommand):
    help = "Send one signed fictional payment to this container's local API."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("charge_id", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            charge = Charge.objects.get(pk=options["charge_id"])
        except Charge.DoesNotExist as error:
            raise CommandError("Charge not found.") from error
        if charge.status != Charge.Status.PENDING:
            raise CommandError("Only a pending charge can be simulated.")
        notification = PaymentNotification(
            event_id=uuid4(),
            clinic_id=charge.clinic_id,
            charge_id=charge.pk,
            payment_reference=f"simulated:{uuid4()}",
            amount=charge.amount,
            currency=charge.currency,
            paid_at=timezone.now(),
        )
        payload = notification.canonical_payload()
        body = json.dumps(payload, separators=(",", ":")).encode()
        try:
            headers = signature_headers(body)
        except WebhookUnavailable as error:
            raise CommandError(str(error.detail)) from error
        request = Request(
            "http://127.0.0.1:8000/api/v1/payment-webhooks/simulated/",
            data=body,
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                receipt = json.load(response)
        except (OSError, HTTPException, ValueError) as error:
            # Never retry with a fresh event/payment identity after uncertainty.
            raise CommandError(
                f"Payment submission unconfirmed. Check event {payload['event_id']} "
                "before retrying; no second event was sent."
            ) from error
        self.stdout.write(json.dumps(receipt))
