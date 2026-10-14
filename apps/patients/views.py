from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.patients.serializers import PatientSerializer


class PatientViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]
    clinic: Clinic

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        self.clinic = get_object_or_404(
            Clinic.objects.filter(memberships__user=request.user),
            pk=self.kwargs["clinic_id"],
        )

    def get_queryset(self) -> QuerySet[Patient]:
        return Patient.objects.filter(clinic=self.clinic)

    def perform_create(self, serializer: PatientSerializer) -> None:
        serializer.save(clinic=self.clinic)
