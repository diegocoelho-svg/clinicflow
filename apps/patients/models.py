from django.db import models

from apps.clinics.models import Clinic


class Patient(models.Model):
    clinic = models.ForeignKey(
        Clinic, on_delete=models.PROTECT, related_name="patients"
    )
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    email = models.EmailField(max_length=254, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(full_name__regex=r"^\s*$"),
                name="patient_full_name_not_blank",
            )
        ]

    def __str__(self) -> str:
        return self.full_name
