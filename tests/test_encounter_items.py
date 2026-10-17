from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, connection, connections, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicMembership
from apps.encounters.models import Encounter, EncounterItem
from apps.encounters.serializers import EncounterItemSerializer
from apps.patients.models import Patient
from apps.procedures.models import Procedure

pytestmark = pytest.mark.django_db


def authenticated_client(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Item Clinic")
    for username, role in [("item_owner", "OWNER"), ("item_member", "MEMBER")]:
        user = django_user_model.objects.create_user(username=username)
        ClinicMembership.objects.create(clinic=clinic, user=user, role=role)
    return clinic


@pytest.fixture(params=["OWNER", "MEMBER"])
def clinic_client(clinic: Clinic, request: pytest.FixtureRequest) -> APIClient:
    return authenticated_client(clinic.memberships.get(role=request.param).user)


@pytest.fixture
def owner_client(clinic: Clinic) -> APIClient:
    return authenticated_client(clinic.memberships.get(role="OWNER").user)


@pytest.fixture
def encounter(clinic: Clinic) -> Encounter:
    patient = Patient.objects.create(
        clinic=clinic, full_name="Item Patient", birth_date="1990-01-01"
    )
    return Encounter.objects.create(
        clinic=clinic,
        patient=patient,
        performed_at=timezone.now() - timedelta(days=1),
        description="Consultation",
    )


@pytest.fixture
def procedure(clinic: Clinic) -> Procedure:
    return Procedure.objects.create(
        clinic=clinic, name="Original procedure", unit_price=Decimal("12.34")
    )


@pytest.fixture
def item(encounter: Encounter, procedure: Procedure) -> EncounterItem:
    return EncounterItem.objects.create(
        encounter=encounter,
        procedure=procedure,
        procedure_name=procedure.name,
        unit_price=procedure.unit_price,
        quantity=2,
    )


@pytest.fixture
def foreign_clinic(django_user_model: type[User]) -> Clinic:
    clinic = Clinic.objects.create(name="Foreign Item Clinic")
    user = django_user_model.objects.create_user(username="item_outsider")
    ClinicMembership.objects.create(clinic=clinic, user=user, role="OWNER")
    return clinic


def list_url(clinic: Clinic, encounter: Encounter) -> str:
    return reverse("encounters:encounter-item-list", args=[clinic.pk, encounter.pk])


def detail_url(clinic: Clinic, encounter: Encounter, item: EncounterItem) -> str:
    return reverse(
        "encounters:encounter-item-detail", args=[clinic.pk, encounter.pk, item.pk]
    )


def test_owner_and_member_create_item_with_server_price_snapshot(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, procedure: Procedure
) -> None:
    response = clinic_client.post(
        list_url(clinic, encounter),
        {
            "procedure": procedure.pk,
            "quantity": 2,
            "procedure_name": "Forged name",
            "unit_price": "0.00",
            "total": "0.00",
            "encounter": 999999,
            "encounter_id": 999999,
            "clinic": 999999,
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
        "encounter",
        "procedure",
        "procedure_name",
        "quantity",
        "unit_price",
        "total",
        "created_at",
        "updated_at",
    }
    assert data["id"] != 0
    assert data["encounter"] == encounter.pk
    assert data["procedure"] == procedure.pk
    assert data["procedure_name"] == "Original procedure"
    assert data["quantity"] == 2
    assert data["unit_price"] == "12.34"
    assert data["total"] == "24.68"
    assert data["created_at"] != "2000-01-01T00:00:00Z"
    assert data["updated_at"] != "2000-01-01T00:00:00Z"
    saved = EncounterItem.objects.get(pk=data["id"])
    assert saved.unit_price == Decimal("12.34")
    assert saved.total == Decimal("24.68")


def test_quantity_defaults_to_one(
    clinic: Clinic, owner_client: APIClient, encounter: Encounter, procedure: Procedure
) -> None:
    response = owner_client.post(
        list_url(clinic, encounter), {"procedure": procedure.pk}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["quantity"] == 1
    assert response.json()["total"] == "12.34"


@pytest.mark.parametrize(
    ("price", "quantity", "expected"),
    [
        ("0.00", 2, "0.00"),
        ("0.10", 3, "0.30"),
        ("0.29", 3, "0.87"),
        ("9999999999.99", 2147483647, "21474836469978525163.53"),
    ],
)
def test_total_preserves_decimal_precision_and_supported_bounds(
    clinic: Clinic,
    owner_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    price: str,
    quantity: int,
    expected: str,
) -> None:
    procedure.unit_price = Decimal(price)
    procedure.save()
    response = owner_client.post(
        list_url(clinic, encounter),
        {"procedure": procedure.pk, "quantity": quantity},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["total"] == expected


@pytest.mark.parametrize(
    "quantity", [0, -1, None, "", "invalid", 1.5, "1.1", True, 2147483648]
)
def test_creation_rejects_invalid_quantity(
    clinic: Clinic,
    owner_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    quantity,
) -> None:
    response = owner_client.post(
        list_url(clinic, encounter),
        {"procedure": procedure.pk, "quantity": quantity},
        format="json",
    )
    assert response.status_code == 400
    assert "quantity" in response.json()
    assert not EncounterItem.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [{}, {"procedure": None}, {"procedure": 999999}, {"procedure": "invalid"}],
)
def test_creation_requires_existing_procedure(
    clinic: Clinic, owner_client: APIClient, encounter: Encounter, payload: dict
) -> None:
    response = owner_client.post(list_url(clinic, encounter), payload, format="json")
    assert response.status_code == 400
    assert "procedure" in response.json()
    assert not EncounterItem.objects.exists()


def test_inactive_procedure_cannot_be_added(
    clinic: Clinic, owner_client: APIClient, encounter: Encounter, procedure: Procedure
) -> None:
    procedure.is_active = False
    procedure.save()
    response = owner_client.post(
        list_url(clinic, encounter), {"procedure": procedure.pk}, format="json"
    )
    assert response.status_code == 400
    assert "procedure" in response.json()
    assert not EncounterItem.objects.exists()


@pytest.mark.parametrize("both_memberships", [False, True])
def test_foreign_procedure_is_rejected_even_with_both_memberships(
    clinic: Clinic,
    owner_client: APIClient,
    encounter: Encounter,
    foreign_clinic: Clinic,
    both_memberships: bool,
) -> None:
    foreign = Procedure.objects.create(
        clinic=foreign_clinic, name="Foreign", unit_price=Decimal("1.00")
    )
    if both_memberships:
        ClinicMembership.objects.create(
            clinic=foreign_clinic, user=clinic.memberships.get(role="OWNER").user
        )
    response = owner_client.post(
        list_url(clinic, encounter), {"procedure": foreign.pk}, format="json"
    )
    assert response.status_code == 400
    assert "procedure" in response.json()
    assert not EncounterItem.objects.exists()


def test_duplicate_procedure_returns_400_without_changing_existing_item(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, item: EncounterItem
) -> None:
    before = EncounterItem.objects.values().get(pk=item.pk)
    response = clinic_client.post(
        list_url(clinic, encounter),
        {"procedure": item.procedure_id, "quantity": 9},
        format="json",
    )
    assert response.status_code == 400
    assert "procedure" in response.json()
    assert EncounterItem.objects.count() == 1
    assert EncounterItem.objects.values().get(pk=item.pk) == before


def test_listing_and_detail_are_scoped_to_parent_encounter(
    clinic: Clinic,
    clinic_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    item: EncounterItem,
) -> None:
    other = Encounter.objects.create(
        clinic=clinic,
        patient=encounter.patient,
        performed_at=encounter.performed_at,
        description="Other encounter",
    )
    EncounterItem.objects.create(
        encounter=other,
        procedure=procedure,
        procedure_name=procedure.name,
        unit_price=procedure.unit_price,
    )
    response = clinic_client.get(
        list_url(clinic, encounter),
        {"encounter": other.pk, "clinic": 999999},
        HTTP_X_CLINIC_ID="999999",
    )
    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == [item.pk]
    detail = clinic_client.get(detail_url(clinic, encounter, item))
    assert detail.status_code == 200
    assert detail.json()["total"] == "24.68"


def test_empty_encounter_returns_empty_list(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter
) -> None:
    response = clinic_client.get(list_url(clinic, encounter))
    assert response.status_code == 200
    assert response.json() == []


def test_catalog_changes_preserve_snapshot_and_allow_quantity_edits(
    clinic: Clinic,
    clinic_client: APIClient,
    owner_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    item: EncounterItem,
) -> None:
    response = owner_client.patch(
        reverse("procedures:procedure-detail", args=[clinic.pk, procedure.pk]),
        {"name": "New catalog name", "unit_price": "99.99", "is_active": False},
        format="json",
    )
    assert response.status_code == 200
    detail = clinic_client.get(detail_url(clinic, encounter, item))
    assert detail.status_code == 200
    assert detail.json()["procedure_name"] == "Original procedure"
    assert detail.json()["unit_price"] == "12.34"
    response = clinic_client.patch(
        detail_url(clinic, encounter, item),
        {
            "quantity": 3,
            "procedure": procedure.pk,
            "unit_price": "0.00",
            "procedure_name": "Forged",
            "total": "0.00",
            "encounter": 999999,
            "id": 0,
            "created_at": "2000-01-01T00:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["procedure_name"] == "Original procedure"
    assert response.json()["unit_price"] == "12.34"
    assert response.json()["total"] == "37.02"
    item.refresh_from_db()
    assert item.encounter_id == encounter.pk
    assert item.quantity == 3


@pytest.mark.parametrize("quantity", [0, -1, None, 1.5, 2147483648])
def test_invalid_quantity_patch_does_not_change_item(
    clinic: Clinic,
    clinic_client: APIClient,
    encounter: Encounter,
    item: EncounterItem,
    quantity,
) -> None:
    before = EncounterItem.objects.values().get(pk=item.pk)
    response = clinic_client.patch(
        detail_url(clinic, encounter, item), {"quantity": quantity}, format="json"
    )
    assert response.status_code == 400
    assert "quantity" in response.json()
    assert EncounterItem.objects.values().get(pk=item.pk) == before


def test_procedure_cannot_be_replaced_on_patch(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, item: EncounterItem
) -> None:
    other = Procedure.objects.create(
        clinic=clinic, name="Other procedure", unit_price=Decimal("1.00")
    )
    before = EncounterItem.objects.values().get(pk=item.pk)
    response = clinic_client.patch(
        detail_url(clinic, encounter, item),
        {"procedure": other.pk, "quantity": 9},
        format="json",
    )
    assert response.status_code == 400
    assert "procedure" in response.json()
    assert EncounterItem.objects.values().get(pk=item.pk) == before


def test_owner_and_member_can_delete_then_readd_at_current_price(
    clinic: Clinic,
    clinic_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    item: EncounterItem,
) -> None:
    previous_id = item.pk
    response = clinic_client.delete(detail_url(clinic, encounter, item))
    assert response.status_code == 204
    assert response.content == b""
    assert not EncounterItem.objects.exists()
    assert clinic_client.get(detail_url(clinic, encounter, item)).status_code == 404
    procedure.unit_price = Decimal("99.99")
    procedure.save()
    response = clinic_client.post(
        list_url(clinic, encounter), {"procedure": procedure.pk}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["id"] != previous_id
    assert response.json()["unit_price"] == "99.99"


def test_inactive_catalog_does_not_prevent_item_removal(
    clinic: Clinic,
    clinic_client: APIClient,
    encounter: Encounter,
    procedure: Procedure,
    item: EncounterItem,
) -> None:
    procedure.is_active = False
    procedure.save()
    assert clinic_client.delete(detail_url(clinic, encounter, item)).status_code == 204
    assert not EncounterItem.objects.exists()


@pytest.mark.parametrize("method", ["list", "create", "retrieve", "patch", "delete"])
def test_unrelated_user_cannot_access_items(
    clinic: Clinic,
    encounter: Encounter,
    item: EncounterItem,
    foreign_clinic: Clinic,
    method: str,
) -> None:
    client = authenticated_client(foreign_clinic.memberships.get().user)
    if method == "list":
        response = client.get(list_url(clinic, encounter))
    elif method == "create":
        response = client.post(list_url(clinic, encounter), {}, format="json")
    elif method == "retrieve":
        response = client.get(detail_url(clinic, encounter, item))
    elif method == "patch":
        response = client.patch(
            detail_url(clinic, encounter, item), {"quantity": 9}, format="json"
        )
    else:
        response = client.delete(detail_url(clinic, encounter, item))
    assert response.status_code == 404
    item.refresh_from_db()
    assert item.quantity == 2


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_item_cannot_be_accessed_under_another_encounter(
    clinic: Clinic,
    owner_client: APIClient,
    encounter: Encounter,
    item: EncounterItem,
    method: str,
) -> None:
    other = Encounter.objects.create(
        clinic=clinic,
        patient=encounter.patient,
        performed_at=encounter.performed_at,
        description="Other",
    )
    response = getattr(owner_client, method)(
        detail_url(clinic, other, item), {"quantity": 9}, format="json"
    )
    assert response.status_code == 404
    item.refresh_from_db()
    assert item.quantity == 2


def test_wrong_clinic_parent_returns_404_with_both_memberships(
    clinic: Clinic,
    owner_client: APIClient,
    encounter: Encounter,
    item: EncounterItem,
    foreign_clinic: Clinic,
) -> None:
    ClinicMembership.objects.create(
        clinic=foreign_clinic, user=clinic.memberships.get(role="OWNER").user
    )
    assert owner_client.get(list_url(foreign_clinic, encounter)).status_code == 404
    assert (
        owner_client.post(
            list_url(foreign_clinic, encounter), {}, format="json"
        ).status_code
        == 404
    )
    assert (
        owner_client.get(detail_url(foreign_clinic, encounter, item)).status_code == 404
    )


def test_unknown_parent_and_item_return_404(
    clinic: Clinic, owner_client: APIClient, encounter: Encounter
) -> None:
    assert (
        owner_client.get(
            reverse("encounters:encounter-item-list", args=[clinic.pk, 999999])
        ).status_code
        == 404
    )
    assert (
        owner_client.get(
            reverse("encounters:encounter-item-list", args=[999999, encounter.pk])
        ).status_code
        == 404
    )
    assert (
        owner_client.get(
            reverse(
                "encounters:encounter-item-detail",
                args=[clinic.pk, encounter.pk, 999999],
            )
        ).status_code
        == 404
    )


@pytest.mark.parametrize("is_superuser", [False, True])
def test_administrative_flags_do_not_grant_item_access(
    clinic: Clinic,
    encounter: Encounter,
    django_user_model: type[User],
    is_superuser: bool,
) -> None:
    user = django_user_model.objects.create_user(
        username="item_unrelated_admin", is_staff=True, is_superuser=is_superuser
    )
    assert (
        authenticated_client(user).get(list_url(clinic, encounter)).status_code == 404
    )


def test_removed_membership_revokes_all_item_operations(
    clinic: Clinic, encounter: Encounter, item: EncounterItem
) -> None:
    membership = clinic.memberships.get(role="MEMBER")
    client = authenticated_client(membership.user)
    assert client.get(detail_url(clinic, encounter, item)).status_code == 200
    membership.delete()
    assert client.get(list_url(clinic, encounter)).status_code == 404
    assert (
        client.post(list_url(clinic, encounter), {}, format="json").status_code == 404
    )
    assert client.get(detail_url(clinic, encounter, item)).status_code == 404
    assert (
        client.patch(
            detail_url(clinic, encounter, item), {"quantity": 9}, format="json"
        ).status_code
        == 404
    )
    assert client.delete(detail_url(clinic, encounter, item)).status_code == 404
    assert client.get(reverse("accounts:me")).status_code == 200


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Token invalid"])
def test_bearer_authentication_is_required(
    clinic: Clinic, encounter: Encounter, item: EncounterItem, authorization: str | None
) -> None:
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)
    responses = [
        client.get(list_url(clinic, encounter)),
        client.post(list_url(clinic, encounter), {}, format="json"),
        client.get(detail_url(clinic, encounter, item)),
        client.patch(detail_url(clinic, encounter, item), {}, format="json"),
        client.delete(detail_url(clinic, encounter, item)),
    ]
    assert all(response.status_code == 401 for response in responses)
    assert all(response["WWW-Authenticate"] == "Bearer" for response in responses)


def test_put_is_not_supported(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, item: EncounterItem
) -> None:
    assert (
        clinic_client.put(
            detail_url(clinic, encounter, item), {"quantity": 9}, format="json"
        ).status_code
        == 405
    )
    item.refresh_from_db()
    assert item.quantity == 2


def test_head_and_options_are_supported(
    clinic: Clinic, clinic_client: APIClient, encounter: Encounter, item: EncounterItem
) -> None:
    assert clinic_client.head(list_url(clinic, encounter)).status_code == 200
    assert clinic_client.head(detail_url(clinic, encounter, item)).status_code == 200
    assert clinic_client.options(list_url(clinic, encounter)).status_code == 200


def test_snapshot_uses_catalog_values_current_after_validation(
    encounter: Encounter, procedure: Procedure
) -> None:
    serializer = EncounterItemSerializer(
        data={"procedure": procedure.pk}, context={"encounter": encounter}
    )
    assert serializer.is_valid(), serializer.errors
    Procedure.objects.filter(pk=procedure.pk).update(
        name="Changed before save", unit_price=Decimal("99.99")
    )
    saved = serializer.save(encounter=encounter)
    assert saved.procedure_name == "Changed before save"
    assert saved.unit_price == Decimal("99.99")


@pytest.mark.parametrize("change", ["deactivate", "delete"])
def test_procedure_is_rechecked_after_validation(
    encounter: Encounter, procedure: Procedure, change: str
) -> None:
    serializer = EncounterItemSerializer(
        data={"procedure": procedure.pk}, context={"encounter": encounter}
    )
    assert serializer.is_valid(), serializer.errors
    if change == "deactivate":
        Procedure.objects.filter(pk=procedure.pk).update(is_active=False)
    else:
        procedure.delete()
    with pytest.raises(serializers.ValidationError):
        serializer.save(encounter=encounter)
    assert not EncounterItem.objects.exists()


@pytest.mark.parametrize("quantity", [0, -1])
def test_database_requires_positive_quantity(
    encounter: Encounter, procedure: Procedure, quantity: int
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        EncounterItem.objects.create(
            encounter=encounter,
            procedure=procedure,
            procedure_name=procedure.name,
            unit_price=procedure.unit_price,
            quantity=quantity,
        )
    assert not EncounterItem.objects.exists()


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_database_requires_nonblank_snapshot_name(
    encounter: Encounter, procedure: Procedure, name: str
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        EncounterItem.objects.create(
            encounter=encounter,
            procedure=procedure,
            procedure_name=name,
            unit_price=procedure.unit_price,
        )
    assert not EncounterItem.objects.exists()


def test_database_rejects_negative_snapshot_price(
    encounter: Encounter, procedure: Procedure
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        EncounterItem.objects.create(
            encounter=encounter,
            procedure=procedure,
            procedure_name=procedure.name,
            unit_price=Decimal("-0.01"),
        )
    assert not EncounterItem.objects.exists()


def test_database_rejects_nan_snapshot_price(
    encounter: Encounter, procedure: Procedure
) -> None:
    with (
        pytest.raises(IntegrityError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO encounters_encounteritem "
            "(encounter_id, procedure_id, procedure_name, quantity, unit_price, "
            "created_at, updated_at) "
            "VALUES (%s, %s, %s, 1, 'NaN'::numeric, now(), now())",
            [encounter.pk, procedure.pk, procedure.name],
        )
    assert not EncounterItem.objects.exists()


def test_database_enforces_unique_encounter_procedure_pair(
    encounter: Encounter, procedure: Procedure, item: EncounterItem
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        EncounterItem.objects.create(
            encounter=encounter,
            procedure=procedure,
            procedure_name=procedure.name,
            unit_price=procedure.unit_price,
        )
    assert EncounterItem.objects.count() == 1


def test_item_protects_encounter_and_procedure_from_orm_deletion(
    encounter: Encounter, procedure: Procedure, item: EncounterItem
) -> None:
    for record in [encounter, procedure]:
        with pytest.raises(ProtectedError):
            record.delete()
    assert EncounterItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_requests_create_one_item(
    clinic: Clinic, encounter: Encounter, procedure: Procedure
) -> None:
    token = Token.objects.create(user=clinic.memberships.get(role="OWNER").user).key
    url = list_url(clinic, encounter)
    procedure_id = procedure.pk
    barrier = Barrier(2)

    def submit() -> int:
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            barrier.wait(timeout=10)
            return client.post(
                url, {"procedure": procedure_id}, format="json"
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: submit(), range(2)))
    assert sorted(statuses) == [201, 400]
    assert EncounterItem.objects.count() == 1
