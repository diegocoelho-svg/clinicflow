from django.db.models import QuerySet
from rest_framework import mixins
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated

from apps.clinics.access import ClinicScopedViewSet
from apps.procedures.models import Procedure
from apps.procedures.permissions import CanManageProcedureCatalog
from apps.procedures.serializers import ProcedureSerializer


class ProcedureViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    ClinicScopedViewSet,
):
    serializer_class = ProcedureSerializer
    permission_classes = [IsAuthenticated, CanManageProcedureCatalog]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Procedure]:
        return Procedure.objects.filter(clinic=self.clinic_membership.clinic)

    def perform_create(self, serializer: ProcedureSerializer) -> None:
        serializer.save(clinic=self.clinic_membership.clinic)
