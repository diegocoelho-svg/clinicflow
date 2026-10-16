from functools import cached_property

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated

from apps.clinics.models import ClinicMembership
from apps.procedures.models import Procedure
from apps.procedures.permissions import CanManageProcedureCatalog
from apps.procedures.serializers import ProcedureSerializer


class ProcedureViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProcedureSerializer
    permission_classes = [IsAuthenticated, CanManageProcedureCatalog]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @cached_property
    def clinic_membership(self) -> ClinicMembership:
        return get_object_or_404(
            ClinicMembership.objects.select_related("clinic"),
            clinic_id=self.kwargs["clinic_id"],
            user=self.request.user,
        )

    def get_queryset(self) -> QuerySet[Procedure]:
        return Procedure.objects.filter(clinic=self.clinic_membership.clinic)

    def perform_create(self, serializer: ProcedureSerializer) -> None:
        serializer.save(clinic=self.clinic_membership.clinic)
