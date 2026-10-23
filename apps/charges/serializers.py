from rest_framework import serializers

from apps.charges.models import Charge, ChargeItem


class IssueChargeSerializer(serializers.Serializer):
    def validate(self, attrs: dict) -> dict:
        if self.initial_data:
            raise serializers.ValidationError(
                "Send an empty JSON object; charge values are calculated by the server."
            )
        return attrs


class CancelChargeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=False)

    def validate(self, attrs: dict) -> dict:
        if set(self.initial_data) - {"reason"}:
            raise serializers.ValidationError("Only reason can be supplied.")
        return attrs


class ChargeItemSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=22, decimal_places=2, read_only=True)

    class Meta:
        model = ChargeItem
        fields = (
            "id",
            "procedure",
            "procedure_name",
            "quantity",
            "unit_price",
            "total",
        )
        read_only_fields = fields


class ChargeSerializer(serializers.ModelSerializer):
    items = ChargeItemSerializer(many=True, read_only=True)

    class Meta:
        model = Charge
        fields = (
            "id",
            "clinic",
            "encounter",
            "amount",
            "currency",
            "status",
            "idempotency_key",
            "created_by",
            "created_at",
            "updated_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "items",
        )
        read_only_fields = fields
