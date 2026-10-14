from django.urls import path

from apps.patients.views import PatientViewSet

app_name = "patients"

urlpatterns = [
    path(
        "clinics/<int:clinic_id>/patients/",
        PatientViewSet.as_view({"get": "list", "post": "create"}),
        name="patient-list",
    ),
    path(
        "clinics/<int:clinic_id>/patients/<int:pk>/",
        PatientViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="patient-detail",
    ),
]
