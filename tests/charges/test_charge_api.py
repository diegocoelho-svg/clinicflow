from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import Http404
from django.urls import reverse
from rest_framework.test import APIClient

from apps.charges.exceptions import ChargeConflict
from apps.charges.models import MAX_CHARGE_AMOUNT, Charge, ChargeItem
from apps.charges.services import issue_charge
from apps.clinics.models import ClinicMembership
from apps.encounters.models import Encounter, EncounterItem
from apps.encounters.serializers import EncounterItemSerializer
from apps.patients.models import Patient
from apps.procedures.models import Procedure

pytestmark = pytest.mark.django_db


def detail_url(billing, charge):
    return reverse("charges:charge-detail", args=[billing.clinic.pk, charge.pk])


def cancel_url(billing, charge):
    return reverse("charges:charge-cancel", args=[billing.clinic.pk, charge.pk])


def item_url(billing):
    return reverse(
        "encounters:encounter-item-detail",
        args=[billing.clinic.pk, billing.encounter.pk, billing.item.pk],
    )


def other_encounter(billing):
    return Encounter.objects.create(
        clinic=billing.clinic,
        patient=billing.patient,
        performed_at=billing.encounter.performed_at,
        description="Another encounter",
    )


@pytest.mark.parametrize("role", ["owner", "member"])
def test_issue_and_read_server_calculated_brl_charge(billing, issue, role):
    key = uuid4()
    client = getattr(billing, f"{role}_client")
    response = issue(key=key, client=client)
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "clinic",
        "encounter",
        "amount",
        "currency",
        "status",
        "idempotency_key",
        "created_by",
        "created_at",
        "updated_at",
        "cancelled_at",
        "cancelled_by",
        "cancellation_reason",
        "items",
    }
    assert isinstance(data["id"], int)
    assert data["clinic"] == billing.clinic.pk
    assert data["encounter"] == billing.encounter.pk
    assert data["amount"] == "24.68"
    assert data["currency"] == "BRL"
    assert data["status"] == "PENDING"
    assert data["idempotency_key"] == str(key)
    assert data["created_by"] == getattr(billing, role).pk
    assert data["created_at"] and data["updated_at"]
    assert (
        data["cancelled_at"]
        is data["cancelled_by"]
        is data["cancellation_reason"]
        is None
    )
    assert data["items"] == [
        {
            "id": ChargeItem.objects.get().pk,
            "procedure": billing.procedure.pk,
            "procedure_name": "Original consultation",
            "quantity": 2,
            "unit_price": "12.34",
            "total": "24.68",
        }
    ]
    saved = Charge.objects.get()
    assert saved.amount == Decimal("24.68")
    assert client.get(detail_url(billing, saved)).json() == data
    listing = client.get(reverse("charges:charge-list", args=[billing.clinic.pk]))
    assert listing.status_code == 200
    assert listing.json() == [data]


def test_catalog_changes_do_not_change_issued_snapshot(billing, issue):
    Procedure.objects.filter(pk=billing.procedure.pk).update(
        name="Changed catalog", unit_price=Decimal("99.99"), is_active=False
    )
    response = issue()
    assert response.status_code == 201
    assert response.json()["amount"] == "24.68"
    assert response.json()["items"][0]["procedure_name"] == "Original consultation"
    assert response.json()["items"][0]["unit_price"] == "12.34"
    Procedure.objects.filter(pk=billing.procedure.pk).update(unit_price=Decimal("0.00"))
    assert (
        billing.owner_client.get(detail_url(billing, Charge.objects.get())).json()
        == response.json()
    )


def test_retry_returns_same_charge_without_another_snapshot(billing, issue):
    key = uuid4()
    first = issue(key=key)
    second = issue(key=key, client=billing.member_client)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert Charge.objects.count() == ChargeItem.objects.count() == 1


