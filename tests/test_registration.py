import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.serializers import RegistrationSerializer

pytestmark = pytest.mark.django_db

TEST_PASSWORD = "registration-test-phrase-942!"
REQUIRED_FIELDS = ("username", "password", "email", "first_name", "last_name")


@pytest.fixture
def registration_data() -> dict[str, str]:
    return {
        "username": "registration_demo",
        "password": TEST_PASSWORD,
        "email": "demo@example.test",
        "first_name": "Alex",
        "last_name": "Demo",
    }


def test_register_creates_normal_user_and_can_sign_in(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer old-token")
    response = client.post(
        reverse("accounts:register"), registration_data, format="json"
    )

    assert response.status_code == 201
    assert "no-store" in response["Cache-Control"]
    user = django_user_model.objects.get(username=registration_data["username"])
    assert response.json() == {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    assert user.password != TEST_PASSWORD
    assert user.check_password(TEST_PASSWORD)
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser
    assert not Token.objects.filter(user=user).exists()

    login = client.post(
        reverse("accounts:token-login"),
        {"username": user.username, "password": TEST_PASSWORD},
        format="json",
    )
    assert login.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")
    assert client.get(reverse("accounts:me")).json() == response.json()


def test_register_cannot_assign_privileges(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    response = APIClient().post(
        reverse("accounts:register"),
        {
            **registration_data,
            "id": 0,
            "is_staff": True,
            "is_superuser": True,
            "is_active": False,
            "groups": [1],
            "user_permissions": [1],
        },
        format="json",
    )

    assert response.status_code == 201
    user = django_user_model.objects.get(username=registration_data["username"])
    assert user.pk != 0
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser
    assert not user.groups.exists()
    assert not user.user_permissions.exists()


@pytest.mark.parametrize(
    "password", ["short", "1234567891011", "password", "fresh_user"]
)
def test_register_rejects_weak_passwords(
    password: str,
    django_user_model: type[User],
    registration_data: dict[str, str],
) -> None:
    response = APIClient().post(
        reverse("accounts:register"),
        {**registration_data, "username": "fresh_user", "password": password},
        format="json",
    )

    assert response.status_code == 400
    assert "password" in response.json()
    assert "no-store" in response["Cache-Control"]
    assert not django_user_model.objects.exists()


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_register_requires_all_identity_fields(
    field: str, django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    registration_data.pop(field)

    response = APIClient().post(
        reverse("accounts:register"), registration_data, format="json"
    )

    assert response.status_code == 400
    assert field in response.json()
    assert not django_user_model.objects.exists()


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
@pytest.mark.parametrize("value", ["", "    ", None])
def test_register_rejects_empty_required_fields(
    field: str,
    value: str | None,
    django_user_model: type[User],
    registration_data: dict[str, str],
) -> None:
    response = APIClient().post(
        reverse("accounts:register"),
        {**registration_data, field: value},
        format="json",
    )

    assert response.status_code == 400
    assert field in response.json()
    assert not django_user_model.objects.exists()


def test_register_rejects_invalid_email(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    response = APIClient().post(
        reverse("accounts:register"),
        {**registration_data, "email": "invalid-email"},
        format="json",
    )

    assert response.status_code == 400
    assert "email" in response.json()
    assert not django_user_model.objects.exists()


def test_register_rejects_duplicate_username(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    django_user_model.objects.create_user(**registration_data)

    response = APIClient().post(
        reverse("accounts:register"), registration_data, format="json"
    )

    assert response.status_code == 400
    assert "username" in response.json()
    assert django_user_model.objects.count() == 1


def test_username_collision_after_validation_returns_field_error(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    serializer = RegistrationSerializer(data=registration_data)
    assert serializer.is_valid(), serializer.errors
    django_user_model.objects.create_user(**registration_data)

    with pytest.raises(serializers.ValidationError) as captured:
        serializer.save()

    assert "username" in captured.value.detail
    assert (
        django_user_model.objects.filter(username=registration_data["username"]).count()
        == 1
    )


def test_registration_preserves_password_whitespace(
    django_user_model: type[User], registration_data: dict[str, str]
) -> None:
    password = "  local-test-phrase-942!  "
    client = APIClient()
    registration = client.post(
        reverse("accounts:register"),
        {**registration_data, "password": password},
        format="json",
    )

    assert registration.status_code == 201
    user = django_user_model.objects.get(username=registration_data["username"])
    assert user.check_password(password)
    assert not user.check_password(password.strip())
    login = client.post(
        reverse("accounts:token-login"),
        {"username": user.username, "password": password},
        format="json",
    )
    assert login.status_code == 200


def test_registration_is_throttled_by_connection_ip() -> None:
    client = APIClient()
    for attempt in range(10):
        response = client.post(
            reverse("accounts:register"),
            {},
            format="json",
            HTTP_X_FORWARDED_FOR=f"203.0.113.{attempt + 1}",
        )
        assert response.status_code == 400

    blocked = client.post(
        reverse("accounts:register"),
        {},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.200",
    )
    assert blocked.status_code == 429
    assert int(blocked["Retry-After"]) > 0


def test_registration_rejects_get(django_user_model: type[User]) -> None:
    response = APIClient().get(reverse("accounts:register"))

    assert response.status_code == 405
    assert not django_user_model.objects.exists()
