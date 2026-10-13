import logging

from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(HealthView):
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            logger.warning("Database readiness check failed", exc_info=True)
            return Response(
                {"status": "unavailable", "database": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ready", "database": "ok"})
