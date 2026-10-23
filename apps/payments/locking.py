import hashlib

from django.db import connection


def lock_payment_reference(payment_reference: str) -> None:
    # Acquire inside atomic(), before the encounter and event locks.
    # Collisions only serialize extra work; full identities are still compared.
    lock_key = int.from_bytes(
        hashlib.sha256(
            ("clinicflow.simulated-payment:" + payment_reference).encode()
        ).digest()[:8],
        "big",
        signed=True,
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])
