from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.charges.models import Charge, ChargeItem
from apps.encounters.models import Encounter

pytestmark = pytest.mark.django_db


def assert_constraint(error, expected):
    actual = error.value.__cause__.diag.constraint_name
    assert actual in expected if isinstance(expected, set) else actual == expected


@pytest.mark.parametrize(
    ("updates", "constraint"),
    [
        ({"amount": Decimal("-0.01")}, "charge_amount_valid_range"),
        ({"currency": "USD"}, "charge_currency_brl"),
        ({"status": "UNKNOWN"}, "charge_status_amount_consistent"),
        ({"amount": Decimal("0.00")}, "charge_status_amount_consistent"),
        (
            {"status": "PAID", "amount": Decimal("0.00")},
            "charge_status_amount_consistent",
        ),
        ({"status": "NO_PAYMENT_REQUIRED"}, "charge_status_amount_consistent"),
        ({"status": "CANCELLED"}, "charge_cancellation_consistent"),
        ({"cancellation_reason": "Correction"}, "charge_cancellation_consistent"),
        ({"cancelled_at": timezone.now()}, "charge_cancellation_consistent"),
    ],
)
def test_database_enforces_amount_currency_state_and_audit(charge, updates, constraint):
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Charge.objects.filter(pk=charge.pk).update(**updates)
    assert_constraint(error, constraint)
    charge.refresh_from_db()
    assert charge.status == "PENDING"


@pytest.mark.parametrize("reason", [None, "", " \t\n"])
def test_cancelled_charge_requires_nonblank_reason(billing, charge, reason):
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Charge.objects.filter(pk=charge.pk).update(
            status="CANCELLED",
            cancelled_at=timezone.now(),
            cancelled_by=billing.owner,
            cancellation_reason=reason,
        )
    assert_constraint(error, "charge_cancellation_consistent")


def test_database_rejects_nan_amount(charge):
    with (
        pytest.raises(IntegrityError) as error,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE charges_charge SET amount = 'NaN'::numeric WHERE id = %s",
            [charge.pk],
        )
    assert_constraint(error, "charge_amount_valid_range")


def test_database_prevents_duplicate_key_in_same_clinic(billing, charge):
    encounter = Encounter.objects.create(
        clinic=billing.clinic,
        patient=billing.patient,
        performed_at=billing.encounter.performed_at,
        description="Another encounter",
    )
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Charge.objects.create(
            clinic=billing.clinic,
            encounter=encounter,
            amount=Decimal("1.00"),
            status="PENDING",
            idempotency_key=charge.idempotency_key,
            created_by=billing.owner,
        )
    assert_constraint(error, "unique_clinic_charge_key")


def test_database_prevents_two_non_cancelled_charges(billing, charge):
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Charge.objects.create(
            clinic=billing.clinic,
            encounter=billing.encounter,
            amount=Decimal("1.00"),
            status="PENDING",
            idempotency_key=uuid4(),
            created_by=billing.owner,
        )
    assert_constraint(error, "unique_non_cancelled_encounter_charge")


@pytest.mark.parametrize(
    ("updates", "constraint"),
    [
        ({"quantity": 0}, "charge_item_quantity_positive"),
        (
            {"quantity": -1},
            {"charge_item_quantity_positive", "charges_chargeitem_quantity_check"},
        ),
        ({"procedure_name": " \t\n"}, "charge_item_name_not_blank"),
        ({"unit_price": Decimal("-0.01")}, "charge_item_price_valid_range"),
    ],
)
def test_database_validates_snapshot_values(charge, updates, constraint):
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        charge.items.update(**updates)
    assert_constraint(error, constraint)


def test_database_rejects_nan_snapshot_price(charge):
    with (
        pytest.raises(IntegrityError) as error,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE charges_chargeitem SET unit_price = 'NaN'::numeric "
            "WHERE charge_id = %s",
            [charge.pk],
        )
    assert_constraint(error, "charge_item_price_valid_range")


def test_database_prevents_duplicate_snapshot_procedures(billing, charge):
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        ChargeItem.objects.create(
            charge=charge,
            procedure=billing.procedure,
            procedure_name="Duplicate",
            quantity=1,
            unit_price=Decimal("1.00"),
        )
    assert_constraint(error, "unique_charge_procedure_item")


def test_financial_history_protects_related_records(billing, charge):
    billing.item.delete()
    for record in [
        charge,
        billing.encounter,
        billing.clinic,
        billing.procedure,
        billing.owner,
    ]:
        with pytest.raises(ProtectedError):
            record.delete()
    assert Charge.objects.filter(pk=charge.pk).exists()
    assert charge.items.count() == 1
