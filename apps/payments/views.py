import json
from typing import Any, NoReturn

from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import mixins, status
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clinics.access import ClinicScopedViewSet
from apps.core.api import RequestTooLarge
from apps.payments.models import Payment, PaymentEvent
from apps.payments.serializers import (
    PaymentEventSerializer,
    PaymentNotificationSerializer,
    PaymentSerializer,
)
from apps.payments.services import accept_event
from apps.payments.signatures import MAX_BODY_BYTES, verify_signature


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> NoReturn:
    raise ValueError("Non-finite JSON number")


@method_decorator(never_cache, name="dispatch")
class SimulatedPaymentWebhook(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    parser_classes = ()
    http_method_names = ["post", "options"]

    def post(self, request: Request) -> Response:
        if request.content_type.split(";")[0].strip() != "application/json":
            raise UnsupportedMediaType(request.content_type)
        declared_size = request.META.get("CONTENT_LENGTH", "")
        if declared_size.isdigit() and int(declared_size) > MAX_BODY_BYTES:
            raise RequestTooLarge("Payment notifications cannot exceed 64 KiB.")
        body = request.body
        if len(body) > MAX_BODY_BYTES:
            raise RequestTooLarge("Payment notifications cannot exceed 64 KiB.")
        verify_signature(
            body,
            request.headers.get("X-Webhook-Timestamp", ""),
            request.headers.get("X-Webhook-Signature", ""),
        )
        try:
            data = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ParseError("Invalid JSON payment notification.") from error
        serializer = PaymentNotificationSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        event, created = accept_event(serializer.to_notification())
        return Response(
            PaymentEventSerializer(event).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class ClinicPaymentReadOnlyViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, ClinicScopedViewSet
):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["get", "head", "options"]

    def get_queryset(self) -> QuerySet[Payment | PaymentEvent]:
        return super().get_queryset().filter(clinic_id=self.clinic.id)


class PaymentViewSet(ClinicPaymentReadOnlyViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class PaymentEventViewSet(ClinicPaymentReadOnlyViewSet):
    queryset = PaymentEvent.objects.all()
    serializer_class = PaymentEventSerializer
