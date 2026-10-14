import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

TEST_PASSWORD = "local-test-password-42"


@pytest.fixture
def user(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user(
        username="alex_demo",
        password=TEST_PASSWORD,
        email="alex@example.test",
        first_name="Alex",
        last_name="Demo",
    )


def test_login_creates_token_and_identifies_current_user(user: User) -> None:
    client = APIClient()

    login = client.post(
        reverse("accounts:token-login"),
        {"username": user.username, "password": TEST_PASSWORD},
        format="json",
    )

    assert login.status_code == 200
    assert "no-store" in login["Cache-Control"]
    token = Token.objects.get(user=user)
    assert login.json() == {"token": token.key}

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    current_user = client.get(reverse("accounts:me"))

    assert current_user.status_code == 200
    assert "no-store" in current_user["Cache-Control"]
    assert current_user.json() == {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def test_login_reuses_existing_token(user: User) -> None:
    token = Token.objects.create(user=user)

    response = APIClient().post(
        reverse("accounts:token-login"),
        {"username": user.username, "password": TEST_PASSWORD},
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {"token": token.key}
    assert Token.objects.filter(user=user).count() == 1


@pytest.mark.parametrize("failure", ["unknown_user", "wrong_password", "inactive_user"])
def test_login_rejects_invalid_credentials(user: User, failure: str) -> None:
    username = user.username
    password = TEST_PASSWORD
    if failure == "unknown_user":
        username = "missing_user"
    elif failure == "wrong_password":
        password = "incorrect-test-password"
    else:
        user.is_active = False
        user.save(update_fields=["is_active"])

    response = APIClient().post(
        reverse("accounts:token-login"),
        {"username": username, "password": password},
        format="json",
    )

    assert response.status_code == 400
    assert "no-store" in response["Cache-Control"]
    assert response.json() == {
        "non_field_errors": ["Unable to log in with provided credentials."]
    }
    assert not Token.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [{}, {"username": "alex_demo"}, {"password": TEST_PASSWORD}],
)
def test_login_requires_username_and_password(payload: dict[str, str]) -> None:
    response = APIClient().post(reverse("accounts:token-login"), payload, format="json")

    assert response.status_code == 400
    assert not Token.objects.exists()


@pytest.mark.parametrize("endpoint", ["accounts:me", "accounts:logout"])
@pytest.mark.parametrize("authorization", ["", "Bearer unknown-token"])
def test_protected_endpoints_require_valid_token(
    endpoint: str, authorization: str
) -> None:
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)

    if endpoint == "accounts:me":
        response = client.get(reverse(endpoint))
    else:
        response = client.post(reverse(endpoint))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


def test_session_cookie_does_not_authenticate_current_user(user: User) -> None:
    client = APIClient()
    client.force_login(user)

    response = client.get(reverse("accounts:me"))

    assert response.status_code == 401


def test_inactive_user_cannot_use_existing_token(user: User) -> None:
    token = Token.objects.create(user=user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

    response = client.get(reverse("accounts:me"))

    assert response.status_code == 401


def test_logout_revokes_current_token_and_allows_fresh_login(
    user: User, django_user_model: type[User]
) -> None:
    token = Token.objects.create(user=user)
    old_key = token.key
    other_user = django_user_model.objects.create_user(
        username="other_demo", password=TEST_PASSWORD
    )
    other_token = Token.objects.create(user=other_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_key}")

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 204
    assert response.content == b""
    assert "no-store" in response["Cache-Control"]
    assert not Token.objects.filter(key=old_key).exists()
    assert Token.objects.filter(key=other_token.key).exists()
    assert client.get(reverse("accounts:me")).status_code == 401

    login = client.post(
        reverse("accounts:token-login"),
        {"username": user.username, "password": TEST_PASSWORD},
        format="json",
    )

    assert login.status_code == 200
    assert login.json()["token"] != old_key
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")
    assert client.get(reverse("accounts:me")).status_code == 200

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token.key}")
    assert client.get(reverse("accounts:me")).json()["username"] == other_user.username


def test_logout_cannot_be_triggered_by_get(user: User) -> None:
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405
    assert Token.objects.filter(key=token.key).exists()


def test_login_is_throttled_even_with_spoofed_forwarded_headers() -> None:
    client = APIClient()
    for attempt in range(10):
        response = client.post(
            reverse("accounts:token-login"),
            {},
            format="json",
            HTTP_X_FORWARDED_FOR=f"203.0.113.{attempt + 1}",
        )
        assert response.status_code == 400

    blocked = client.post(
        reverse("accounts:token-login"),
        {},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.200",
    )

    assert blocked.status_code == 429
    assert int(blocked["Retry-After"]) > 0


@pytest.mark.parametrize("endpoint", ["accounts:me", "accounts:logout"])
def test_legacy_token_prefix_is_rejected(endpoint: str, user: User) -> None:
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    if endpoint == "accounts:me":
        response = client.get(reverse(endpoint))
    else:
        response = client.post(reverse(endpoint))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    assert Token.objects.filter(key=token.key).exists()