def test_same_key_for_another_encounter_is_a_conflict(billing, issue):
    key = uuid4()
    assert issue(key=key).status_code == 201
    response = issue(key=key, encounter=other_encounter(billing))
    assert response.status_code == 409
    assert Charge.objects.count() == 1


def test_different_key_cannot_bypass_one_non_cancelled_charge(billing, issue):
    assert issue().status_code == 201
    before = Charge.objects.values().get()
    assert issue().status_code == 409
    assert Charge.objects.values().get() == before


def test_keys_are_scoped_to_the_clinic(billing, issue):
    key = uuid4()
    assert issue(key=key).status_code == 201
    patient = Patient.objects.create(
        clinic=billing.foreign_clinic,
        full_name="Foreign Patient",
        birth_date="2000-01-01",
    )
    encounter = Encounter.objects.create(
        clinic=billing.foreign_clinic,
        patient=patient,
        performed_at=billing.encounter.performed_at,
        description="Foreign encounter",
    )
    procedure = Procedure.objects.create(
        clinic=billing.foreign_clinic,
        name="Foreign procedure",
        unit_price=Decimal("1.00"),
    )
    EncounterItem.objects.create(
        encounter=encounter,
        procedure=procedure,
        procedure_name=procedure.name,
        unit_price=procedure.unit_price,
        quantity=1,
    )
    response = issue(
        key=key,
        encounter=encounter,
        clinic=billing.foreign_clinic,
        client=billing.outsider_client,
    )
    assert response.status_code == 201
    assert Charge.objects.filter(idempotency_key=key).count() == 2
    assert (
        len(
            billing.owner_client.get(
                reverse("charges:charge-list", args=[billing.clinic.pk])
            ).json()
        )
        == 1
    )


@pytest.mark.parametrize("key", [None, "", "invalid", "123", "a" * 1000])
def test_valid_uuid_header_is_required(billing, key):
    headers = {} if key is None else {"HTTP_IDEMPOTENCY_KEY": key}
    response = billing.owner_client.post(
        reverse(
            "charges:encounter-charge-list",
            args=[billing.clinic.pk, billing.encounter.pk],
        ),
        {},
        format="json",
        **headers,
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()
    assert not Charge.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": "0.00"},
        {"currency": "USD"},
        {"status": "PAID"},
        {"encounter": 999999},
        {"created_by": 999999},
        {"items": []},
        [],
        "invalid",
    ],
)
def test_issuance_accepts_only_an_empty_json_object(billing, issue, payload):
    assert issue(payload=payload).status_code == 400
    assert not Charge.objects.exists()


def test_empty_encounter_is_rejected_and_failed_validation_does_not_consume_key(
    billing, issue
):
    key = uuid4()
    billing.item.delete()
    assert issue(key=key).status_code == 400
    assert not Charge.objects.exists()
    billing.item.pk = None
    billing.item.save()
    assert issue(key=key).status_code == 201


def test_zero_total_does_not_record_a_payment(billing, issue):
    EncounterItem.objects.filter(pk=billing.item.pk).update(unit_price=Decimal("0.00"))
    response = issue()
    assert response.status_code == 201
    assert response.json()["amount"] == "0.00"
    assert response.json()["status"] == "NO_PAYMENT_REQUIRED"


def test_total_supports_large_exact_values_and_rejects_overflow_atomically(
    billing, issue
):
    EncounterItem.objects.filter(pk=billing.item.pk).update(
        unit_price=Decimal("9999999999.99"), quantity=2147483647
    )
    for index in range(4):
        procedure = Procedure.objects.create(
            clinic=billing.clinic,
            name=f"Large {index}",
            unit_price=Decimal("9999999999.99"),
        )
        EncounterItem.objects.create(
            encounter=billing.encounter,
            procedure=procedure,
            procedure_name=procedure.name,
            unit_price=procedure.unit_price,
            quantity=2147483647,
        )
    key = uuid4()
    assert issue(key=key).status_code == 400
    assert not Charge.objects.exists()
    assert not ChargeItem.objects.exists()
    billing.encounter.items.last().delete()
    response = issue(key=key)
    assert response.status_code == 201
    expected = Decimal("21474836469978525163.53") * 4
    assert expected <= MAX_CHARGE_AMOUNT
    assert response.json()["amount"] == str(expected)


