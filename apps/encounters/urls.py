from django.urls import path

from apps.encounters.views import EncounterItemViewSet, EncounterViewSet

app_name = "encounters"

urlpatterns = [
    path(
        "clinics/<int:clinic_id>/encounters/",
        EncounterViewSet.as_view({"get": "list", "post": "create"}),
        name="encounter-list",
    ),
    path(
        "clinics/<int:clinic_id>/encounters/<int:pk>/",
        EncounterViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="encounter-detail",
    ),
    path(
        "clinics/<int:clinic_id>/encounters/<int:encounter_id>/items/",
        EncounterItemViewSet.as_view({"get": "list", "post": "create"}),
        name="encounter-item-list",
    ),
    path(
        "clinics/<int:clinic_id>/encounters/<int:encounter_id>/items/<int:pk>/",
        EncounterItemViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="encounter-item-detail",
    ),
]
