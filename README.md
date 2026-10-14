# ClinicFlow — Financial Automation API

ClinicFlow is a backend project for automating financial operations in clinics.
The intended workflow connects appointments, charges, simulated payment webhooks,
and asynchronous reconciliation, with data isolation between clinics.

## Current scope

The API includes Django REST Framework, PostgreSQL, Docker Compose, health
endpoints, user registration, Bearer token login, the authenticated user profile,
logout, clinic creation/listing/retrieval/name updates, owner/member permissions,
clinic access isolation, Pytest, and Ruff.
Patient endpoints, membership management, payment integrations, the Pub/Sub
emulator, and its consumer will be added in subsequent development steps.

All patient data and payment integrations will be fictional. The project runs
locally and does not require cloud resources or paid services.

## Technology choices

- Python 3.13 is the container runtime.
- Django 5.2 is an LTS release, compatible with Python 3.13.
- Django REST Framework provides the HTTP API layer.
- PostgreSQL 17 is the only database used by the application and tests.
- Psycopg 3 connects the Django ORM to PostgreSQL. Its binary distribution avoids
  requiring a compiler in the local development image.
- Pytest, pytest-django, and Ruff run in the same image as the API.

Dependency ranges are defined in `pyproject.toml`. Exact runtime and development
versions, including transitive dependencies, are recorded in `requirements.lock`.
Docker image tags track patch updates within their selected release families.

