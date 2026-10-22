from django.urls import path

from apps.payments.views import (
    PaymentEventViewSet,
    PaymentViewSet,
    SimulatedPaymentWebhook,
)

app_name = "payments"

urlpatterns = [
    path(
        "payment-webhooks/simulated/",
        SimulatedPaymentWebhook.as_view(),
        name="simulated-webhook",
    ),
    path(
        "clinics/<int:clinic_id>/payments/",
        PaymentViewSet.as_view({"get": "list"}),
        name="payment-list",
    ),
    path(
        "clinics/<int:clinic_id>/payments/<int:pk>/",
        PaymentViewSet.as_view({"get": "retrieve"}),
        name="payment-detail",
    ),
    path(
        "clinics/<int:clinic_id>/payment-events/",
        PaymentEventViewSet.as_view({"get": "list"}),
        name="event-list",
    ),
    path(
        "clinics/<int:clinic_id>/payment-events/<int:pk>/",
        PaymentEventViewSet.as_view({"get": "retrieve"}),
        name="event-detail",
    ),
]
