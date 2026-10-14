from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicMembership

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user(
        username="clinic_owner",
        email="owner@example.test",
        first_name="Alex",
        last_name="Demo",
    )


@pytest.fixture
def outsider(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user(
        username="clinic_outsider",
        email="outsider@example.test",
        first_name="Sam",
        last_name="Demo",
    )


def authenticated_client(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def owner_client(owner: User) -> APIClient:
    return authenticated_client(owner)


@pytest.fixture
def clinic(owner: User) -> Clinic:
    clinic = Clinic.objects.create(name="Demo Clinic")
    ClinicMembership.objects.create(
        clinic=clinic, user=owner, role=ClinicMembership.Role.OWNER
    )
    return clinic


def test_create_clinic_assigns_authenticated_owner(
    owner: User, outsider: User, owner_client: APIClient
) -> None:
    response = owner_client.post(
        reverse("clinics:clinic-list"),
        {
            "name": "  Demo Clinic  ",
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
            "owner": outsider.pk,
            "user": outsider.pk,
            "role": "MEMBER",
            "memberships": [{"user": outsider.pk, "role": "OWNER"}],
        },
        format="json",
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "name", "created_at", "updated_at"}
    assert data["id"] != 0
    assert data["name"] == "Demo Clinic"
    assert data["created_at"] != "2000-01-01T00:00:00Z"
    assert data["updated_at"] != "2000-01-01T00:00:00Z"
    membership = ClinicMembership.objects.get(clinic_id=data["id"])
    assert membership.user == owner
    assert membership.role == ClinicMembership.Role.OWNER
    assert ClinicMembership.objects.count() == 1
    assert (
        owner_client.get(reverse("clinics:clinic-detail", args=[data["id"]])).json()
        == data
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": ""},
        {"name": "   "},
        {"name": "\t\n"},
        {"name": "x" * 256},
    ],
)
def test_create_rejects_invalid_name(
    owner_client: APIClient, payload: dict[str, str | None]
) -> None:
    response = owner_client.post(reverse("clinics:clinic-list"), payload, format="json")

    assert response.status_code == 400
    assert "name" in response.json()
    assert not Clinic.objects.exists()
    assert not ClinicMembership.objects.exists()


def test_failed_membership_creation_rolls_back_clinic(owner_client: APIClient) -> None:
    with (
        patch.object(
            ClinicMembership.objects,
            "create",
            side_effect=IntegrityError("Simulated membership write failure"),
        ),
        pytest.raises(IntegrityError),
    ):
        owner_client.post(
            reverse("clinics:clinic-list"), {"name": "Rollback Clinic"}, format="json"
        )

    assert not Clinic.objects.exists()
    assert not ClinicMembership.objects.exists()


def test_list_returns_only_memberships_and_cannot_be_overridden(
    owner: User, outsider: User, owner_client: APIClient, clinic: Clinic
) -> None:
    foreign = Clinic.objects.create(name="Other Clinic")
    ClinicMembership.objects.create(
        clinic=foreign, user=outsider, role=ClinicMembership.Role.OWNER
    )
    shared = Clinic.objects.create(name="Shared Clinic")
    ClinicMembership.objects.create(
        clinic=shared, user=outsider, role=ClinicMembership.Role.OWNER
    )
    ClinicMembership.objects.create(clinic=shared, user=owner)

    response = owner_client.get(
        reverse("clinics:clinic-list"),
        {"user": outsider.pk, "clinic": foreign.pk, "role": "OWNER"},
        HTTP_X_CLINIC_ID=str(foreign.pk),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [clinic.pk, shared.pk]
    other_response = authenticated_client(outsider).get(reverse("clinics:clinic-list"))
    assert [item["id"] for item in other_response.json()] == [foreign.pk, shared.pk]


def test_user_without_memberships_gets_empty_list(
    outsider: User, clinic: Clinic
) -> None:
    response = authenticated_client(outsider).get(reverse("clinics:clinic-list"))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("method", ["get", "patch"])
def test_unrelated_user_cannot_access_clinic(
    outsider: User, clinic: Clinic, method: str
) -> None:
    client = authenticated_client(outsider)
    response = getattr(client, method)(
        reverse("clinics:clinic-detail", args=[clinic.pk]),
        {"name": "Unauthorized change"},
        format="json",
    )

    assert response.status_code == 404
    clinic.refresh_from_db()
    assert clinic.name == "Demo Clinic"


def test_superuser_without_membership_has_no_cross_clinic_access(
    outsider: User, clinic: Clinic
) -> None:
    outsider.is_staff = True
    outsider.is_superuser = True
    outsider.save(update_fields=["is_staff", "is_superuser"])
    client = authenticated_client(outsider)

    assert client.get(reverse("clinics:clinic-list")).json() == []
    assert (
        client.get(reverse("clinics:clinic-detail", args=[clinic.pk])).status_code
        == 404
    )
    assert (
        client.patch(
            reverse("clinics:clinic-detail", args=[clinic.pk]),
            {"name": "Unauthorized"},
            format="json",
        ).status_code
        == 404
    )


def test_member_can_read_but_cannot_edit_or_self_promote(
    outsider: User, clinic: Clinic
) -> None:
    membership = ClinicMembership.objects.create(clinic=clinic, user=outsider)
    client = authenticated_client(outsider)
    endpoint = reverse("clinics:clinic-detail", args=[clinic.pk])

    assert client.get(endpoint).status_code == 200
    response = client.patch(
        endpoint, {"name": "Unauthorized", "role": "OWNER"}, format="json"
    )

    assert response.status_code == 403
    membership.refresh_from_db()
    clinic.refresh_from_db()
    assert membership.role == ClinicMembership.Role.MEMBER
    assert clinic.name == "Demo Clinic"


def test_owner_can_edit_name_but_cannot_change_identity_or_memberships(
    owner: User, outsider: User, owner_client: APIClient, clinic: Clinic
) -> None:
    created_at = clinic.created_at
    previous_updated_at = clinic.updated_at
    response = owner_client.patch(
        reverse("clinics:clinic-detail", args=[clinic.pk]),
        {
            "name": " Updated Clinic ",
            "id": clinic.pk + 100,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
            "owner": outsider.pk,
            "role": "MEMBER",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["id"] == clinic.pk
    clinic.refresh_from_db()
    assert clinic.name == "Updated Clinic"
    assert clinic.created_at == created_at
    assert clinic.updated_at > previous_updated_at
    membership = ClinicMembership.objects.get(clinic=clinic)
    assert membership.user == owner
    assert membership.role == ClinicMembership.Role.OWNER


@pytest.mark.parametrize("value", [None, "", "   ", "x" * 256])
def test_patch_rejects_invalid_name(
    owner_client: APIClient, clinic: Clinic, value: str | None
) -> None:
    response = owner_client.patch(
        reverse("clinics:clinic-detail", args=[clinic.pk]),
        {"name": value},
        format="json",
    )

    assert response.status_code == 400
    clinic.refresh_from_db()
    assert clinic.name == "Demo Clinic"


def test_membership_removal_revokes_visibility_without_changing_token(
    outsider: User, clinic: Clinic
) -> None:
    membership = ClinicMembership.objects.create(clinic=clinic, user=outsider)
    client = authenticated_client(outsider)
    endpoint = reverse("clinics:clinic-detail", args=[clinic.pk])
    assert client.get(endpoint).status_code == 200

    membership.delete()

    assert client.get(endpoint).status_code == 404
    assert client.get(reverse("clinics:clinic-list")).json() == []
    assert client.get(reverse("accounts:me")).status_code == 200


@pytest.mark.parametrize("authorization", ["", "Bearer unknown-token"])
@pytest.mark.parametrize("operation", ["list", "create", "retrieve", "patch"])
def test_clinic_endpoints_require_authentication(
    clinic: Clinic, authorization: str, operation: str
) -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=authorization)
    if operation == "list":
        response = client.get(reverse("clinics:clinic-list"))
    elif operation == "create":
        response = client.post(
            reverse("clinics:clinic-list"), {"name": "Unauthorized"}, format="json"
        )
    else:
        method = "get" if operation == "retrieve" else "patch"
        response = getattr(client, method)(
            reverse("clinics:clinic-detail", args=[clinic.pk]),
            {"name": "Unauthorized"},
            format="json",
        )

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    clinic.refresh_from_db()
    assert clinic.name == "Demo Clinic"
    assert Clinic.objects.count() == 1


@pytest.mark.parametrize("method", ["put", "delete"])
def test_unsupported_mutations_are_rejected(
    owner_client: APIClient, clinic: Clinic, method: str
) -> None:
    response = getattr(owner_client, method)(
        reverse("clinics:clinic-detail", args=[clinic.pk]),
        {"name": "Unsupported"},
        format="json",
    )

    assert response.status_code == 405
    clinic.refresh_from_db()
    assert clinic.name == "Demo Clinic"
    assert ClinicMembership.objects.filter(clinic=clinic).exists()


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_database_rejects_blank_clinic_name(name: str) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Clinic.objects.create(name=name)


def test_database_rejects_duplicate_membership(owner: User, clinic: Clinic) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicMembership.objects.create(clinic=clinic, user=owner)


def test_database_rejects_unknown_membership_role(
    outsider: User, clinic: Clinic
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicMembership.objects.create(clinic=clinic, user=outsider, role="ADMIN")


def test_user_with_membership_is_protected_from_deletion(
    owner: User, clinic: Clinic
) -> None:
    with pytest.raises(ProtectedError):
        owner.delete()

    assert ClinicMembership.objects.filter(clinic=clinic, user=owner).exists()
