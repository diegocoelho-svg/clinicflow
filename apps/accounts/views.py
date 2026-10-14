from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import CreateAPIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.authentication import BearerTokenAuthentication
from apps.accounts.serializers import CurrentUserSerializer, RegistrationSerializer


@method_decorator(never_cache, name="dispatch")
class RegisterView(CreateAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    serializer_class = RegistrationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"


@method_decorator(never_cache, name="dispatch")
class TokenLoginView(ObtainAuthToken):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


@method_decorator(never_cache, name="dispatch")
class CurrentUserView(APIView):
    def get(self, request: Request) -> Response:
        return Response(CurrentUserSerializer(request.user).data)


@method_decorator(never_cache, name="dispatch")
class LogoutView(APIView):
    authentication_classes = [BearerTokenAuthentication]

    def post(self, request: Request) -> Response:
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
