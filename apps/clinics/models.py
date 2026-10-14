from django.conf import settings
from django.db import models


class Clinic(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="clinic_name_not_blank",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ClinicMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MEMBER = "MEMBER", "Member"

    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clinic_memberships",
    )
    role = models.CharField(max_length=6, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "user"], name="unique_clinic_user_membership"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["OWNER", "MEMBER"]),
                name="clinic_membership_valid_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.clinic_id}:{self.role}"
