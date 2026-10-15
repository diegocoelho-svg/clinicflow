from django.urls import include, path

urlpatterns = [
    path("health/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.clinics.urls")),
    path("api/v1/", include("apps.patients.urls")),
    path("api/v1/", include("apps.encounters.urls")),
]
