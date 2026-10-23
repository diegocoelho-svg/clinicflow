import re
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.payments.models import Payment, PaymentEvent
from apps.payments.types import PaymentNotification


class ReferenceField(serializers.IntegerField):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(min_value=1, max_value=9223372036854775807, **kwargs)

    def to_internal_value(self, data: Any) -> int:
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class PaymentNotificationSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    clinic_id = ReferenceField()
    charge_id = ReferenceField()
    payment_reference = serializers.RegexField(
        r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", max_length=128, trim_whitespace=False
    )
    amount = serializers.CharField(max_length=23, trim_whitespace=False)
    currency = serializers.RegexField(
        r"\A[A-Z]{3}\Z", max_length=3, trim_whitespace=False
    )
    paid_at = serializers.DateTimeField()

    def validate_amount(self, value: str) -> Decimal:
        if not isinstance(self.initial_data.get("amount"), str) or not re.fullmatch(
            r"(0|[1-9][0-9]{0,19})\.[0-9]{2}", value
        ):
            raise serializers.ValidationError(
                "Use an exact nonnegative decimal string."
            )
        return Decimal(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        for field in ("event_id", "payment_reference", "currency", "paid_at"):
            if not isinstance(self.initial_data[field], str):
                raise serializers.ValidationError({field: ["Use a JSON string."]})
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError("Unknown payment notification fields.")
        return attrs

    def to_notification(self) -> PaymentNotification:
        return PaymentNotification(**self.validated_data)


class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = (
            "id",
            "event_id",
            "clinic",
            "charge_reference",
            "payment_reference",
            "amount",
            "currency",
            "paid_at",
            "status",
            "discrepancy_code",
            "payment",
            "received_at",
            "processed_at",
        )
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "clinic",
            "charge",
            "payment_reference",
            "source_event",
            "amount",
            "currency",
            "paid_at",
            "reconciled_at",
        )
        read_only_fields = fields