References: [Django 5.2 compatibility](https://docs.djangoproject.com/en/5.2/releases/5.2/),
[DRF requirements](https://www.django-rest-framework.org/#requirements), and
[PostgreSQL version policy](https://www.postgresql.org/support/versioning/).

## Run locally

Requirements: Docker Engine or Docker Desktop with Docker Compose v2. A host
Python installation is not needed.

From the repository or worktree root, copy `.env.example` to `.env`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux or macOS:

```sh
cp .env.example .env
```

Replace `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` with generated local values.
Generate a value for each using:

```sh
docker run --rm python:3.13-slim-bookworm python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`.env` is ignored by Git and excluded from the Docker build context. Never commit
credentials. Keep `POSTGRES_HOST=db` and `POSTGRES_PORT=5432` for container commands.
Compose sets these addresses explicitly for the API.

Start the environment:

```sh
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
```

Compose waits for PostgreSQL to become healthy. The API applies Django's built-in
migrations before starting, then reports healthy when its readiness endpoint
can query PostgreSQL. Database files live in the named `postgres_data` volume.
PostgreSQL is accessible inside the Compose network; the API binds to loopback
port 8000. Set `API_PORT` in `.env` if that port is already in use.

The image contains a snapshot of the source. After editing code, run
`docker compose up -d --build --wait` again to apply the changes.

## Health endpoints

Both endpoints are public, return JSON, and support GET and HEAD.

| Endpoint | Success | Failure | Purpose |
| --- | --- | --- | --- |
| `/health/` | `200 {"status":"ok"}` | No database dependency | API liveness |
| `/health/ready/` | `200 {"status":"ready","database":"ok"}` | `503 {"status":"unavailable","database":"unavailable"}` | PostgreSQL connectivity |

Readiness executes `SELECT 1`; it verifies connectivity, not migration state or
the availability of future external integrations. Database exceptions are logged
server-side; connection details are not returned to callers. Other endpoints
will require authentication by default.

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health/
Invoke-RestMethod http://localhost:8000/health/ready/
```

Linux or macOS:

```sh
curl -fsS http://localhost:8000/health/
curl -fsS http://localhost:8000/health/ready/
```

## Authentication

The API uses Django's native user model and DRF's database-backed tokens, sent
with the Bearer authorization scheme.

| Endpoint | Request | Success | Access |
| --- | --- | --- | --- |
| `POST /api/v1/auth/register/` | JSON with `username`, `password`, `email`, `first_name`, and `last_name` | `201`, user profile JSON | Public |
| `POST /api/v1/auth/token/` | JSON with `username` and `password` | `200 {"token":"..."}` | Public |
| `GET /api/v1/auth/me/` | `Authorization: Bearer <token>` | `200`, user profile JSON | Authenticated |
| `POST /api/v1/auth/logout/` | `Authorization: Bearer <token>` | `204`, empty body | Authenticated |

Registration requires all five fields. Missing, null, empty, or whitespace-only
values return 400 without creating an account. Email must be valid, username must
be unique, and passwords must pass Django's configured strength validators.
Duplicate username conflicts, including concurrent creation, return 400.

Accounts are active ordinary users. Clients cannot assign IDs, staff or superuser
permissions, groups, or account activation flags. Django hashes passwords; the
response contains only `id`, `username`, `email`, `first_name`, and `last_name`.
Registration does not issue a token; sign in separately to obtain one. Email is
required but is not a unique identifier in the current native user model.

Login accepts JSON and returns 400 for missing or invalid credentials, with a
generic error for an unknown user, incorrect password, or inactive account.
Protected endpoints return 401 with `WWW-Authenticate: Bearer` for missing,
invalid, revoked, or inactive-user tokens. The previous `Token` prefix is not
accepted. Session cookies alone do not authenticate API requests. Login and
registration ignore stale authorization headers.

Each user has one opaque token; it is not a JWT. Repeated login reuses it, and
logout revokes it for all clients using that token. A subsequent login creates a
new token. Tokens have no automatic expiration in this local MVP. Authentication
responses include `Cache-Control: no-store`.

Login and registration each allow 10 requests per minute per client IP, then
return 429 with `Retry-After`. The app ignores client-supplied forwarded IP
headers for these limits. Limits include successful and failed requests, use
Django's local cache, and reset when the API process restarts. They are best-effort
limits for this single-process environment. A production setup would need HTTPS,
an appropriate token lifecycle, and shared rate limiting.

### Test with Insomnia

Use `http://localhost:8000` as the base URL, or the port configured in `API_PORT`.

1. Send `POST /api/v1/auth/register/` with a JSON body:

   ```json
   {
     "username": "alex_demo",
     "password": "Choose-a-strong-local-password-942!",
     "email": "alex@example.test",
     "first_name": "Alex",
     "last_name": "Demo"
   }
   ```

   Choose your own local password. A successful request returns 201 and the user
   profile.
2. Send `POST /api/v1/auth/token/` with the same username and password.
3. Copy the returned token. On `GET /api/v1/auth/me/`, select **Auth → Bearer
   Token** and paste only the token value.
4. Send `POST /api/v1/auth/logout/` with the same Bearer authentication. It
   returns 204; using that token on `/me/` now returns 401.

For administrative access only, Django's `createsuperuser` command remains
available:

```sh
docker compose exec api python manage.py createsuperuser
```

PowerShell login example, using the account registered above:

```powershell
$baseUrl = "http://localhost:8000"
$credential = Get-Credential -Message "Enter your registered username and password"
$loginBody = @{
    username = $credential.UserName
    password = $credential.GetNetworkCredential().Password
} | ConvertTo-Json
$login = Invoke-RestMethod "$baseUrl/api/v1/auth/token/" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.token)" }
Invoke-RestMethod "$baseUrl/api/v1/auth/me/" -Headers $headers
Invoke-WebRequest "$baseUrl/api/v1/auth/logout/" -Method Post -Headers $headers -UseBasicParsing
```

Set `$baseUrl` to match `API_PORT` when using a different local port.

## Clinics

All clinic endpoints require Bearer authentication.

| Endpoint | Request | Success | Access |
| --- | --- | --- | --- |
| `POST /api/v1/clinics/` | JSON with `name` | `201`, clinic JSON | Authenticated user; becomes owner |
| `GET /api/v1/clinics/` | Bearer token | `200`, array of clinics | Only the user's memberships |
| `GET /api/v1/clinics/{id}/` | Bearer token | `200`, clinic JSON | Owner or member |
| `PATCH /api/v1/clinics/{id}/` | JSON with `name` | `200`, updated clinic JSON | Owner |

`name` is required at creation, trimmed, nonblank, and limited to 255 characters.
Missing, null, blank, whitespace-only, or oversized names return 400. Clinic names
are not globally unique. Responses expose only `id`, `name`, `created_at`, and
`updated_at`; identity and timestamps are read-only.

Clinic creation and its `OWNER` membership run in a single transaction. User IDs,
roles, and memberships supplied in the clinic body cannot change ownership. The
database enforces a nonblank name, unique user/clinic memberships, and valid roles.
Deleting a user through the Django ORM is protected while memberships reference
that user.

Owners and members can list and retrieve their clinics. Members cannot edit them
and receive 403 on PATCH. A clinic without a membership for the caller returns 404,
including for staff or superuser accounts. Missing or invalid authentication
returns 401. Memberships are checked from the database on each request; removing
a membership removes clinic access without revoking the user's authentication
token. Query parameters and client-supplied clinic headers do not grant access.

PUT and DELETE are not exposed and return 405. This step creates owner memberships
automatically; invitations, member assignment, role changes, and clinic deletion
policies require subsequent deliveries. The `MEMBER` role is supported by the
model and access rules and tested using database fixtures.

### Test with Insomnia

1. Register and sign in using the authentication endpoints above.
2. Send `POST /api/v1/clinics/` with **Auth → Bearer Token** and this JSON:

   ```json
   {"name": "Demo Clinic"}
   ```

3. Copy the returned `id`. List `/api/v1/clinics/`, then retrieve
   `/api/v1/clinics/{id}/` with the same token.
4. PATCH that clinic with `{"name":"Updated Demo Clinic"}`.
5. Register and sign in as a different user. That user's list is initially empty,
   and GET or PATCH for the first user's clinic returns 404.

## Quality checks

```sh
docker compose run --rm api python manage.py check
docker compose run --rm api python manage.py makemigrations --check --dry-run
docker compose run --rm api ruff check .
docker compose run --rm api ruff format --check .
docker compose run --rm api pytest
```

Pytest creates a separate PostgreSQL database named `test_clinicflow` by default
and removes it after the run. The local PostgreSQL container user can create this
database. Tests cover readiness against PostgreSQL, database outage handling,
public liveness without database access, and rejection of mutation requests.
Authentication tests cover required registration fields, password validation and
hashing, duplicate usernames, privilege assignment protection, login validation,
protected profile access, token revocation, inactive users, profile field exposure,
and registration and login rate limiting. Clinic tests cover required names,
atomic creation, ownership assignment, cross-clinic isolation, role permissions,
membership revocation, unsupported methods, and database constraints.

To refresh the dependency lock, run this in a clean Python 3.13 container, then
rebuild and repeat the quality checks. The resolver needs network access.

PowerShell:

```powershell
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/app" -w /app python:3.13-slim-bookworm python scripts/lock_dependencies.py
```

Linux or macOS:

```sh
docker run --rm --mount "type=bind,source=$PWD,target=/app" -w /app python:3.13-slim-bookworm python scripts/lock_dependencies.py
```

## Useful commands

```sh
docker compose logs --tail 100 api db
docker compose exec api python manage.py shell
docker compose down
```

`docker compose down` preserves the database volume. Avoid adding `--volumes`
unless you intend to delete the local database. Changing the database credentials
in `.env` does not update users in an already initialized PostgreSQL volume.

This is a local development environment. Django's development server and the
image containing development tools are appropriate for this stage; production
configuration will require a separate review.

## Repository layout

```text
apps/accounts/              Registration, Bearer login, user profile, and logout
apps/clinics/               Clinics, memberships, migrations, and access rules
apps/core/                  Health endpoints
config/                     Settings, root URLs, WSGI and ASGI entry points
scripts/lock_dependencies.py Dependency lock regeneration
tests/                      Automated tests
compose.yaml                API and PostgreSQL services
Dockerfile                  Local development image
pyproject.toml              Dependencies and quality tool configuration
requirements.lock           Resolved dependency versions
```
