from django.urls import path

from apps.core.views import HealthView, ReadinessView

app_name = "core"

urlpatterns = [
    path("", HealthView.as_view(), name="health"),
    path("ready/", ReadinessView.as_view(), name="readiness"),
]