def test_owner_cancels_with_reason_and_audit_fields(billing, charge):
    response = billing.owner_client.post(
        cancel_url(billing, charge), {"reason": "  Incorrect quantity  "}, format="json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert data["cancellation_reason"] == "Incorrect quantity"
    assert data["cancelled_by"] == billing.owner.pk
    assert data["cancelled_at"]
    assert data["amount"] == "24.68"
    assert ChargeItem.objects.count() == 1
    repeated = billing.owner_client.post(
        cancel_url(billing, charge), {"reason": "Another reason"}, format="json"
    )
    assert repeated.status_code == 200
    assert repeated.json() == data


def test_member_cannot_cancel(billing, charge):
    before = Charge.objects.values().get()
    assert (
        billing.member_client.post(
            cancel_url(billing, charge), {"reason": "Correction"}, format="json"
        ).status_code
        == 403
    )
    assert Charge.objects.values().get() == before


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"reason": ""},
        {"reason": " \t\n"},
        {"reason": None},
        {"reason": "a" * 1001},
        {"reason": "Correction", "status": "PAID"},
    ],
)
def test_cancellation_requires_a_nonblank_bounded_reason(billing, charge, payload):
    assert (
        billing.owner_client.post(
            cancel_url(billing, charge), payload, format="json"
        ).status_code
        == 400
    )
    charge.refresh_from_db()
    assert charge.status == "PENDING"


def test_paid_charge_cannot_be_cancelled(billing, charge):
    Charge.objects.filter(pk=charge.pk).update(status=Charge.Status.PAID)
    assert (
        billing.owner_client.post(
            cancel_url(billing, charge), {"reason": "Correction"}, format="json"
        ).status_code
        == 409
    )
    charge.refresh_from_db()
    assert charge.status == "PAID"
    assert charge.cancelled_at is None


@pytest.mark.parametrize("state", ["PENDING", "NO_PAYMENT_REQUIRED", "PAID"])
@pytest.mark.parametrize("operation", ["create", "patch", "delete"])
def test_non_cancelled_charge_freezes_all_item_writes(
    billing, charge, state, operation
):
    updates = {"status": state}
    if state == "NO_PAYMENT_REQUIRED":
        updates["amount"] = Decimal("0.00")
    Charge.objects.filter(pk=charge.pk).update(**updates)
    if operation == "create":
        procedure = Procedure.objects.create(
            clinic=billing.clinic, name="Additional", unit_price=Decimal("1.00")
        )
        response = billing.member_client.post(
            reverse(
                "encounters:encounter-item-list",
                args=[billing.clinic.pk, billing.encounter.pk],
            ),
            {"procedure": procedure.pk},
            format="json",
        )
    elif operation == "patch":
        response = billing.member_client.patch(
            item_url(billing), {"quantity": 3}, format="json"
        )
    else:
        response = billing.member_client.delete(item_url(billing))
    assert response.status_code == 409
    billing.item.refresh_from_db()
    assert billing.item.quantity == 2
    assert billing.encounter.items.count() == 1
    assert billing.member_client.get(item_url(billing)).status_code == 200


def test_clinical_description_can_still_change_after_issuance(billing, charge):
    response = billing.member_client.patch(
        reverse(
            "encounters:encounter-detail",
            args=[billing.clinic.pk, billing.encounter.pk],
        ),
        {"description": "Corrected clinical description"},
        format="json",
    )
    assert response.status_code == 200
    charge.refresh_from_db()
    assert charge.amount == Decimal("24.68")


