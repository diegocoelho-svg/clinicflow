from datetime import date

from django.utils import timezone
from rest_framework import serializers

from apps.patients.models import Patient


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = (
            "id",
            "clinic",
            "full_name",
            "birth_date",
            "email",
            "phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "clinic", "created_at", "updated_at")

    def validate_birth_date(self, value: date) -> date:
        if value > timezone.localdate():
            raise serializers.ValidationError("Birth date cannot be in the future.")
        return value
