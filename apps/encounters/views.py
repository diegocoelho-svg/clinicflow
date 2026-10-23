from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.clinics.access import ClinicScopedViewSet
from apps.encounters.models import Encounter, EncounterItem
from apps.encounters.serializers import EncounterItemSerializer, EncounterSerializer
from apps.encounters.services import delete_encounter_item


class EncounterViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    ClinicScopedViewSet,
):
    serializer_class = EncounterSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

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
    ClinicScopedViewSet,
):
    serializer_class = EncounterItemSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    encounter: Encounter

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        self.encounter = get_object_or_404(
            Encounter,
            clinic=self.clinic,
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

    def perform_destroy(self, instance: EncounterItem) -> None:
        delete_encounter_item(encounter_id=self.encounter.pk, item_id=instance.pk)