def test_cancel_edit_and_reissue_preserves_history_and_original_key(billing, issue):
    old_key = uuid4()
    first = issue(key=old_key)
    original = Charge.objects.get()
    assert (
        billing.owner_client.post(
            cancel_url(billing, original), {"reason": "Correction"}, format="json"
        ).status_code
        == 200
    )
    assert (
        billing.member_client.patch(
            item_url(billing), {"quantity": 3}, format="json"
        ).status_code
        == 200
    )
    second = issue()
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert second.json()["amount"] == "37.02"
    replay = issue(key=old_key)
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["status"] == "CANCELLED"
    assert replay.json()["amount"] == "24.68"
    assert replay.json()["items"][0]["quantity"] == 2
    assert Charge.objects.count() == 2
    assert ChargeItem.objects.count() == 2


def test_cancelled_snapshots_survive_item_removal_and_readdition(
    billing, issue, charge
):
    assert (
        billing.owner_client.post(
            cancel_url(billing, charge), {"reason": "Correction"}, format="json"
        ).status_code
        == 200
    )
    assert billing.member_client.delete(item_url(billing)).status_code == 204
    assert issue(key=charge.idempotency_key).status_code == 200
    assert issue().status_code == 400
    Procedure.objects.filter(pk=billing.procedure.pk).update(
        name="New name", unit_price=Decimal("99.99")
    )
    response = billing.member_client.post(
        reverse(
            "encounters:encounter-item-list",
            args=[billing.clinic.pk, billing.encounter.pk],
        ),
        {"procedure": billing.procedure.pk},
        format="json",
    )
    assert response.status_code == 201
    assert issue().json()["amount"] == "99.99"
    old = billing.owner_client.get(detail_url(billing, charge)).json()
    assert old["items"][0]["procedure_name"] == "Original consultation"
    assert old["items"][0]["quantity"] == 2


def test_zero_charge_can_be_cancelled_and_reissued(billing, issue):
    EncounterItem.objects.filter(pk=billing.item.pk).update(unit_price=Decimal("0.00"))
    assert issue().json()["status"] == "NO_PAYMENT_REQUIRED"
    charge = Charge.objects.get()
    assert (
        billing.owner_client.post(
            cancel_url(billing, charge), {"reason": "Correction"}, format="json"
        ).status_code
        == 200
    )
    assert (
        billing.owner_client.patch(
            item_url(billing), {"quantity": 3}, format="json"
        ).status_code
        == 200
    )
    assert issue().status_code == 201


def access_requests(billing, charge, client, clinic_id=None):
    clinic_id = billing.clinic.pk if clinic_id is None else clinic_id
    return [
        client.get(reverse("charges:charge-list", args=[clinic_id])),
        client.get(reverse("charges:charge-detail", args=[clinic_id, charge.pk])),
        client.post(
            reverse("charges:charge-cancel", args=[clinic_id, charge.pk]),
            {"reason": "Correction"},
            format="json",
        ),
        client.post(
            reverse(
                "charges:encounter-charge-list", args=[clinic_id, billing.encounter.pk]
            ),
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        ),
    ]


@pytest.mark.parametrize("admin", [False, True])
def test_unrelated_users_and_admins_cannot_access_charges(billing, charge, admin):
    User.objects.filter(pk=billing.outsider.pk).update(
        is_staff=admin, is_superuser=admin
    )
    assert [
        response.status_code
        for response in access_requests(billing, charge, billing.outsider_client)
    ] == [404] * 4
    charge.refresh_from_db()
    assert charge.status == "PENDING"


def test_wrong_clinic_parent_is_rejected_even_with_both_memberships(billing, charge):
    ClinicMembership.objects.create(
        clinic=billing.foreign_clinic, user=billing.owner, role="OWNER"
    )
    responses = access_requests(
        billing, charge, billing.owner_client, billing.foreign_clinic.pk
    )
    assert [response.status_code for response in responses] == [200, 404, 404, 404]
    assert responses[0].json() == []


