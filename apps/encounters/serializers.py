from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.encounters.models import Encounter
from apps.patients.models import Patient


class EncounterSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.none())

    class Meta:
        model = Encounter
        fields = (
            "id",
            "clinic",
            "patient",
            "performed_at",
            "description",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "clinic", "created_at", "updated_at")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        clinic = self.context.get("clinic")
        if clinic is not None:
            self.fields["patient"].queryset = Patient.objects.filter(clinic=clinic)

    def validate_patient(self, value: Patient) -> Patient:
        if self.instance is not None and value.pk != self.instance.patient_id:
            raise serializers.ValidationError(
                "Patient cannot be changed after encounter creation."
            )
        return value

    def validate_performed_at(self, value: datetime) -> datetime:
        if value > timezone.now():
            raise serializers.ValidationError("Performed time cannot be in the future.")
        return value
