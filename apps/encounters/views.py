from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.clinics.models import Clinic
from apps.encounters.models import Encounter, EncounterItem
from apps.encounters.serializers import EncounterItemSerializer, EncounterSerializer


class EncounterViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EncounterSerializer
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

    def get_queryset(self) -> QuerySet[Encounter]:
        return Encounter.objects.filter(clinic=self.clinic)

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["clinic"] = self.clinic
        return context

    def perform_create(self, serializer: EncounterSerializer) -> None:
        serializer.save(clinic=self.clinic)


class EncounterItemViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EncounterItemSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    encounter: Encounter

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        self.encounter = get_object_or_404(
            Encounter.objects.filter(clinic__memberships__user=request.user),
            clinic_id=self.kwargs["clinic_id"],
            pk=self.kwargs["encounter_id"],
        )

    def get_queryset(self) -> QuerySet[EncounterItem]:
        return EncounterItem.objects.filter(encounter=self.encounter)

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["encounter"] = self.encounter
        return context

    def perform_create(self, serializer: EncounterItemSerializer) -> None:
        serializer.save(encounter=self.encounter)
