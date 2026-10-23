import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.payments.models import PaymentEvent
from apps.payments.services import reconcile_event


class Command(BaseCommand):
    help = "Reconcile persisted simulated-payment events in a separate process."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        try:
            while True:
                ids = list(
                    PaymentEvent.objects.filter(
                        status=PaymentEvent.Status.RECEIVED
                    ).values_list("pk", flat=True)[: options["limit"]]
                )
                for event_pk in ids:
                    event = reconcile_event(event_pk)
                    self.stdout.write(f"{event.event_id}: {event.status}")
                if not options["watch"]:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Payment worker stopped.")
