from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from uuid import uuid4

import pytest
from django.db import connection, connections, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.charges.models import Charge, ChargeItem
from apps.charges.services import issue_charge
from apps.encounters.models import Encounter, EncounterItem
from apps.procedures.models import Procedure

pytestmark = pytest.mark.django_db(transaction=True)


def worker_client(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_simultaneous_retries_create_one_charge_and_one_snapshot(billing):
    assert_duplicate_issuance(billing, same_key=True, same_encounter=True)


def test_simultaneous_different_keys_cannot_duplicate_a_charge(billing):
    assert_duplicate_issuance(billing, same_key=False, same_encounter=True)


def test_simultaneous_key_reuse_across_encounters_is_a_conflict(billing, monkeypatch):
    # Force both transactions past the initial replay lookup, exercising the
    # database uniqueness conflict and the recovery after atomic rolls back.
    barrier = Barrier(2)
    original_create = Charge.objects.create

    def synchronized_create(**kwargs):
        barrier.wait(timeout=10)
        return original_create(**kwargs)

    monkeypatch.setattr(Charge.objects, "create", synchronized_create)
    assert_duplicate_issuance(billing, same_key=True, same_encounter=False)


def assert_duplicate_issuance(billing, *, same_key, same_encounter):
    barrier = Barrier(2)
    token = billing.owner.auth_token.key
    keys = [uuid4(), uuid4()]
    if same_key:
        keys[1] = keys[0]
    encounters = [billing.encounter.pk, billing.encounter.pk]
    if not same_encounter:
        other = Encounter.objects.create(
            clinic=billing.clinic,
            patient=billing.patient,
            performed_at=billing.encounter.performed_at,
            description="Concurrent encounter",
        )
        EncounterItem.objects.create(
            encounter=other,
            procedure=billing.procedure,
            procedure_name=billing.procedure.name,
            unit_price=billing.procedure.unit_price,
            quantity=1,
        )
        encounters[1] = other.pk

    def submit(index):
        try:
            client = worker_client(token)
            barrier.wait(timeout=10)
            response = client.post(
                reverse(
                    "charges:encounter-charge-list",
                    args=[billing.clinic.pk, encounters[index]],
                ),
                {},
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(keys[index]),
            )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))
    assert sorted(status for status, _ in results) == (
        [200, 201] if same_key and same_encounter else [201, 409]
    )
    assert Charge.objects.count() == ChargeItem.objects.count() == 1
    if same_key and same_encounter:
        assert results[0][1] == results[1][1]


def wait_until_blocked(pid):
    deadline = monotonic() + 10
    pause = Event()
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT cardinality(pg_blocking_pids(%s)) > 0", [pid])
            if cursor.fetchone()[0]:
                return
        pause.wait(0.01)
    pytest.fail("The concurrent writer never waited on the encounter row lock.")


def submit_with_pid(token, pid_queue, action):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pid_queue.put(cursor.fetchone()[0])
        response = action(worker_client(token))
        return response.status_code, response.json() if response.content else None
    finally:
        connections.close_all()


def mutate(billing, client, operation, procedure):
    url = reverse(
        "encounters:encounter-item-detail",
        args=[billing.clinic.pk, billing.encounter.pk, billing.item.pk],
    )
    if operation == "patch":
        return client.patch(url, {"quantity": 3}, format="json")
    if operation == "delete":
        return client.delete(url)
    return client.post(
        reverse(
            "encounters:encounter-item-list",
            args=[billing.clinic.pk, billing.encounter.pk],
        ),
        {"procedure": procedure.pk, "quantity": 1},
        format="json",
    )


@pytest.mark.parametrize("operation", ["create", "patch", "delete"])
def test_item_writer_waits_for_issuance_then_rejects_the_change(billing, operation):
    procedure = Procedure.objects.create(
        clinic=billing.clinic, name="Additional", unit_price=Decimal("1.00")
    )
    queue = Queue()
    token = billing.owner.auth_token.key
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            Encounter.objects.select_for_update().get(pk=billing.encounter.pk)
            future = executor.submit(
                submit_with_pid,
                token,
                queue,
                lambda client: mutate(billing, client, operation, procedure),
            )
            wait_until_blocked(queue.get(timeout=10))
            charge, created = issue_charge(
                clinic_id=billing.clinic.pk,
                encounter_id=billing.encounter.pk,
                actor=billing.owner,
                idempotency_key=uuid4(),
            )
            assert created
        result, _ = future.result(timeout=15)
    assert result == 409
    billing.item.refresh_from_db()
    assert billing.item.quantity == 2
    assert billing.encounter.items.count() == 1
    assert charge.amount == Decimal("24.68")
    assert charge.items.get().quantity == 2


@pytest.mark.parametrize("operation", ["create", "patch", "delete"])
def test_issuance_waits_for_item_writer_and_reads_committed_items(billing, operation):
    procedure = Procedure.objects.create(
        clinic=billing.clinic, name="Additional", unit_price=Decimal("1.00")
    )
    queue = Queue()
    token = billing.owner.auth_token.key
    url = reverse(
        "charges:encounter-charge-list", args=[billing.clinic.pk, billing.encounter.pk]
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            Encounter.objects.select_for_update().get(pk=billing.encounter.pk)
            future = executor.submit(
                submit_with_pid,
                token,
                queue,
                lambda client: client.post(
                    url, {}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid4())
                ),
            )
            wait_until_blocked(queue.get(timeout=10))
            response = mutate(billing, billing.owner_client, operation, procedure)
            assert (
                response.status_code
                == {"create": 201, "patch": 200, "delete": 204}[operation]
            )
        result, data = future.result(timeout=15)
    if operation == "delete":
        assert result == 400
        assert not Charge.objects.exists()
        assert not ChargeItem.objects.exists()
    else:
        assert result == 201
        assert data["amount"] == {"create": "25.68", "patch": "37.02"}[operation]
        assert len(data["items"]) == (2 if operation == "create" else 1)


def test_item_writer_waits_for_cancellation_then_can_edit(billing, charge):
    queue = Queue()
    token = billing.owner.auth_token.key
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            Encounter.objects.select_for_update().get(pk=billing.encounter.pk)
            future = executor.submit(
                submit_with_pid,
                token,
                queue,
                lambda client: mutate(billing, client, "patch", billing.procedure),
            )
            wait_until_blocked(queue.get(timeout=10))
            response = billing.owner_client.post(
                reverse("charges:charge-cancel", args=[billing.clinic.pk, charge.pk]),
                {"reason": "Correction"},
                format="json",
            )
            assert response.status_code == 200
        result, data = future.result(timeout=15)
    assert result == 200
    assert data["quantity"] == 3
    charge.refresh_from_db()
    assert charge.status == "CANCELLED"
    assert charge.items.get().quantity == 2


def test_simultaneous_cancellation_preserves_one_audit_record(billing, charge):
    barrier = Barrier(2)
    token = billing.owner.auth_token.key

    def cancel(index):
        try:
            client = worker_client(token)
            barrier.wait(timeout=10)
            response = client.post(
                reverse("charges:charge-cancel", args=[billing.clinic.pk, charge.pk]),
                {"reason": f"Correction {index}"},
                format="json",
            )
            assert response.status_code == 200
            return response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(cancel, range(2)))
    assert results[0] == results[1]
    assert results[0]["status"] == "CANCELLED"
    assert Charge.objects.count() == ChargeItem.objects.count() == 1
