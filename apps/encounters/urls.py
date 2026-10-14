from django.urls import path

from apps.encounters.views import EncounterViewSet

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
]
