from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicMembership
from apps.encounters.models import Encounter
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


def authenticated_client(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Encounter Clinic")
    for username, role in [
        ("encounter_owner", ClinicMembership.Role.OWNER),
        ("encounter_member", ClinicMembership.Role.MEMBER),
    ]:
        user = django_user_model.objects.create_user(username=username)
        ClinicMembership.objects.create(clinic=clinic, user=user, role=role)
    return clinic


@pytest.fixture(params=[ClinicMembership.Role.OWNER, ClinicMembership.Role.MEMBER])
def clinic_client(clinic: Clinic, request: pytest.FixtureRequest) -> APIClient:
    return authenticated_client(clinic.memberships.get(role=request.param).user)


@pytest.fixture
def foreign_clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Foreign Encounter Clinic")
    user = django_user_model.objects.create_user(username="encounter_outsider")
    ClinicMembership.objects.create(
        clinic=clinic, user=user, role=ClinicMembership.Role.OWNER
    )
    return clinic


@pytest.fixture
def patient(clinic: Clinic) -> Patient:
    return Patient.objects.create(
        clinic=clinic, full_name="Alex Encounter Patient", birth_date="1990-05-12"
    )


@pytest.fixture
def encounter(clinic: Clinic, patient: Patient) -> Encounter:
    return Encounter.objects.create(
        clinic=clinic,
        patient=patient,
        performed_at=timezone.now() - timedelta(days=1),
        description="Initial consultation",
    )


def list_url(clinic: Clinic) -> str:
    return reverse("encounters:encounter-list", args=[clinic.pk])


def detail_url(clinic: Clinic, encounter: Encounter) -> str:
    return reverse("encounters:encounter-detail", args=[clinic.pk, encounter.pk])


def valid_payload(patient: Patient) -> dict:
    return {
        "patient": patient.pk,
        "performed_at": "2020-01-01T10:00:00-03:00",
        "description": "Routine consultation",
    }


def owner_client(clinic: Clinic) -> APIClient:
    return authenticated_client(clinic.memberships.get(role="OWNER").user)


def test_owner_and_member_can_create_encounter(
    clinic: Clinic, clinic_client: APIClient, patient: Patient, foreign_clinic: Clinic
) -> None:
    payload = valid_payload(patient) | {
        "description": "  Routine consultation  ",
        "clinic": foreign_clinic.pk,
        "clinic_id": foreign_clinic.pk,
        "patient_id": 999999,
        "id": 0,
        "created_at": "2000-01-01T00:00:00Z",
        "updated_at": "2000-01-01T00:00:00Z",
    }
    response = clinic_client.post(list_url(clinic), payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "clinic",
        "patient",
        "performed_at",
        "description",
        "created_at",
        "updated_at",
    }
    assert data["id"] != 0
    assert data["clinic"] == clinic.pk
    assert data["patient"] == patient.pk
    assert data["description"] == "Routine consultation"
    assert data["performed_at"] == "2020-01-01T13:00:00Z"
    assert data["created_at"] != "2000-01-01T00:00:00Z"
    assert data["updated_at"] != "2000-01-01T00:00:00Z"
    saved = Encounter.objects.get(pk=data["id"])
    assert saved.clinic_id == clinic.pk
    assert saved.patient_id == patient.pk
    assert not foreign_clinic.encounters.exists()


@pytest.mark.parametrize(
    ("field", "value", "omit"),
    [
        ("patient", None, True),
        ("patient", None, False),
        ("patient", 999999, False),
        ("patient", "invalid", False),
        ("performed_at", None, True),
        ("performed_at", None, False),
        ("performed_at", "", False),
        ("performed_at", "invalid", False),
        ("description", None, True),
        ("description", None, False),
        ("description", "", False),
        ("description", " \t\n", False),
    ],
)
def test_creation_requires_valid_fields(
    clinic: Clinic, patient: Patient, field: str, value, omit: bool
) -> None:
    payload = valid_payload(patient)
    if omit:
        payload.pop(field)
    else:
        payload[field] = value
    response = owner_client(clinic).post(list_url(clinic), payload, format="json")
    assert response.status_code == 400
    assert field in response.json()
    assert not Encounter.objects.exists()


def test_creation_rejects_future_performed_time(
    clinic: Clinic, patient: Patient
) -> None:
    payload = valid_payload(patient) | {
        "performed_at": (timezone.now() + timedelta(hours=1)).isoformat()
    }
    response = owner_client(clinic).post(list_url(clinic), payload, format="json")
    assert response.status_code == 400
    assert "performed_at" in response.json()
    assert not Encounter.objects.exists()


def test_creation_accepts_current_performed_time(
    clinic: Clinic, patient: Patient
) -> None:
    now = timezone.now()
    payload = valid_payload(patient) | {"performed_at": now.isoformat()}
    with patch("apps.encounters.serializers.timezone.now", return_value=now):
        response = owner_client(clinic).post(list_url(clinic), payload, format="json")
    assert response.status_code == 201


@pytest.mark.parametrize("both_memberships", [False, True])
def test_creation_rejects_patient_from_another_clinic(
    clinic: Clinic, foreign_clinic: Clinic, both_memberships: bool
) -> None:
    foreign_patient = Patient.objects.create(
        clinic=foreign_clinic, full_name="Foreign Patient", birth_date="1980-01-01"
    )
    if both_memberships:
        ClinicMembership.objects.create(
            clinic=foreign_clinic, user=clinic.memberships.get(role="OWNER").user
        )
    client = owner_client(clinic)
    response = client.post(
        list_url(clinic), valid_payload(foreign_patient), format="json"
    )
    unknown = client.post(
        list_url(clinic),
        valid_payload(foreign_patient) | {"patient": 999999},
        format="json",
    )
    assert response.status_code == unknown.status_code == 400
    assert "patient" in response.json()
    assert not Encounter.objects.exists()


def test_listing_is_scoped_to_url_clinic(
    clinic: Clinic,
    clinic_client: APIClient,
    foreign_clinic: Clinic,
    encounter: Encounter,
) -> None:
    foreign_patient = Patient.objects.create(
        clinic=foreign_clinic, full_name="Foreign Patient", birth_date="1980-01-01"
    )
    Encounter.objects.create(
        clinic=foreign_clinic,
        patient=foreign_patient,
        performed_at=timezone.now() - timedelta(days=1),
        description="Foreign consultation",
    )
    response = clinic_client.get(
        list_url(clinic),
        {"clinic": foreign_clinic.pk, "patient": foreign_patient.pk},
        HTTP_X_CLINIC_ID=str(foreign_clinic.pk),
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [encounter.pk]


def test_accessible_clinic_without_encounters_returns_empty_list(
    clinic: Clinic, clinic_client: APIClient
) -> None:
    response = clinic_client.get(list_url(clinic))
    assert response.status_code == 200
    assert response.json() == []


def test_owner_and_member_can_retrieve_encounter(
    clinic: Clinic, clinic_client: APIClient, patient: Patient, encounter: Encounter
) -> None:
    response = clinic_client.get(detail_url(clinic, encounter))
    assert response.status_code == 200
    assert response.json()["id"] == encounter.pk
    assert response.json()["patient"] == patient.pk
    assert response.json()["description"] == encounter.description


def test_owner_and_member_can_edit_description_and_time(
    clinic: Clinic,
    clinic_client: APIClient,
    encounter: Encounter,
    foreign_clinic: Clinic,
) -> None:
    before = Encounter.objects.get(pk=encounter.pk)
    response = clinic_client.patch(
        detail_url(clinic, encounter),
        {
            "description": "  Updated consultation  ",
            "performed_at": "2021-02-03T14:00:00-03:00",
            "clinic": foreign_clinic.pk,
            "clinic_id": foreign_clinic.pk,
            "patient_id": 999999,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["performed_at"] == "2021-02-03T17:00:00Z"
    encounter.refresh_from_db()
    assert encounter.description == "Updated consultation"
    assert encounter.clinic_id == clinic.pk
    assert encounter.patient_id == before.patient_id
    assert encounter.created_at == before.created_at
    assert encounter.updated_at > before.updated_at


def test_partial_update_retains_patient_and_performed_time(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter
) -> None:
    before = Encounter.objects.get(pk=encounter.pk)
    response = clinic_client.patch(
        detail_url(clinic, encounter),
        {"description": "Corrected description"},
        format="json",
    )
    assert response.status_code == 200
    encounter.refresh_from_db()
    assert encounter.patient_id == before.patient_id
    assert encounter.performed_at == before.performed_at


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", ""),
        ("description", " \t\n"),
        ("description", None),
        ("performed_at", None),
        ("performed_at", ""),
        ("performed_at", "invalid"),
        ("patient", None),
    ],
)
def test_invalid_patch_leaves_encounter_unchanged(
    clinic: Clinic, encounter: Encounter, field: str, value
) -> None:
    before = Encounter.objects.values().get(pk=encounter.pk)
    response = owner_client(clinic).patch(
        detail_url(clinic, encounter), {field: value}, format="json"
    )
    assert response.status_code == 400
    assert field in response.json()
    assert Encounter.objects.values().get(pk=encounter.pk) == before


def test_patch_rejects_future_performed_time(
    clinic: Clinic, encounter: Encounter
) -> None:
    before = Encounter.objects.values().get(pk=encounter.pk)
    response = owner_client(clinic).patch(
        detail_url(clinic, encounter),
        {
            "performed_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            "description": "Should not be persisted",
        },
        format="json",
    )
    assert response.status_code == 400
    assert Encounter.objects.values().get(pk=encounter.pk) == before


def test_patient_cannot_be_changed_to_another_patient_in_same_clinic(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter
) -> None:
    other = Patient.objects.create(
        clinic=clinic, full_name="Other Patient", birth_date="1980-01-01"
    )
    before = Encounter.objects.values().get(pk=encounter.pk)
    response = clinic_client.patch(
        detail_url(clinic, encounter),
        {"patient": other.pk, "description": "Should not be persisted"},
        format="json",
    )
    assert response.status_code == 400
    assert "patient" in response.json()
    assert Encounter.objects.values().get(pk=encounter.pk) == before


def test_same_patient_can_be_resubmitted_on_patch(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter
) -> None:
    response = clinic_client.patch(
        detail_url(clinic, encounter),
        {"patient": encounter.patient_id, "description": "Corrected description"},
        format="json",
    )
    assert response.status_code == 200
    encounter.refresh_from_db()
    assert encounter.description == "Corrected description"


@pytest.mark.parametrize("method", ["list", "create", "retrieve", "patch"])
def test_unrelated_user_cannot_access_encounters(
    clinic: Clinic, encounter: Encounter, foreign_clinic: Clinic, method: str
) -> None:
    client = authenticated_client(foreign_clinic.memberships.get().user)
    if method == "list":
        response = client.get(list_url(clinic))
    elif method == "create":
        response = client.post(list_url(clinic), {}, format="json")
    elif method == "retrieve":
        response = client.get(detail_url(clinic, encounter))
    else:
        response = client.patch(
            detail_url(clinic, encounter), {"description": "Forbidden"}, format="json"
        )
    assert response.status_code == 404
    encounter.refresh_from_db()
    assert encounter.description == "Initial consultation"
    assert Encounter.objects.count() == 1


@pytest.mark.parametrize("method", ["get", "patch"])
def test_encounter_must_belong_to_url_clinic_even_with_both_memberships(
    clinic: Clinic, foreign_clinic: Clinic, encounter: Encounter, method: str
) -> None:
    ClinicMembership.objects.create(
        clinic=foreign_clinic, user=clinic.memberships.get(role="OWNER").user
    )
    response = getattr(owner_client(clinic), method)(
        detail_url(foreign_clinic, encounter),
        {"description": "Forbidden"},
        format="json",
    )
    assert response.status_code == 404
    encounter.refresh_from_db()
    assert encounter.clinic_id == clinic.pk
    assert encounter.description == "Initial consultation"


def test_nonexistent_clinic_and_encounter_return_404(clinic: Clinic) -> None:
    client = owner_client(clinic)
    assert (
        client.get(reverse("encounters:encounter-list", args=[999999])).status_code
        == 404
    )
    assert (
        client.get(
            reverse("encounters:encounter-detail", args=[clinic.pk, 999999])
        ).status_code
        == 404
    )


@pytest.mark.parametrize("is_superuser", [False, True])
def test_administrative_flags_do_not_grant_clinic_access(
    clinic: Clinic, django_user_model: type[User], is_superuser: bool
) -> None:
    user = django_user_model.objects.create_user(
        username="unrelated_encounter_admin", is_staff=True, is_superuser=is_superuser
    )
    assert authenticated_client(user).get(list_url(clinic)).status_code == 404


def test_removed_membership_revokes_encounter_access(
    clinic: Clinic, encounter: Encounter
) -> None:
    membership = clinic.memberships.get(role="MEMBER")
    client = authenticated_client(membership.user)
    assert client.get(detail_url(clinic, encounter)).status_code == 200
    membership.delete()
    assert client.get(list_url(clinic)).status_code == 404
    assert client.get(detail_url(clinic, encounter)).status_code == 404
    assert client.post(list_url(clinic), {}, format="json").status_code == 404
    assert (
        client.patch(
            detail_url(clinic, encounter), {"description": "Forbidden"}, format="json"
        ).status_code
        == 404
    )
    assert client.get(reverse("accounts:me")).status_code == 200


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Token invalid"])
def test_bearer_authentication_is_required(
    clinic: Clinic, encounter: Encounter, authorization: str | None
) -> None:
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)
    responses = [
        client.get(list_url(clinic)),
        client.post(list_url(clinic), {}, format="json"),
        client.get(detail_url(clinic, encounter)),
        client.patch(detail_url(clinic, encounter), {}, format="json"),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response["WWW-Authenticate"] == "Bearer" for response in responses)


@pytest.mark.parametrize("method", ["put", "delete"])
def test_unsupported_methods_do_not_modify_encounter(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, method: str
) -> None:
    response = getattr(clinic_client, method)(
        detail_url(clinic, encounter), {"description": "Forbidden"}, format="json"
    )
    assert response.status_code == 405
    encounter.refresh_from_db()
    assert encounter.description == "Initial consultation"


def test_head_and_options_are_available(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter
) -> None:
    assert clinic_client.head(list_url(clinic)).status_code == 200
    assert clinic_client.head(detail_url(clinic, encounter)).status_code == 200
    assert clinic_client.options(list_url(clinic)).status_code == 200


@pytest.mark.parametrize("description", ["", "   ", "\t\n"])
def test_database_rejects_blank_description(
    clinic: Clinic, patient: Patient, description: str
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Encounter.objects.create(
            clinic=clinic,
            patient=patient,
            performed_at=timezone.now(),
            description=description,
        )
    assert not Encounter.objects.exists()


def test_database_requires_performed_time(clinic: Clinic, patient: Patient) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Encounter.objects.create(
            clinic=clinic, patient=patient, description="Incomplete"
        )
    assert not Encounter.objects.exists()


def test_database_requires_patient(clinic: Clinic) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Encounter.objects.create(
            clinic=clinic, performed_at=timezone.now(), description="Incomplete"
        )
    assert not Encounter.objects.exists()


def test_encounter_protects_patient_from_orm_deletion(
    patient: Patient, encounter: Encounter
) -> None:
    with pytest.raises(ProtectedError):
        patient.delete()
    assert Patient.objects.filter(pk=patient.pk).exists()
    assert Encounter.objects.filter(pk=encounter.pk).exists()


def test_encounter_protects_clinic_from_orm_deletion(
    clinic: Clinic, encounter: Encounter
) -> None:
    with pytest.raises(ProtectedError):
        clinic.delete()
    assert Clinic.objects.filter(pk=clinic.pk).exists()
    assert Encounter.objects.filter(pk=encounter.pk).exists()
    assert clinic.memberships.count() == 2


def test_patient_can_have_multiple_encounters(
    clinic: Clinic, patient: Patient, encounter: Encounter
) -> None:
    second = Encounter.objects.create(
        clinic=clinic,
        patient=patient,
        performed_at=timezone.now() - timedelta(hours=1),
        description="Follow-up consultation",
    )
    assert second.pk != encounter.pk
    assert patient.encounters.count() == 2
