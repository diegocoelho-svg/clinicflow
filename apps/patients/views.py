from django.db.models import QuerySet
from rest_framework import mixins
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated

from apps.clinics.access import ClinicScopedViewSet
from apps.patients.models import Patient
from apps.patients.serializers import PatientSerializer


class PatientViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    ClinicScopedViewSet,
):
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Patient]:
        return Patient.objects.filter(clinic=self.clinic)

    def perform_create(self, serializer: PatientSerializer) -> None:
        serializer.save(clinic=self.clinic)
