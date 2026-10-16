from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicMembership
from apps.procedures.models import Procedure

pytestmark = pytest.mark.django_db


def authenticated_client(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Procedure Clinic")
    for username, role in [
        ("procedure_owner", ClinicMembership.Role.OWNER),
        ("procedure_member", ClinicMembership.Role.MEMBER),
    ]:
        user = django_user_model.objects.create_user(username=username)
        ClinicMembership.objects.create(clinic=clinic, user=user, role=role)
    return clinic


@pytest.fixture
def owner_client(clinic: Clinic) -> APIClient:
    return authenticated_client(clinic.memberships.get(role="OWNER").user)


@pytest.fixture
def member_client(clinic: Clinic) -> APIClient:
    return authenticated_client(clinic.memberships.get(role="MEMBER").user)


@pytest.fixture(params=[ClinicMembership.Role.OWNER, ClinicMembership.Role.MEMBER])
def reader_client(clinic: Clinic, request: pytest.FixtureRequest) -> APIClient:
    return authenticated_client(clinic.memberships.get(role=request.param).user)


@pytest.fixture
def foreign_clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Foreign Procedure Clinic")
    user = django_user_model.objects.create_user(username="procedure_outsider")
    ClinicMembership.objects.create(
        clinic=clinic, user=user, role=ClinicMembership.Role.OWNER
    )
    return clinic


@pytest.fixture
def procedure(clinic: Clinic) -> Procedure:
    return Procedure.objects.create(
        clinic=clinic, name="Consultation", unit_price=Decimal("123.45")
    )


def list_url(clinic: Clinic) -> str:
    return reverse("procedures:procedure-list", args=[clinic.pk])


def detail_url(clinic: Clinic, procedure: Procedure) -> str:
    return reverse("procedures:procedure-detail", args=[clinic.pk, procedure.pk])


def test_owner_can_create_procedure_with_decimal_price(
    clinic: Clinic, owner_client: APIClient, foreign_clinic: Clinic
) -> None:
    response = owner_client.post(
        list_url(clinic),
        {
            "name": "  Consultation  ",
            "unit_price": "0.10",
            "clinic": foreign_clinic.pk,
            "clinic_id": foreign_clinic.pk,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
            "role": "MEMBER",
        },
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "clinic",
        "name",
        "unit_price",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert data["id"] != 0
    assert data["clinic"] == clinic.pk
    assert data["name"] == "Consultation"
    assert data["unit_price"] == "0.10"
    assert data["is_active"] is True
    assert data["created_at"] != "2000-01-01T00:00:00Z"
    assert data["updated_at"] != "2000-01-01T00:00:00Z"
    saved = Procedure.objects.get(pk=data["id"])
    assert isinstance(saved.unit_price, Decimal)
    assert saved.unit_price == Decimal("0.10")
    assert not foreign_clinic.procedures.exists()


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (0, "0.00"),
        ("0.00", "0.00"),
        ("0.29", "0.29"),
        ("1", "1.00"),
        ("1234.56", "1234.56"),
        ("9999999999.99", "9999999999.99"),
    ],
)
def test_zero_and_valid_decimal_prices_are_preserved(
    clinic: Clinic, owner_client: APIClient, price, expected: str
) -> None:
    response = owner_client.post(
        list_url(clinic), {"name": "Procedure", "unit_price": price}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["unit_price"] == expected
    assert Procedure.objects.get(pk=response.json()["id"]).unit_price == Decimal(
        expected
    )


@pytest.mark.parametrize(
    ("field", "value", "omit"),
    [
        ("name", None, True),
        ("name", None, False),
        ("name", "", False),
        ("name", " \t\n", False),
        ("name", "x" * 256, False),
        ("unit_price", None, True),
        ("unit_price", None, False),
        ("unit_price", "", False),
        ("unit_price", "invalid", False),
        ("unit_price", "-0.01", False),
        ("unit_price", "-10.00", False),
        ("unit_price", "1.001", False),
        ("unit_price", "10000000000.00", False),
        ("unit_price", "NaN", False),
        ("unit_price", "Infinity", False),
        ("is_active", None, False),
        ("is_active", "invalid", False),
    ],
)
def test_creation_rejects_invalid_fields(
    clinic: Clinic, owner_client: APIClient, field: str, value, omit: bool
) -> None:
    payload = {"name": "Consultation", "unit_price": "12.34"}
    if omit:
        payload.pop(field)
    else:
        payload[field] = value
    response = owner_client.post(list_url(clinic), payload, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert not Procedure.objects.exists()


def test_owner_can_create_inactive_procedure(
    clinic: Clinic, owner_client: APIClient
) -> None:
    response = owner_client.post(
        list_url(clinic),
        {"name": "Inactive", "unit_price": "0.00", "is_active": False},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is False


def test_owner_and_member_can_read_active_and_inactive_catalog(
    clinic: Clinic,
    reader_client: APIClient,
    procedure: Procedure,
    foreign_clinic: Clinic,
) -> None:
    inactive = Procedure.objects.create(
        clinic=clinic, name="Inactive", unit_price=Decimal("0.00"), is_active=False
    )
    Procedure.objects.create(
        clinic=foreign_clinic, name="Foreign", unit_price=Decimal("9.99")
    )
    response = reader_client.get(
        list_url(clinic),
        {"clinic": foreign_clinic.pk},
        HTTP_X_CLINIC_ID=str(foreign_clinic.pk),
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [procedure.pk, inactive.pk]
    for item in [procedure, inactive]:
        detail = reader_client.get(detail_url(clinic, item))
        assert detail.status_code == 200
        assert detail.json()["id"] == item.pk
        assert detail.json()["is_active"] is item.is_active


def test_accessible_clinic_without_procedures_returns_empty_list(
    clinic: Clinic, reader_client: APIClient
) -> None:
    response = reader_client.get(list_url(clinic))
    assert response.status_code == 200
    assert response.json() == []


def test_owner_can_edit_and_deactivate_without_transferring_clinic(
    clinic: Clinic,
    owner_client: APIClient,
    procedure: Procedure,
    foreign_clinic: Clinic,
) -> None:
    before = Procedure.objects.get(pk=procedure.pk)
    response = owner_client.patch(
        detail_url(clinic, procedure),
        {
            "name": "  Updated procedure  ",
            "unit_price": "0.00",
            "is_active": False,
            "clinic": foreign_clinic.pk,
            "clinic_id": foreign_clinic.pk,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    procedure.refresh_from_db()
    assert procedure.name == "Updated procedure"
    assert procedure.unit_price == Decimal("0.00")
    assert procedure.is_active is False
    assert procedure.clinic_id == clinic.pk
    assert procedure.created_at == before.created_at
    assert procedure.updated_at > before.updated_at
    assert response.json()["id"] == procedure.pk
    assert response.json()["unit_price"] == "0.00"


def test_owner_can_reactivate_procedure(
    clinic: Clinic, owner_client: APIClient, procedure: Procedure
) -> None:
    procedure.is_active = False
    procedure.save()
    response = owner_client.patch(
        detail_url(clinic, procedure), {"is_active": True}, format="json"
    )
    assert response.status_code == 200
    procedure.refresh_from_db()
    assert procedure.is_active is True


def test_partial_update_retains_price_and_active_flag(
    clinic: Clinic, owner_client: APIClient, procedure: Procedure
) -> None:
    response = owner_client.patch(
        detail_url(clinic, procedure), {"name": "Renamed"}, format="json"
    )
    assert response.status_code == 200
    procedure.refresh_from_db()
    assert procedure.unit_price == Decimal("123.45")
    assert procedure.is_active is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", " \t\n"),
        ("name", None),
        ("name", "x" * 256),
        ("unit_price", None),
        ("unit_price", ""),
        ("unit_price", "-0.01"),
        ("unit_price", "1.001"),
        ("unit_price", "10000000000.00"),
        ("unit_price", "NaN"),
        ("unit_price", "Infinity"),
        ("is_active", None),
        ("is_active", "invalid"),
    ],
)
def test_invalid_patch_does_not_modify_procedure(
    clinic: Clinic, owner_client: APIClient, procedure: Procedure, field: str, value
) -> None:
    before = Procedure.objects.values().get(pk=procedure.pk)
    payload = {"name": "Should not persist", field: value}
    response = owner_client.patch(detail_url(clinic, procedure), payload, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert Procedure.objects.values().get(pk=procedure.pk) == before


@pytest.mark.parametrize("payload", [{}, {"name": "Forbidden", "unit_price": "0.00"}])
def test_member_cannot_create_procedures(
    clinic: Clinic, member_client: APIClient, payload: dict
) -> None:
    response = member_client.post(list_url(clinic), payload, format="json")
    assert response.status_code == 403
    assert not Procedure.objects.exists()


@pytest.mark.parametrize(
    "payload", [{}, {"name": "Forbidden"}, {"unit_price": "0.00"}, {"is_active": False}]
)
def test_member_cannot_edit_procedures(
    clinic: Clinic, member_client: APIClient, procedure: Procedure, payload: dict
) -> None:
    before = Procedure.objects.values().get(pk=procedure.pk)
    response = member_client.patch(
        detail_url(clinic, procedure), payload, format="json"
    )
    assert response.status_code == 403
    assert Procedure.objects.values().get(pk=procedure.pk) == before


@pytest.mark.parametrize("method", ["list", "create", "retrieve", "patch"])
def test_unrelated_user_cannot_access_procedures(
    clinic: Clinic, procedure: Procedure, foreign_clinic: Clinic, method: str
) -> None:
    client = authenticated_client(foreign_clinic.memberships.get().user)
    if method == "list":
        response = client.get(list_url(clinic))
    elif method == "create":
        response = client.post(list_url(clinic), {}, format="json")
    elif method == "retrieve":
        response = client.get(detail_url(clinic, procedure))
    else:
        response = client.patch(
            detail_url(clinic, procedure), {"name": "Forbidden"}, format="json"
        )
    assert response.status_code == 404
    procedure.refresh_from_db()
    assert procedure.name == "Consultation"
    assert Procedure.objects.count() == 1


@pytest.mark.parametrize("method", ["get", "patch"])
def test_procedure_must_belong_to_url_clinic_even_with_both_owner_memberships(
    clinic: Clinic,
    owner_client: APIClient,
    procedure: Procedure,
    foreign_clinic: Clinic,
    method: str,
) -> None:
    ClinicMembership.objects.create(
        clinic=foreign_clinic,
        user=clinic.memberships.get(role="OWNER").user,
        role="OWNER",
    )
    response = getattr(owner_client, method)(
        detail_url(foreign_clinic, procedure), {"name": "Forbidden"}, format="json"
    )
    assert response.status_code == 404
    procedure.refresh_from_db()
    assert procedure.clinic_id == clinic.pk
    assert procedure.name == "Consultation"


def test_nonexistent_clinic_and_procedure_return_404(
    clinic: Clinic, owner_client: APIClient
) -> None:
    assert (
        owner_client.get(
            reverse("procedures:procedure-list", args=[999999])
        ).status_code
        == 404
    )
    assert (
        owner_client.get(
            reverse("procedures:procedure-detail", args=[clinic.pk, 999999])
        ).status_code
        == 404
    )


@pytest.mark.parametrize("is_superuser", [False, True])
def test_administrative_flags_do_not_grant_clinic_access(
    clinic: Clinic, django_user_model: type[User], is_superuser: bool
) -> None:
    user = django_user_model.objects.create_user(
        username="unrelated_procedure_admin", is_staff=True, is_superuser=is_superuser
    )
    assert authenticated_client(user).get(list_url(clinic)).status_code == 404


@pytest.mark.parametrize("role", ["OWNER", "MEMBER"])
def test_removed_membership_revokes_procedure_access(
    clinic: Clinic, procedure: Procedure, role: str
) -> None:
    membership = clinic.memberships.get(role=role)
    client = authenticated_client(membership.user)
    assert client.get(detail_url(clinic, procedure)).status_code == 200
    membership.delete()
    assert client.get(list_url(clinic)).status_code == 404
    assert client.get(detail_url(clinic, procedure)).status_code == 404
    assert client.post(list_url(clinic), {}, format="json").status_code == 404
    assert (
        client.patch(
            detail_url(clinic, procedure), {"name": "Forbidden"}, format="json"
        ).status_code
        == 404
    )
    assert client.get(reverse("accounts:me")).status_code == 200


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Token invalid"])
def test_bearer_authentication_is_required(
    clinic: Clinic, procedure: Procedure, authorization: str | None
) -> None:
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)
    responses = [
        client.get(list_url(clinic)),
        client.post(list_url(clinic), {}, format="json"),
        client.get(detail_url(clinic, procedure)),
        client.patch(detail_url(clinic, procedure), {}, format="json"),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response["WWW-Authenticate"] == "Bearer" for response in responses)


@pytest.mark.parametrize("method", ["put", "delete"])
def test_unsupported_methods_do_not_modify_procedure(
    clinic: Clinic, reader_client: APIClient, procedure: Procedure, method: str
) -> None:
    response = getattr(reader_client, method)(
        detail_url(clinic, procedure), {"name": "Forbidden"}, format="json"
    )
    assert response.status_code == 405
    procedure.refresh_from_db()
    assert procedure.name == "Consultation"


def test_head_and_options_are_available(
    clinic: Clinic, reader_client: APIClient, procedure: Procedure
) -> None:
    assert reader_client.head(list_url(clinic)).status_code == 200
    assert reader_client.head(detail_url(clinic, procedure)).status_code == 200
    assert reader_client.options(list_url(clinic)).status_code == 200


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_database_rejects_blank_name(clinic: Clinic, name: str) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Procedure.objects.create(clinic=clinic, name=name, unit_price=Decimal("0.00"))
    assert not Procedure.objects.exists()


@pytest.mark.parametrize("price", [Decimal("-0.01"), Decimal("-123.45")])
def test_database_rejects_negative_price(clinic: Clinic, price: Decimal) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Procedure.objects.create(clinic=clinic, name="Negative", unit_price=price)
    assert not Procedure.objects.exists()


def test_database_requires_price(clinic: Clinic) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Procedure.objects.create(clinic=clinic, name="Missing price")
    assert not Procedure.objects.exists()


def test_database_rejects_nan_price_on_direct_sql(clinic: Clinic) -> None:
    with (
        pytest.raises(IntegrityError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO procedures_procedure "
            "(clinic_id, name, unit_price, is_active, created_at, updated_at) "
            "VALUES (%s, %s, 'NaN'::numeric, true, now(), now())",
            [clinic.pk, "Invalid price"],
        )
    assert not Procedure.objects.exists()


def test_procedure_protects_clinic_from_orm_deletion(
    clinic: Clinic, procedure: Procedure
) -> None:
    with pytest.raises(ProtectedError):
        clinic.delete()
    assert Clinic.objects.filter(pk=clinic.pk).exists()
    assert Procedure.objects.filter(pk=procedure.pk).exists()
    assert clinic.memberships.count() == 2
