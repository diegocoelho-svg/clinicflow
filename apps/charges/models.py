from decimal import Decimal
from typing import Self

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.clinics.models import Clinic
from apps.encounters.models import Encounter
from apps.procedures.models import Procedure

MAX_CHARGE_AMOUNT = Decimal("99999999999999999999.99")


class ChargeQuerySet(models.QuerySet):
    def active(self) -> Self:
        return self.exclude(status=Charge.Status.CANCELLED)


class Charge(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        NO_PAYMENT_REQUIRED = "NO_PAYMENT_REQUIRED", "No payment required"
        CANCELLED = "CANCELLED", "Cancelled"
        PAID = "PAID", "Paid"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="charges")
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="charges"
    )
    amount = models.DecimalField(
        max_digits=22,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(MAX_CHARGE_AMOUNT),
        ],
    )
    currency = models.CharField(max_length=3, default="BRL")
    status = models.CharField(max_length=20, choices=Status.choices)
    idempotency_key = models.UUIDField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_charges",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_charges",
        null=True,
        blank=True,
    )
    # NULL distinguishes no cancellation event from an invalid blank reason.
    cancellation_reason = models.CharField(  # noqa: DJ001
        max_length=1000, null=True, blank=True
    )

    objects = ChargeQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "idempotency_key"], name="unique_clinic_charge_key"
            ),
            models.UniqueConstraint(
                fields=["encounter"],
                condition=~models.Q(status="CANCELLED"),
                name="unique_non_cancelled_encounter_charge",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0, amount__lte=MAX_CHARGE_AMOUNT),
                name="charge_amount_valid_range",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="BRL"), name="charge_currency_brl"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status__in=["PENDING", "PAID"], amount__gt=0)
                    | models.Q(status="NO_PAYMENT_REQUIRED", amount=0)
                    | models.Q(status="CANCELLED")
                ),
                name="charge_status_amount_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(
                            status="CANCELLED",
                            cancelled_at__isnull=False,
                            cancelled_by__isnull=False,
                            cancellation_reason__isnull=False,
                        )
                        & ~models.Q(cancellation_reason__regex=r"^\s*$")
                    )
                    | (
                        ~models.Q(status="CANCELLED")
                        & models.Q(
                            cancelled_at__isnull=True,
                            cancelled_by__isnull=True,
                            cancellation_reason__isnull=True,
                        )
                    )
                ),
                name="charge_cancellation_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"Charge {self.pk} for encounter {self.encounter_id}"


class ChargeItem(models.Model):
    charge = models.ForeignKey(Charge, on_delete=models.PROTECT, related_name="items")
    procedure = models.ForeignKey(
        Procedure, on_delete=models.PROTECT, related_name="charge_items"
    )
    procedure_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["charge", "procedure"], name="unique_charge_procedure_item"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="charge_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(procedure_name__regex=r"^\s*$"),
                name="charge_item_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    unit_price__gte=0, unit_price__lte=Decimal("9999999999.99")
                ),
                name="charge_item_price_valid_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.charge_id}:{self.procedure_id}"

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity
