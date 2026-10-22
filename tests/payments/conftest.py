import hashlib
import hmac
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.charges.services import issue_charge
from apps.clinics.models import Clinic, ClinicMembership
from apps.encounters.models import Encounter, EncounterItem
from apps.patients.models import Patient
from apps.payments.serializers import PaymentNotificationSerializer
from apps.payments.services import accept_event
from apps.procedures.models import Procedure

TEST_SECRET = "fictional-webhook-test-key-with-more-than-32-bytes"


def client_for(user):
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture(autouse=True)
def configured_webhook(settings):
    settings.SIMULATED_PAYMENT_WEBHOOK_SECRET = TEST_SECRET


@pytest.fixture
def scope():
    clinic = Clinic.objects.create(name="Fictional Payment Clinic")
    other = Clinic.objects.create(name="Other Payment Clinic")
    owner = User.objects.create_user(username="payment-owner")
    member = User.objects.create_user(username="payment-member")
    outsider = User.objects.create_superuser(username="payment-outsider")
    ClinicMembership.objects.create(clinic=clinic, user=owner, role="OWNER")
    ClinicMembership.objects.create(clinic=clinic, user=member, role="MEMBER")
    ClinicMembership.objects.create(clinic=other, user=outsider, role="OWNER")
    patient = Patient.objects.create(
        clinic=clinic, full_name="Fictional Payment Patient", birth_date="1990-01-01"
    )
    procedure = Procedure.objects.create(
        clinic=clinic, name="Consultation", unit_price=Decimal("12.34")
    )

    def new_charge():
        encounter = Encounter.objects.create(
            clinic=clinic,
            patient=patient,
            description="Completed fictional consultation",
            performed_at=timezone.now(),
        )
        EncounterItem.objects.create(
            encounter=encounter,
            procedure=procedure,
            procedure_name=procedure.name,
            quantity=2,
            unit_price=procedure.unit_price,
        )
        return issue_charge(
            clinic_id=clinic.pk,
            encounter_id=encounter.pk,
            actor=owner,
            idempotency_key=uuid4(),
        )[0]

    charge = new_charge()
    payload = {
        "event_id": str(uuid4()),
        "clinic_id": clinic.pk,
        "charge_id": charge.pk,
        "payment_reference": f"test:{uuid4()}",
        "amount": "24.68",
        "currency": "BRL",
        "paid_at": timezone.now().isoformat(),
    }

    def new_event(**changes):
        data = {
            **payload,
            "event_id": str(uuid4()),
            "payment_reference": f"test:{uuid4()}",
            **changes,
        }
        serializer = PaymentNotificationSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return accept_event(serializer.validated_data)[0]

    return SimpleNamespace(
        clinic=clinic,
        other=other,
        owner=owner,
        member=member,
        outsider=outsider,
        charge=charge,
        payload=payload,
        new_charge=new_charge,
        new_event=new_event,
        owner_client=client_for(owner),
        member_client=client_for(member),
        outsider_client=client_for(outsider),
    )


@pytest.fixture
def post_notification():
    def post(
        payload=None,
        *,
        raw=None,
        timestamp=None,
        content_type="application/json",
        **overrides,
    ):
        body = raw if raw is not None else json.dumps(payload).encode()
        timestamp_text = str(int(time.time()) if timestamp is None else timestamp)
        digest = hmac.new(
            TEST_SECRET.encode(), timestamp_text.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return APIClient().generic(
            "POST",
            reverse("payments:simulated-webhook"),
            body,
            content_type=content_type,
            **{
                "HTTP_X_WEBHOOK_TIMESTAMP": timestamp_text,
                "HTTP_X_WEBHOOK_SIGNATURE": f"sha256={digest}",
                **overrides,
            },
        )

    return post
