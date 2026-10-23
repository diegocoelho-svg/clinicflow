from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.encounters.models import Encounter, EncounterItem
from apps.encounters.services import create_encounter_item, update_encounter_item
from apps.patients.models import Patient
from apps.procedures.models import Procedure


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


class EncounterItemSerializer(serializers.ModelSerializer):
    procedure = serializers.PrimaryKeyRelatedField(queryset=Procedure.objects.none())
    total = serializers.DecimalField(max_digits=22, decimal_places=2, read_only=True)

    class Meta:
        model = EncounterItem
        fields = (
            "id",
            "encounter",
            "procedure",
            "procedure_name",
            "quantity",
            "unit_price",
            "total",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "encounter",
            "procedure_name",
            "unit_price",
            "total",
            "created_at",
            "updated_at",
        )
        # The parent comes from the URL; create handles database uniqueness conflicts.
        validators = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        encounter = self.context.get("encounter")
        if encounter is not None:
            self.fields["procedure"].queryset = Procedure.objects.filter(
                clinic_id=encounter.clinic_id
            )

    def validate_procedure(self, value: Procedure) -> Procedure:
        if self.instance is not None and value.pk != self.instance.procedure_id:
            raise serializers.ValidationError(
                "Procedure cannot be changed after item creation."
            )
        return value

    def create(self, validated_data: dict) -> EncounterItem:
        return create_encounter_item(
            encounter_id=validated_data["encounter"].pk,
            procedure_id=validated_data["procedure"].pk,
            quantity=validated_data.get("quantity", 1),
        )

    def update(self, instance: EncounterItem, validated_data: dict) -> EncounterItem:
        return update_encounter_item(
            encounter_id=instance.encounter_id,
            item_id=instance.pk,
            quantity=validated_data.get("quantity"),
        )
