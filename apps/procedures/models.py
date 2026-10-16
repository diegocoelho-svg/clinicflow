from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.clinics.models import Clinic


class Procedure(models.Model):
    clinic = models.ForeignKey(
        Clinic, on_delete=models.PROTECT, related_name="procedures"
    )
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="procedure_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    unit_price__gte=0, unit_price__lte=Decimal("9999999999.99")
                ),
                name="procedure_unit_price_valid_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name
