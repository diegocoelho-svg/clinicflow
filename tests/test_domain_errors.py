import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.core.exceptions import (
    AccessDenied,
    BusinessRuleViolation,
    Conflict,
    ResourceNotFound,
    ServiceUnavailable,
)


@pytest.mark.parametrize(
    "error,status,detail",
    [
        (ResourceNotFound(), 404, {"detail": "Not found."}),
        (Conflict("Already issued."), 409, {"detail": "Already issued."}),
        (AccessDenied("Invalid signature."), 403, {"detail": "Invalid signature."}),
        (ServiceUnavailable("Not configured."), 503, {"detail": "Not configured."}),
        (
            BusinessRuleViolation({"amount": ["Out of range."]}),
            400,
            {"amount": ["Out of range."]},
        ),
        (ValidationError({"name": ["Required."]}), 400, {"name": ["Required."]}),
    ],
)
def test_business_errors_keep_the_public_http_contract(error, status, detail):
    class FailingView(APIView):
        authentication_classes = ()
        permission_classes = (AllowAny,)

        def get(self, request):
            raise error

    response = FailingView.as_view()(APIRequestFactory().get("/"))
    assert response.status_code == status
    assert response.data == detail


def test_unexpected_exceptions_are_not_hidden_as_business_errors():
    class BrokenView(APIView):
        authentication_classes = ()
        permission_classes = (AllowAny,)

        def get(self, request):
            raise RuntimeError("Unexpected failure")

    with pytest.raises(RuntimeError, match="Unexpected failure"):
        BrokenView.as_view()(APIRequestFactory().get("/"))
