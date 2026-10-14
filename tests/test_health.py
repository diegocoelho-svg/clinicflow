from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.urls import reverse
from rest_framework.test import APIClient


def test_liveness_is_public_and_does_not_need_database() -> None:
    # pytest-django prohibits database access without the django_db marker.
    response = APIClient().get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_checks_postgresql() -> None:
    response = APIClient().get(reverse("core:readiness"))

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_database_outage_does_not_expose_details_or_break_liveness() -> None:
    error = OperationalError("sensitive-database-connection-information")
    client = APIClient()

    with patch("apps.core.views.connection.cursor", side_effect=error):
        readiness = client.get(reverse("core:readiness"))
        liveness = client.get(reverse("core:health"))

    assert readiness.status_code == 503
    assert readiness.json() == {"status": "unavailable", "database": "unavailable"}
    assert str(error) not in readiness.content.decode()
    assert liveness.status_code == 200


@pytest.mark.parametrize("endpoint", ["core:health", "core:readiness"])
def test_health_endpoints_reject_mutations(endpoint: str) -> None:
    response = APIClient().post(reverse(endpoint), {}, format="json")

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["core:health", "core:readiness"])
def test_health_endpoints_ignore_invalid_authorization_header(endpoint: str) -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer unknown-token")

    response = client.get(reverse(endpoint))

    assert response.status_code == 200
