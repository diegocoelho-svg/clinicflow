import hashlib
import hmac
import json
from http.client import IncompleteRead
from io import BytesIO, StringIO
from urllib.error import URLError

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.payments.management.commands import simulate_payment
from apps.payments.models import PaymentEvent

pytestmark = pytest.mark.django_db


def test_simulator_signs_one_local_request_without_exposing_secret(
    scope, monkeypatch, settings
):
    requests = []

    def receive(request, **kwargs):
        requests.append(request)
        return BytesIO(b'{"id":123,"status":"RECEIVED"}')

    monkeypatch.setattr(simulate_payment, "urlopen", receive)
    output = StringIO()
    call_command("simulate_payment", scope.charge.pk, stdout=output)
    assert len(requests) == 1
    request = requests[0]
    assert (
        request.full_url == "http://127.0.0.1:8000/api/v1/payment-webhooks/simulated/"
    )
    headers = dict((key.lower(), value) for key, value in request.header_items())
    expected = hmac.new(
        settings.SIMULATED_PAYMENT_WEBHOOK_SECRET.encode(),
        headers["x-webhook-timestamp"].encode() + b"." + request.data,
        hashlib.sha256,
    ).hexdigest()
    assert headers["x-webhook-signature"] == "sha256=" + expected
    assert json.loads(request.data)["amount"] == "24.68"
    assert settings.SIMULATED_PAYMENT_WEBHOOK_SECRET not in output.getvalue()


def test_simulator_does_not_blindly_retry_after_an_uncertain_submission(
    scope, monkeypatch
):
    calls = []

    def unavailable(request, **kwargs):
        calls.append(request)
        raise URLError("Synthetic connection loss")

    monkeypatch.setattr(simulate_payment, "urlopen", unavailable)
    with pytest.raises(CommandError, match="no second event was sent"):
        call_command("simulate_payment", scope.charge.pk)
    assert len(calls) == 1


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_worker_rejects_invalid_batch_limits(limit):
    with pytest.raises(CommandError):
        call_command("reconcile_payments", limit=limit)


def test_watch_worker_stops_cleanly(scope, monkeypatch):
    scope.new_event()

    def stop(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "apps.payments.management.commands.reconcile_payments.time.sleep", stop
    )
    output = StringIO()
    call_command("reconcile_payments", watch=True, stdout=output)
    assert "stopped" in output.getvalue()
    assert not PaymentEvent.objects.filter(status="RECEIVED").exists()


@pytest.mark.parametrize("failure", ["truncated", "reset", "invalid_json"])
def test_simulator_preserves_event_identity_after_response_read_failure(
    scope, monkeypatch, settings, failure
):
    calls = []

    class FailedReceipt(BytesIO):
        def read(self, *args, **kwargs):
            if failure == "truncated":
                raise IncompleteRead(b"{", 10)
            if failure == "reset":
                raise ConnectionResetError("Synthetic response loss")
            return b"<html>unreadable acknowledgement</html>"

    def uncertain(request, **kwargs):
        calls.append(request)
        return FailedReceipt()

    monkeypatch.setattr(simulate_payment, "urlopen", uncertain)
    with pytest.raises(CommandError) as error:
        call_command("simulate_payment", scope.charge.pk)
    assert len(calls) == 1
    event_id = json.loads(calls[0].data)["event_id"]
    assert f"Check event {event_id}" in str(error.value)
    assert "no second event was sent" in str(error.value)
    assert settings.SIMULATED_PAYMENT_WEBHOOK_SECRET not in str(error.value)
