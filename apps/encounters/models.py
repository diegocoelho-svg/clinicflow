from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.procedures.models import Procedure


class Encounter(models.Model):
    clinic = models.ForeignKey(
        Clinic, on_delete=models.PROTECT, related_name="encounters"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="encounters"
    )
    performed_at = models.DateTimeField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(description__regex=r"^\s*$"),
                name="encounter_description_not_blank",
            )
        ]

    def __str__(self) -> str:
        return f"Encounter {self.pk} for patient {self.patient_id}"


class EncounterItem(models.Model):
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="items"
    )
    procedure = models.ForeignKey(
        Procedure, on_delete=models.PROTECT, related_name="encounter_items"
    )
    procedure_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["encounter", "procedure"],
                name="unique_encounter_procedure_item",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="encounter_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(procedure_name__regex=r"^\s*$"),
                name="encounter_item_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    unit_price__gte=0, unit_price__lte=Decimal("9999999999.99")
                ),
                name="encounter_item_unit_price_valid_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.encounter_id}:{self.procedure_id}"

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity
