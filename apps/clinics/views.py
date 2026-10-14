from django.db import transaction
from django.db.models import QuerySet
from rest_framework import mixins, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated

from apps.clinics.models import Clinic, ClinicMembership
from apps.clinics.permissions import IsClinicOwnerOrReadOnly
from apps.clinics.serializers import ClinicSerializer


class ClinicViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ClinicSerializer
    permission_classes = [IsAuthenticated, IsClinicOwnerOrReadOnly]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Clinic]:
        return Clinic.objects.filter(memberships__user=self.request.user)

    def perform_create(self, serializer: ClinicSerializer) -> None:
        with transaction.atomic():
            clinic = serializer.save()
            ClinicMembership.objects.create(
                clinic=clinic,
                user=self.request.user,
                role=ClinicMembership.Role.OWNER,
            )
