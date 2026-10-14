from rest_framework.routers import SimpleRouter

from apps.clinics.views import ClinicViewSet

app_name = "clinics"

router = SimpleRouter()
router.register("clinics", ClinicViewSet, basename="clinic")
urlpatterns = router.urls
