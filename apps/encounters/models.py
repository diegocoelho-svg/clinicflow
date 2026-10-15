from django.db import models

from apps.clinics.models import Clinic
from apps.patients.models import Patient


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
