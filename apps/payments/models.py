from decimal import Decimal

from django.db import models

from apps.charges.models import MAX_CHARGE_AMOUNT, Charge
from apps.clinics.models import Clinic


class PaymentEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        RECONCILED = "RECONCILED", "Reconciled"
        DISCREPANCY = "DISCREPANCY", "Discrepancy"

    class Discrepancy(models.TextChoices):
        CHARGE_NOT_FOUND = "CHARGE_NOT_FOUND", "Charge not found"
        CHARGE_NOT_PENDING = "CHARGE_NOT_PENDING", "Charge not pending"
        CURRENCY_MISMATCH = "CURRENCY_MISMATCH", "Currency mismatch"
        AMOUNT_MISMATCH = "AMOUNT_MISMATCH", "Amount mismatch"
        PAYMENT_REFERENCE_CONFLICT = (
            "PAYMENT_REFERENCE_CONFLICT",
            "Payment reference conflict",
        )

    event_id = models.UUIDField(unique=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT)
    charge_reference = models.PositiveBigIntegerField()
    payment_reference = models.CharField(max_length=128)
    amount = models.DecimalField(max_digits=22, decimal_places=2)
    currency = models.CharField(max_length=3)
    paid_at = models.DateTimeField()
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED
    )
    discrepancy_code = models.CharField(
        max_length=40, choices=Discrepancy.choices, blank=True
    )
    payment = models.ForeignKey(
        "Payment",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["status", "id"], name="payment_event_queue")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0, amount__lte=MAX_CHARGE_AMOUNT),
                name="payment_event_amount_range",
            ),
            models.CheckConstraint(
                condition=models.Q(charge_reference__gt=0),
                name="payment_event_charge_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency__regex=r"^[A-Z]{3}$"),
                name="payment_event_currency_format",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="RECEIVED",
                        payment__isnull=True,
                        processed_at__isnull=True,
                        discrepancy_code="",
                    )
                    | models.Q(
                        status="RECONCILED",
                        payment__isnull=False,
                        processed_at__isnull=False,
                        discrepancy_code="",
                    )
                    | (
                        models.Q(
                            status="DISCREPANCY",
                            payment__isnull=True,
                            processed_at__isnull=False,
                        )
                        & ~models.Q(discrepancy_code="")
                    )
                ),
                name="payment_event_result_consistent",
            ),
        ]

    def __str__(self) -> str:
        return str(self.event_id)


class Payment(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT)
    charge = models.OneToOneField(
        Charge, on_delete=models.PROTECT, related_name="payment"
    )
    payment_reference = models.CharField(max_length=128, unique=True)
    source_event = models.OneToOneField(
        PaymentEvent, on_delete=models.PROTECT, related_name="created_payment"
    )
    amount = models.DecimalField(max_digits=22, decimal_places=2)
    currency = models.CharField(max_length=3, default="BRL")
    paid_at = models.DateTimeField()
    reconciled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    amount__gt=Decimal("0"), amount__lte=MAX_CHARGE_AMOUNT
                ),
                name="payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="BRL"), name="payment_currency_brl"
            ),
        ]

    def __str__(self) -> str:
        return f"Payment {self.pk} for charge {self.charge_id}"
