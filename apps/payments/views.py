import json
from functools import cached_property

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import APIException, ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clinics.models import ClinicMembership
from apps.payments.models import Payment, PaymentEvent
from apps.payments.serializers import (
    PaymentEventSerializer,
    PaymentNotificationSerializer,
    PaymentSerializer,
)
from apps.payments.services import accept_event
from apps.payments.signatures import MAX_BODY_BYTES, verify_signature


class NotificationTooLarge(APIException):
    status_code = 413
    default_detail = "Payment notifications cannot exceed 64 KiB."


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Non-finite JSON number")


@method_decorator(never_cache, name="dispatch")
class SimulatedPaymentWebhook(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    parser_classes = ()
    http_method_names = ["post", "options"]

    def post(self, request):
        if request.content_type.split(";")[0].strip() != "application/json":
            raise UnsupportedMediaType(request.content_type)
        declared_size = request.META.get("CONTENT_LENGTH", "")
        if declared_size.isdigit() and int(declared_size) > MAX_BODY_BYTES:
            raise NotificationTooLarge()
        body = request.body
        if len(body) > MAX_BODY_BYTES:
            raise NotificationTooLarge()
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
        event, created = accept_event(serializer.validated_data)
        return Response(
            PaymentEventSerializer(event).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


@method_decorator(never_cache, name="dispatch")
class ClinicPaymentReadOnlyViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["get", "head", "options"]

    @cached_property
    def clinic_membership(self):
        return get_object_or_404(
            ClinicMembership, clinic_id=self.kwargs["clinic_id"], user=self.request.user
        )

    def get_queryset(self):
        return super().get_queryset().filter(clinic_id=self.clinic_membership.clinic_id)


class PaymentViewSet(ClinicPaymentReadOnlyViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class PaymentEventViewSet(ClinicPaymentReadOnlyViewSet):
    queryset = PaymentEvent.objects.all()
    serializer_class = PaymentEventSerializer
