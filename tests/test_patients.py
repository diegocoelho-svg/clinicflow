from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicMembership
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


def authenticated_client(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Patient Clinic")
    for username, role in [
        ("patient_owner", ClinicMembership.Role.OWNER),
        ("patient_member", ClinicMembership.Role.MEMBER),
    ]:
        user = django_user_model.objects.create_user(username=username)
        ClinicMembership.objects.create(clinic=clinic, user=user, role=role)
    return clinic


@pytest.fixture(params=[ClinicMembership.Role.OWNER, ClinicMembership.Role.MEMBER])
def clinic_client(clinic: Clinic, request: pytest.FixtureRequest) -> APIClient:
    return authenticated_client(clinic.memberships.get(role=request.param).user)


@pytest.fixture
def foreign_clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Foreign Patient Clinic")
    user = django_user_model.objects.create_user(username="patient_outsider")
    ClinicMembership.objects.create(
        clinic=clinic, user=user, role=ClinicMembership.Role.OWNER
    )
    return clinic


@pytest.fixture
def patient(clinic: Clinic) -> Patient:
    return Patient.objects.create(
        clinic=clinic,
        full_name="Alex Patient",
        birth_date="1990-05-12",
        email="alex@example.test",
        phone="+55 (11) 99999-0000",
    )


def list_url(clinic: Clinic) -> str:
    return reverse("patients:patient-list", args=[clinic.pk])


def detail_url(clinic: Clinic, patient: Patient) -> str:
    return reverse("patients:patient-detail", args=[clinic.pk, patient.pk])


def test_owner_and_member_can_create_patient(
    clinic: Clinic, clinic_client: APIClient, foreign_clinic: Clinic
) -> None:
    response = clinic_client.post(
        list_url(clinic),
        {
            "full_name": "  Taylor Patient  ",
            "birth_date": "1995-06-15",
            "clinic": foreign_clinic.pk,
            "clinic_id": foreign_clinic.pk,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "clinic",
        "full_name",
        "birth_date",
        "email",
        "phone",
        "created_at",
        "updated_at",
    }
    assert data["id"] != 0
    assert data["clinic"] == clinic.pk
    assert data["full_name"] == "Taylor Patient"
    assert data["birth_date"] == "1995-06-15"
    assert data["email"] == data["phone"] == ""
    assert data["created_at"] != "2000-01-01T00:00:00Z"
    assert data["updated_at"] != "2000-01-01T00:00:00Z"
    saved = Patient.objects.get(pk=data["id"])
    assert saved.clinic_id == clinic.pk
    assert not foreign_clinic.patients.exists()


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"birth_date": "1990-05-12"}, "full_name"),
        ({"full_name": None, "birth_date": "1990-05-12"}, "full_name"),
        ({"full_name": "", "birth_date": "1990-05-12"}, "full_name"),
        ({"full_name": " \t\n", "birth_date": "1990-05-12"}, "full_name"),
        ({"full_name": "x" * 256, "birth_date": "1990-05-12"}, "full_name"),
        ({"full_name": "Alex Patient"}, "birth_date"),
        ({"full_name": "Alex Patient", "birth_date": None}, "birth_date"),
        ({"full_name": "Alex Patient", "birth_date": ""}, "birth_date"),
        ({"full_name": "Alex Patient", "birth_date": "invalid"}, "birth_date"),
        ({"full_name": "Alex Patient", "birth_date": "2001-02-29"}, "birth_date"),
    ],
)
def test_creation_requires_valid_name_and_birth_date(
    clinic: Clinic, payload: dict, field: str
) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    response = client.post(list_url(clinic), payload, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert not Patient.objects.exists()


def test_creation_rejects_future_birth_date(clinic: Clinic) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    response = client.post(
        list_url(clinic),
        {
            "full_name": "Future Patient",
            "birth_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 400
    assert "birth_date" in response.json()
    assert not Patient.objects.exists()


def test_creation_accepts_today_as_birth_date(clinic: Clinic) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    response = client.post(
        list_url(clinic),
        {
            "full_name": "Newborn Patient",
            "birth_date": timezone.localdate().isoformat(),
        },
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("field", "value"),
    [("email", "not-an-email"), ("email", None), ("phone", "x" * 33), ("phone", None)],
)
def test_creation_validates_optional_contacts(
    clinic: Clinic, field: str, value
) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    response = client.post(
        list_url(clinic),
        {"full_name": "Alex Patient", "birth_date": "1990-05-12", field: value},
        format="json",
    )
    assert response.status_code == 400
    assert field in response.json()
    assert not Patient.objects.exists()


def test_listing_is_scoped_to_url_clinic(
    clinic: Clinic, clinic_client: APIClient, foreign_clinic: Clinic, patient: Patient
) -> None:
    foreign_patient = Patient.objects.create(
        clinic=foreign_clinic, full_name="Foreign Patient", birth_date="1980-01-01"
    )
    response = clinic_client.get(
        list_url(clinic),
        {"clinic": foreign_clinic.pk, "clinic_id": foreign_clinic.pk},
        HTTP_X_CLINIC_ID=str(foreign_clinic.pk),
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [patient.pk]
    assert foreign_patient.pk != patient.pk


def test_accessible_clinic_without_patients_returns_empty_list(
    clinic: Clinic, clinic_client: APIClient
) -> None:
    response = clinic_client.get(list_url(clinic))
    assert response.status_code == 200
    assert response.json() == []


def test_owner_and_member_can_retrieve_patient(
    clinic: Clinic, clinic_client: APIClient, patient: Patient
) -> None:
    response = clinic_client.get(detail_url(clinic, patient))
    assert response.status_code == 200
    assert response.json()["id"] == patient.pk
    assert response.json()["birth_date"] == "1990-05-12"


def test_owner_and_member_can_edit_patient_without_transferring_clinic(
    clinic: Clinic, clinic_client: APIClient, patient: Patient, foreign_clinic: Clinic
) -> None:
    before = Patient.objects.get(pk=patient.pk)
    response = clinic_client.patch(
        detail_url(clinic, patient),
        {
            "full_name": "  Updated Patient  ",
            "birth_date": "1991-07-20",
            "email": "updated@example.test",
            "phone": "(11) 1234-5678",
            "clinic": foreign_clinic.pk,
            "clinic_id": foreign_clinic.pk,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.clinic_id == clinic.pk
    assert patient.full_name == "Updated Patient"
    assert patient.birth_date.isoformat() == "1991-07-20"
    assert patient.email == "updated@example.test"
    assert patient.phone == "(11) 1234-5678"
    assert patient.created_at == before.created_at
    assert patient.updated_at > before.updated_at
    assert response.json()["id"] == patient.pk


def test_partial_update_preserves_required_birth_date_and_can_clear_contacts(
    clinic: Clinic, clinic_client: APIClient, patient: Patient
) -> None:
    response = clinic_client.patch(
        detail_url(clinic, patient), {"email": "", "phone": ""}, format="json"
    )
    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.birth_date.isoformat() == "1990-05-12"
    assert patient.full_name == "Alex Patient"
    assert patient.email == patient.phone == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_name", " \t\n"),
        ("full_name", None),
        ("full_name", "x" * 256),
        ("birth_date", None),
        ("birth_date", ""),
        ("birth_date", "invalid"),
        ("email", "invalid"),
        ("phone", "x" * 33),
    ],
)
def test_invalid_patch_does_not_modify_patient(
    clinic: Clinic, patient: Patient, field: str, value
) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    before = Patient.objects.values().get(pk=patient.pk)
    response = client.patch(detail_url(clinic, patient), {field: value}, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert Patient.objects.values().get(pk=patient.pk) == before


def test_patch_rejects_future_birth_date(clinic: Clinic, patient: Patient) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    response = client.patch(
        detail_url(clinic, patient),
        {"birth_date": (timezone.localdate() + timedelta(days=1)).isoformat()},
        format="json",
    )
    assert response.status_code == 400
    patient.refresh_from_db()
    assert patient.birth_date.isoformat() == "1990-05-12"


@pytest.mark.parametrize("method", ["get", "post", "retrieve", "patch"])
def test_unrelated_user_cannot_access_clinic_patients(
    clinic: Clinic, patient: Patient, foreign_clinic: Clinic, method: str
) -> None:
    client = authenticated_client(foreign_clinic.memberships.get().user)
    if method == "get":
        response = client.get(list_url(clinic))
    elif method == "post":
        response = client.post(list_url(clinic), {}, format="json")
    elif method == "retrieve":
        response = client.get(detail_url(clinic, patient))
    else:
        response = client.patch(
            detail_url(clinic, patient), {"full_name": "Forbidden"}, format="json"
        )
    assert response.status_code == 404
    patient.refresh_from_db()
    assert patient.full_name == "Alex Patient"
    assert Patient.objects.count() == 1


@pytest.mark.parametrize("method", ["get", "patch"])
def test_patient_must_belong_to_url_clinic_even_with_both_memberships(
    clinic: Clinic, foreign_clinic: Clinic, patient: Patient, method: str
) -> None:
    user = clinic.memberships.get(role="OWNER").user
    ClinicMembership.objects.create(clinic=foreign_clinic, user=user)
    client = authenticated_client(user)
    response = getattr(client, method)(
        detail_url(foreign_clinic, patient),
        {"full_name": "Forbidden"},
        format="json",
    )
    assert response.status_code == 404
    patient.refresh_from_db()
    assert patient.clinic_id == clinic.pk
    assert patient.full_name == "Alex Patient"


def test_nonexistent_clinic_and_patient_return_404(clinic: Clinic) -> None:
    client = authenticated_client(clinic.memberships.get(role="OWNER").user)
    assert (
        client.get(reverse("patients:patient-list", args=[999999])).status_code == 404
    )
    assert (
        client.get(
            reverse("patients:patient-detail", args=[clinic.pk, 999999])
        ).status_code
        == 404
    )


@pytest.mark.parametrize("is_superuser", [False, True])
def test_administrative_flags_do_not_grant_clinic_access(
    clinic: Clinic, django_user_model: type[User], is_superuser: bool
) -> None:
    user = django_user_model.objects.create_user(
        username="unrelated_admin", is_staff=True, is_superuser=is_superuser
    )
    assert authenticated_client(user).get(list_url(clinic)).status_code == 404


def test_removed_membership_revokes_patient_access(
    clinic: Clinic, patient: Patient
) -> None:
    membership = clinic.memberships.get(role="MEMBER")
    client = authenticated_client(membership.user)
    assert client.get(detail_url(clinic, patient)).status_code == 200
    membership.delete()
    assert client.get(list_url(clinic)).status_code == 404
    assert client.get(detail_url(clinic, patient)).status_code == 404
    assert client.post(list_url(clinic), {}, format="json").status_code == 404
    assert (
        client.patch(
            detail_url(clinic, patient), {"full_name": "Forbidden"}, format="json"
        ).status_code
        == 404
    )
    assert client.get(reverse("accounts:me")).status_code == 200


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Token invalid"])
def test_bearer_authentication_is_required(
    clinic: Clinic, patient: Patient, authorization: str | None
) -> None:
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)
    responses = [
        client.get(list_url(clinic)),
        client.post(list_url(clinic), {}, format="json"),
        client.get(detail_url(clinic, patient)),
        client.patch(detail_url(clinic, patient), {}, format="json"),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response["WWW-Authenticate"] == "Bearer" for response in responses)


@pytest.mark.parametrize("method", ["put", "delete"])
def test_unsupported_methods_do_not_modify_patient(
    clinic: Clinic, clinic_client: APIClient, patient: Patient, method: str
) -> None:
    response = getattr(clinic_client, method)(
        detail_url(clinic, patient), {"full_name": "Forbidden"}, format="json"
    )
    assert response.status_code == 405
    patient.refresh_from_db()
    assert patient.full_name == "Alex Patient"


def test_head_and_options_are_available(
    clinic: Clinic, clinic_client: APIClient, patient: Patient
) -> None:
    assert clinic_client.head(list_url(clinic)).status_code == 200
    assert clinic_client.head(detail_url(clinic, patient)).status_code == 200
    assert clinic_client.options(list_url(clinic)).status_code == 200


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_database_rejects_blank_patient_name(clinic: Clinic, name: str) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(clinic=clinic, full_name=name, birth_date="1990-05-12")
    assert not Patient.objects.exists()


def test_database_requires_birth_date(clinic: Clinic) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(clinic=clinic, full_name="Incomplete Patient")
    assert not Patient.objects.exists()


def test_patient_protects_clinic_from_orm_deletion(
    clinic: Clinic, patient: Patient
) -> None:
    with pytest.raises(ProtectedError):
        clinic.delete()
    assert Clinic.objects.filter(pk=clinic.pk).exists()
    assert Patient.objects.filter(pk=patient.pk).exists()
    assert clinic.memberships.count() == 2


def test_patient_contacts_and_name_are_not_unique(
    clinic: Clinic, foreign_clinic: Clinic, patient: Patient
) -> None:
    for destination in [clinic, foreign_clinic]:
        Patient.objects.create(
            clinic=destination,
            full_name=patient.full_name,
            birth_date=patient.birth_date,
            email=patient.email,
            phone=patient.phone,
        )
    assert Patient.objects.count() == 3
