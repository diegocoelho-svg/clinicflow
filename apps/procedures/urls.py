from django.urls import path

from apps.procedures.views import ProcedureViewSet

app_name = "procedures"

urlpatterns = [
    path(
        "clinics/<int:clinic_id>/procedures/",
        ProcedureViewSet.as_view({"get": "list", "post": "create"}),
        name="procedure-list",
    ),
    path(
        "clinics/<int:clinic_id>/procedures/<int:pk>/",
        ProcedureViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="procedure-detail",
    ),
]
