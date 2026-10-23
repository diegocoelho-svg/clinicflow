from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.charges.models import Charge
from apps.charges.permissions import CanAccessCharges
from apps.charges.serializers import (
    CancelChargeSerializer,
    ChargeSerializer,
    IssueChargeSerializer,
)
from apps.charges.services import cancel_charge, issue_charge
from apps.clinics.access import ClinicScopedViewSet
from apps.encounters.models import Encounter


class ChargeViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, ClinicScopedViewSet
):
    serializer_class = ChargeSerializer
    permission_classes = [IsAuthenticated, CanAccessCharges]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[Charge]:
        return Charge.objects.filter(
            clinic=self.clinic_membership.clinic
        ).prefetch_related("items")

    def get_serializer_class(self):
        if self.action == "create":
            return IssueChargeSerializer
        if self.action == "cancel":
            return CancelChargeSerializer
        return ChargeSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        encounter = get_object_or_404(
            Encounter,
            pk=self.kwargs["encounter_id"],
            clinic=self.clinic_membership.clinic,
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            key = serializers.UUIDField().run_validation(
                request.headers.get("Idempotency-Key")
            )
        except serializers.ValidationError as error:
            raise serializers.ValidationError(
                {"Idempotency-Key": error.detail}
            ) from error
        charge, created = issue_charge(
            clinic_id=encounter.clinic_id,
            encounter_id=encounter.pk,
            actor=request.user,
            idempotency_key=key,
        )
        return Response(
            ChargeSerializer(charge).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def cancel(self, request: Request, *args, **kwargs) -> Response:
        original = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        charge = cancel_charge(
            clinic_id=self.clinic_membership.clinic_id,
            charge_id=original.pk,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(ChargeSerializer(charge).data)
