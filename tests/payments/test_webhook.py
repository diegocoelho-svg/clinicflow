import json
import time

import pytest
from django.urls import reverse

from apps.charges.models import Charge
from apps.payments.models import Payment, PaymentEvent
from apps.payments.services import reconcile_event

pytestmark = pytest.mark.django_db


def test_acceptance_persists_before_reconciliation(scope, post_notification):
    response = post_notification(scope.payload)
    assert response.status_code == 202
    assert response.data["status"] == "RECEIVED"
    assert response.data["amount"] == "24.68"
    assert "payload_hash" not in response.data
    assert "no-store" in response["Cache-Control"]
    assert PaymentEvent.objects.count() == 1
    assert not Payment.objects.exists()
    scope.charge.refresh_from_db()
    assert scope.charge.status == Charge.Status.PENDING


def test_replay_normalizes_json_and_returns_current_event(scope, post_notification):
    first = post_notification(scope.payload)
    replay = post_notification(raw=json.dumps(scope.payload, indent=2).encode())
    assert replay.status_code == 200
    assert replay.data["id"] == first.data["id"]
    reconcile_event(first.data["id"])
    replay = post_notification(scope.payload)
    assert replay.status_code == 200
    assert replay.data["status"] == "RECONCILED"
    assert PaymentEvent.objects.count() == Payment.objects.count() == 1


def test_conflicting_event_identity_is_not_overwritten(scope, post_notification):
    post_notification(scope.payload)
    response = post_notification({**scope.payload, "amount": "24.69"})
    assert response.status_code == 409
    assert str(PaymentEvent.objects.get().amount) == "24.68"


@pytest.mark.parametrize("delta", [-301, 301])
def test_old_and_future_signatures_are_rejected(scope, post_notification, delta):
    response = post_notification(scope.payload, timestamp=int(time.time()) + delta)
    assert response.status_code == 403
    assert not PaymentEvent.objects.exists()


@pytest.mark.parametrize(
    "headers",
    [
        {"HTTP_X_WEBHOOK_TIMESTAMP": ""},
        {"HTTP_X_WEBHOOK_TIMESTAMP": "not-an-integer"},
        {"HTTP_X_WEBHOOK_SIGNATURE": ""},
        {"HTTP_X_WEBHOOK_SIGNATURE": "sha256=" + "0" * 64},
        {"HTTP_X_WEBHOOK_SIGNATURE": "sha256=" + "A" * 64},
    ],
)
def test_invalid_signatures_do_not_persist(scope, post_notification, headers):
    assert post_notification(scope.payload, **headers).status_code == 403
    assert not PaymentEvent.objects.exists()


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_configuration_is_fail_closed(scope, post_notification, settings, secret):
    settings.SIMULATED_PAYMENT_WEBHOOK_SECRET = secret
    assert post_notification(scope.payload).status_code == 503
    assert not PaymentEvent.objects.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 24.68},
        {"amount": "-1.00"},
        {"amount": "1.0"},
        {"amount": "1e2"},
        {"amount": "100000000000000000000.00"},
        {"currency": "brl"},
        {"currency": "REAL"},
        {"charge_id": True},
        {"clinic_id": "1"},
        {"charge_id": 0},
        {"charge_id": 9223372036854775808},
        {"event_id": "bad-uuid"},
        {"event_id": 0},
        {"payment_reference": 123},
        {"payment_reference": " trimmed "},
        {"payment_reference": "provider:identity\n"},
        {"payment_reference": "a" * 128 + "\n"},
        {"payment_reference": "a" * 129},
        {"currency": "BRL\n"},
        {"currency": " BRL"},
        {"currency": "BRL "},
        {"paid_at": "bad-date"},
        {"payment_reference": " "},
        {"status": "RECONCILED"},
    ],
)
def test_invalid_claims_are_rejected(scope, post_notification, changes):
    response = post_notification({**scope.payload, **changes})
    assert response.status_code == 400
    assert not PaymentEvent.objects.exists()


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"null",
        b"{",
        b'{"amount":NaN}',
        b"\xff",
        b'{"event_id":"first","event_id":"second"}',
    ],
)
def test_malformed_or_ambiguous_json_is_rejected(post_notification, raw):
    assert post_notification(raw=raw).status_code == 400
    assert not PaymentEvent.objects.exists()


@pytest.mark.parametrize("size", [65537, 3000000])
def test_size_and_content_type_are_limited(post_notification, size):
    assert post_notification(raw=b" " * size).status_code == 413
    assert post_notification(raw=b"{}", content_type="text/plain").status_code == 415


def test_unknown_clinic_is_not_accepted(scope, post_notification):
    response = post_notification({**scope.payload, "clinic_id": 9223372036854775807})
    assert response.status_code == 400
    assert not PaymentEvent.objects.exists()


def test_signed_provider_does_not_need_a_browser_token(scope, post_notification):
    response = post_notification(scope.payload, HTTP_AUTHORIZATION="Bearer invalid")
    assert response.status_code == 202


@pytest.mark.parametrize("resource", ["payment", "event"])
def test_reads_are_scoped_to_membership(scope, resource):
    event = scope.new_event()
    reconcile_event(event.pk)
    item = Payment.objects.get() if resource == "payment" else event
    list_url = reverse(f"payments:{resource}-list", args=[scope.clinic.pk])
    detail_url = reverse(f"payments:{resource}-detail", args=[scope.clinic.pk, item.pk])
    wrong_url = reverse(f"payments:{resource}-detail", args=[scope.other.pk, item.pk])
    assert scope.owner_client.get(list_url).status_code == 200
    assert scope.member_client.get(detail_url).status_code == 200
    assert scope.outsider_client.get(list_url).status_code == 404
    assert scope.outsider_client.get(wrong_url).status_code == 404
    assert (
        scope.owner_client.patch(detail_url, {"status": "RECEIVED"}).status_code == 405
    )
    assert scope.owner_client.post(list_url, {}).status_code == 405


def test_expired_or_missing_session_cannot_read(scope):
    from rest_framework.test import APIClient

    assert (
        APIClient()
        .get(reverse("payments:event-list", args=[scope.clinic.pk]))
        .status_code
        == 401
    )


def test_changed_signed_payload_cannot_reuse_another_event_id(scope, post_notification):
    event = scope.new_event()
    response = post_notification({**scope.payload, "event_id": str(event.event_id)})
    assert response.status_code == 409
    assert PaymentEvent.objects.count() == 1


def test_maximum_provider_reference_is_accepted(scope, post_notification):
    response = post_notification({**scope.payload, "payment_reference": "a" * 128})
    assert response.status_code == 202
    assert PaymentEvent.objects.get().payment_reference == "a" * 128


def test_equivalent_timestamp_offset_preserves_event_identity(scope, post_notification):
    from datetime import datetime, timedelta, timezone

    first = post_notification(scope.payload)
    paid_at = datetime.fromisoformat(scope.payload["paid_at"])
    equivalent = paid_at.astimezone(timezone(timedelta(hours=-3))).isoformat()
    replay = post_notification({**scope.payload, "paid_at": equivalent})
    assert replay.status_code == 200
    assert replay.data["id"] == first.data["id"]
