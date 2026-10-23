import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentNotification:
    event_id: UUID
    clinic_id: int
    charge_id: int
    payment_reference: str
    amount: Decimal
    currency: str
    paid_at: datetime

    def canonical_payload(self) -> dict[str, str | int]:
        return {
            "event_id": str(self.event_id),
            "clinic_id": self.clinic_id,
            "charge_id": self.charge_id,
            "payment_reference": self.payment_reference,
            "amount": format(self.amount, ".2f"),
            "currency": self.currency,
            "paid_at": self.paid_at.astimezone(UTC).isoformat(),
        }

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(canonical).hexdigest()
