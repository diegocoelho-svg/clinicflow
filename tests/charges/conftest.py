from datetime import timedelta
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
from apps.procedures.models import Procedure


def client_for(user: User) -> APIClient:
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
    return client


@pytest.fixture
def billing() -> SimpleNamespace:
    clinic = Clinic.objects.create(name="Billing Clinic")
    owner = User.objects.create_user(username="billing_owner")
    member = User.objects.create_user(username="billing_member")
    outsider = User.objects.create_user(username="billing_outsider")
    for user, role in [(owner, "OWNER"), (member, "MEMBER")]:
        ClinicMembership.objects.create(clinic=clinic, user=user, role=role)
    foreign_clinic = Clinic.objects.create(name="Foreign Billing Clinic")
    ClinicMembership.objects.create(clinic=foreign_clinic, user=outsider, role="OWNER")
    patient = Patient.objects.create(
        clinic=clinic, full_name="Fictional Billing Patient", birth_date="1990-01-01"
    )
    encounter = Encounter.objects.create(
        clinic=clinic,
        patient=patient,
        performed_at=timezone.now() - timedelta(days=1),
        description="Completed consultation",
    )
    procedure = Procedure.objects.create(
        clinic=clinic, name="Original consultation", unit_price=Decimal("12.34")
    )
    item = EncounterItem.objects.create(
        encounter=encounter,
        procedure=procedure,
        procedure_name=procedure.name,
        unit_price=procedure.unit_price,
        quantity=2,
    )
    return SimpleNamespace(
        clinic=clinic,
        owner=owner,
        member=member,
        outsider=outsider,
        foreign_clinic=foreign_clinic,
        patient=patient,
        encounter=encounter,
        procedure=procedure,
        item=item,
        owner_client=client_for(owner),
        member_client=client_for(member),
        outsider_client=client_for(outsider),
    )


@pytest.fixture
def issue(billing):
    def submit(*, key=None, encounter=None, clinic=None, client=None, payload=None):
        return (client or billing.owner_client).post(
            reverse(
                "charges:encounter-charge-list",
                args=[
                    (clinic or billing.clinic).pk,
                    (encounter or billing.encounter).pk,
                ],
            ),
            {} if payload is None else payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid4()),
        )

    return submit


@pytest.fixture
def charge(billing):
    charge, _ = issue_charge(
        clinic_id=billing.clinic.pk,
        encounter_id=billing.encounter.pk,
        actor=billing.owner,
        idempotency_key=uuid4(),
    )
    return charge