def test_removed_membership_revokes_financial_access(billing, charge):
    ClinicMembership.objects.filter(clinic=billing.clinic, user=billing.owner).delete()
    assert [
        response.status_code
        for response in access_requests(billing, charge, billing.owner_client)
    ] == [404] * 4


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Token invalid"])
def test_bearer_authentication_is_required(billing, charge, authorization):
    client = APIClient()
    if authorization:
        client.credentials(HTTP_AUTHORIZATION=authorization)
    responses = access_requests(billing, charge, client)
    assert [response.status_code for response in responses] == [401] * 4
    assert all(response["WWW-Authenticate"] == "Bearer" for response in responses)


def test_unknown_encounter_and_charge_are_not_found(billing, issue):
    encounter = other_encounter(billing)
    encounter.delete()
    assert issue(encounter=SimpleNamespace(pk=999999)).status_code == 404
    for name in ["charge-detail", "charge-cancel"]:
        url = reverse(f"charges:{name}", args=[billing.clinic.pk, 999999])
        response = (
            billing.owner_client.get(url)
            if name == "charge-detail"
            else billing.owner_client.post(url, {"reason": "Correction"}, format="json")
        )
        assert response.status_code == 404


def test_charge_mutation_methods_are_not_exposed(billing, charge):
    for method in ["put", "patch", "delete", "post"]:
        assert (
            getattr(billing.owner_client, method)(
                detail_url(billing, charge), {"status": "PAID"}, format="json"
            ).status_code
            == 405
        )
    assert (
        billing.owner_client.post(
            reverse("charges:charge-list", args=[billing.clinic.pk]), {}, format="json"
        ).status_code
        == 405
    )
    assert (
        billing.owner_client.get(
            reverse(
                "charges:encounter-charge-list",
                args=[billing.clinic.pk, billing.encounter.pk],
            )
        ).status_code
        == 405
    )
    assert billing.owner_client.head(detail_url(billing, charge)).status_code == 200
    assert billing.owner_client.options(detail_url(billing, charge)).status_code == 200


def test_snapshot_failure_rolls_back_charge_and_does_not_consume_key(
    billing, monkeypatch
):
    key = uuid4()

    def fail(*args, **kwargs):
        raise IntegrityError("Unrelated snapshot failure")

    with monkeypatch.context() as patch:
        patch.setattr(ChargeItem.objects, "bulk_create", fail)
        with pytest.raises(IntegrityError, match="Unrelated snapshot failure"):
            issue_charge(
                clinic_id=billing.clinic.pk,
                encounter_id=billing.encounter.pk,
                actor=billing.owner,
                idempotency_key=key,
            )
    assert not Charge.objects.exists()
    assert not ChargeItem.objects.exists()
    saved, created = issue_charge(
        clinic_id=billing.clinic.pk,
        encounter_id=billing.encounter.pk,
        actor=billing.owner,
        idempotency_key=key,
    )
    assert created
    assert saved.items.count() == 1


def test_stale_item_serializer_cannot_bypass_a_new_charge(billing, issue):
    serializer = EncounterItemSerializer(
        billing.item,
        data={"quantity": 3},
        partial=True,
        context={"encounter": billing.encounter},
    )
    assert serializer.is_valid(), serializer.errors
    assert issue().status_code == 201
    with pytest.raises(ChargeConflict):
        serializer.save()
    billing.item.refresh_from_db()
    assert billing.item.quantity == 2


def test_stale_item_serializer_cannot_resurrect_a_deleted_item(billing):
    item_id = billing.item.pk
    serializer = EncounterItemSerializer(
        billing.item,
        data={"quantity": 3},
        partial=True,
        context={"encounter": billing.encounter},
    )
    assert serializer.is_valid(), serializer.errors
    EncounterItem.objects.filter(pk=item_id).delete()
    with pytest.raises(Http404):
        serializer.save()
    assert not EncounterItem.objects.filter(pk=item_id).exists()
