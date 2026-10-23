"""Run through Django's shell in the isolated frontend Compose project.

HTTP requests cross Vite's /api proxy; only cleanup uses the ORM. Credentials
are generated in memory, never printed, and all created synthetic data is removed.
"""

import json
import secrets
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.clinics.models import Clinic

marker = "web_smoke_" + secrets.token_hex(8)
usernames = [marker, marker + "_other"]
password = secrets.token_urlsafe(36)
token = None


def call(path, expected, method="GET", body=None, bearer=None):
    headers = {"Accept": "application/json", "Host": "localhost:5173"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = Request(
        "http://frontend:5173/api/v1/" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        raw = response.read()
        data = json.loads(raw) if raw else None
        assert status == expected, (
            f"{method} {path}: expected {expected}, received {status}"
        )
        if path.startswith("auth/"):
            assert "no-store" in response.headers.get("Cache-Control", "")
    print(f"PASS {method} /api/v1/{path} -> {status}")
    return data


try:
    profile = call(
        "auth/register/",
        201,
        "POST",
        {
            "username": usernames[0],
            "password": password,
            "email": marker + "@example.test",
            "first_name": "Pessoa",
            "last_name": "Sintética",
        },
    )
    assert set(profile) == {"id", "username", "email", "first_name", "last_name"}
    call(
        "auth/token/",
        400,
        "POST",
        {"username": usernames[0], "password": secrets.token_urlsafe(36)},
    )
    token = call(
        "auth/token/", 200, "POST", {"username": usernames[0], "password": password}
    )["token"]
    assert call("auth/me/", 200, bearer=token) == profile
    assert call("clinics/", 200, bearer=token) == []
    call("clinics/", 400, "POST", {"name": "   "}, token)
    clinics = [
        call("clinics/", 201, "POST", {"name": f"{marker} Clínica {number}"}, token)
        for number in (1, 2)
    ]
    assert {item["id"] for item in call("clinics/", 200, bearer=token)} == {
        item["id"] for item in clinics
    }
    for clinic in clinics:
        assert call(f"clinics/{clinic['id']}/", 200, bearer=token) == clinic
    call(
        "auth/register/",
        201,
        "POST",
        {
            "username": usernames[1],
            "password": password,
            "email": marker + "_other@example.test",
            "first_name": "Outra",
            "last_name": "Pessoa",
        },
    )
    other_token = call(
        "auth/token/", 200, "POST", {"username": usernames[1], "password": password}
    )["token"]
    assert call("clinics/", 200, bearer=other_token) == []
    call(f"clinics/{clinics[0]['id']}/", 404, bearer=other_token)
    call("auth/logout/", 204, "POST", bearer=other_token)
    call("auth/logout/", 204, "POST", bearer=token)
    call("auth/me/", 401, bearer=token)
    call("clinics/", 401, bearer=token)
    print("PASS real authentication and clinic isolation through Vite proxy")
finally:
    with transaction.atomic():
        synthetic_users = get_user_model().objects.filter(username__in=usernames)
        synthetic_clinics = Clinic.objects.filter(
            memberships__user__in=synthetic_users
        ).distinct()
        for clinic in synthetic_clinics:
            assert clinic.name.startswith(marker), (
                "Refusing cleanup of a foreign clinic"
            )
            assert clinic.memberships.count() == 1, (
                "Refusing cleanup of a shared clinic"
            )
        synthetic_clinics.delete()
        synthetic_users.delete()
    assert not get_user_model().objects.filter(username__in=usernames).exists()
    assert not Clinic.objects.filter(name__startswith=marker).exists()
    password = token = None
    print("PASS cleanup: synthetic users, clinics, memberships and tokens removed")
