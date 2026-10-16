from rest_framework import serializers

from apps.procedures.models import Procedure


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = (
            "id",
            "clinic",
            "name",
            "unit_price",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "clinic", "created_at", "updated_at")
