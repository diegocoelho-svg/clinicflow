from django.urls import path

from apps.charges.views import ChargeViewSet

app_name = "charges"

urlpatterns = [
    path(
        "clinics/<int:clinic_id>/encounters/<int:encounter_id>/charges/",
        ChargeViewSet.as_view({"post": "create"}),
        name="encounter-charge-list",
    ),
    path(
        "clinics/<int:clinic_id>/charges/",
        ChargeViewSet.as_view({"get": "list"}),
        name="charge-list",
    ),
    path(
        "clinics/<int:clinic_id>/charges/<int:pk>/",
        ChargeViewSet.as_view({"get": "retrieve"}),
        name="charge-detail",
    ),
    path(
        "clinics/<int:clinic_id>/charges/<int:pk>/cancel/",
        ChargeViewSet.as_view({"post": "cancel"}),
        name="charge-cancel",
    ),
]
