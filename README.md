# ClinicFlow — Financial Automation API

ClinicFlow is a backend project for automating financial operations in clinics.
The intended workflow connects appointments, charges, simulated payment webhooks,
and asynchronous reconciliation, with data isolation between clinics.

## Product definition

ClinicFlow will centralize the financial workflow of clinics and consulting
practices: register patients and encounters, generate charges, receive simulated
payment confirmations, reconcile payments, and investigate inconsistencies.
The goal is to prevent duplicate processing, incorrect charge states, and lost
financial events while keeping operations traceable.

### Intended business workflow

1. An authenticated user creates a clinic and becomes its owner.
2. Authorized clinic users register fictional patients and their encounters.
3. An encounter generates a charge in the `PENDING` state.
4. A simulated payment provider sends a signed confirmation webhook.
5. The API validates and records the event for asynchronous processing.
6. A consumer reconciles the payment with its charge and marks it `PAID`.
7. Duplicate delivery does not create another payment. Failed processing can be
   retried, and unresolved discrepancies remain available for investigation.

Only the completed checklist items below are implemented. The financial workflow
describes the target product, rather than endpoints already available.

### Business rules and delivery checklist

Checked items represent functionality implemented and validated in this checkout.
Unchecked items are planned work; each delivery updates the checklist.

**Local foundation**

- [x] Run the API and PostgreSQL with Docker Compose and persistent database storage.
- [x] Expose liveness and database readiness endpoints.
- [x] Execute tests against PostgreSQL and enforce lint and formatting checks.
- [ ] Run those checks automatically in GitHub Actions.

**Accounts and access**

- [x] Require username, password, email, first name, and last name at registration.
- [x] Validate password strength, hash stored passwords, and prevent client-assigned administrative privileges.
- [x] Authenticate with Bearer tokens and revoke the current token on logout.
- [x] Limit registration and login requests and disable caching of authentication responses.
- [ ] Define and implement token expiration and rotation policies.

**Clinics and isolation**

- [x] Require a nonblank clinic name and create its owner membership in the same transaction.
- [x] Allow a user to belong to multiple clinics, with one membership per user and clinic.
- [x] List and retrieve only clinics linked to the authenticated user.
- [x] Allow owners to edit clinic names; members can read clinic data.
- [x] Prevent access to unrelated clinics, including through guessed IDs or administrative account flags.
- [ ] Provide controlled membership invitations, role changes, and ownership management.
- [x] Apply clinic isolation to patients, including requests under a different clinic URL.
- [ ] Apply clinic isolation to encounters, charges, payments, and financial reports as those resources are implemented.

**Patients and encounters**

- [x] Register and manage fictional patients within a clinic, with a required name and birth date.
- [ ] Record encounters and procedures linked to a patient in the same clinic.
- [ ] Reject references that combine resources from different clinics.

**Charges and payments**

- [ ] Generate encounter charges with an initial `PENDING` state.
- [ ] Store and calculate monetary values with `Decimal` and PostgreSQL numeric types.
- [ ] Define and enforce valid charge and payment state transitions.
- [ ] Mark a charge `PAID` only after its payment is successfully reconciled.
- [ ] Record discrepancies for investigation instead of silently marking inconsistent payments as successful.
- [ ] Expose clinic-scoped financial indicators.

**Events and resilience**

- [ ] Implement a simulated payment provider and verify webhook signatures.
- [ ] Persist incoming events and prevent duplicate payment creation.
- [ ] Publish events through the local Google Cloud Pub/Sub Emulator.
- [ ] Run a separate Python consumer and make reconciliation idempotent.
- [ ] Handle concurrent processing and out-of-order events without corrupting financial state.
- [ ] Add retries with backoff and a dead-letter path for persistent failures.
- [ ] Evaluate and implement a Transactional Outbox when database writes and event publication must remain consistent.

**Documentation and observability**

- [ ] Document request and response contracts with OpenAPI.
- [ ] Add structured logs and correlation identifiers across API and consumer operations.
- [ ] Document financial state rules, failure scenarios, and architectural decisions as they are implemented.

### Domain outline

| Entity | Responsibility |
| --- | --- |
| User | Account identity and authentication |
| Clinic | Boundary for access and business data |
| ClinicMembership | A user's role within a clinic |
| Patient | Fictional patient registered in a clinic |
| Encounter | A patient's attendance and associated procedures |
| Charge | Amount due and its financial state |
| Payment | Received payment and reconciliation result |
| Payment event | Provider confirmation, processing status, and duplicate protection |

Financial entity fields, event contracts, and policies for cancellation, refunds,
and payment discrepancies will be specified before their implementation.

## Current scope

The API includes Django REST Framework, PostgreSQL, Docker Compose, health
endpoints, user registration, Bearer token login, the authenticated user profile,
logout, clinic creation/listing/retrieval/name updates, owner/member permissions,
clinic access isolation, clinic-scoped patient creation/listing/retrieval/updates,
Pytest, and Ruff.
Encounters, membership management, payment integrations, the Pub/Sub
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

## Patients

All patient endpoints require Bearer authentication and a membership in the clinic
identified by the URL. Both `OWNER` and `MEMBER` can create, list, retrieve, and
edit patients. Editing the clinic itself remains restricted to owners.

| Endpoint | Request | Success |
| --- | --- | --- |
| `POST /api/v1/clinics/{clinic_id}/patients/` | JSON with `full_name`, `birth_date`, and optional contacts | `201`, patient JSON |
| `GET /api/v1/clinics/{clinic_id}/patients/` | Bearer token | `200`, array of patients in that clinic |
| `GET /api/v1/clinics/{clinic_id}/patients/{id}/` | Bearer token | `200`, patient JSON |
| `PATCH /api/v1/clinics/{clinic_id}/patients/{id}/` | JSON with fields to update | `200`, updated patient JSON |

`full_name` and `birth_date` are required at creation. Names are trimmed, cannot
be blank, and are limited to 255 characters. Birth dates use `YYYY-MM-DD`, cannot
be null or empty, and cannot be later than today's UTC date. PATCH can omit either
required field to retain its value, but cannot clear it. Invalid input returns
400 without modifying the patient. The API validates future dates; direct ORM
writes do not automatically execute serializer validation.

Email and phone are optional and stored as empty strings when omitted. Email must
have a valid format when supplied, with a maximum length of 254 characters. Phone
is text with up to 32 characters, without a regional formatting rule. Either
contact can be cleared with `""`; null is not accepted. Names and contacts are not
unique, and the same fictional person can have independent records in different
clinics.

Responses expose `id`, `clinic`, `full_name`, `birth_date`, `email`, `phone`,
`created_at`, and `updated_at`. IDs are auto-incrementing `BIGINT` values, and
`clinic` is the clinic's numeric ID. Identity, clinic, and timestamps are
read-only. Values supplied for `clinic`, `clinic_id`, identity, or timestamps
cannot change the URL's clinic assignment or transfer a patient.

The API resolves the caller's clinic membership before validating patient input.
An unrelated or nonexistent clinic returns 404 for every patient operation,
including list and create. A patient requested under another clinic also returns
404, even if the caller belongs to both clinics. Staff and superuser flags do not
bypass membership checks. Removing a membership revokes patient access on the next
request. Query parameters and clinic headers do not override the URL. Missing or
invalid Bearer authentication returns 401.

| Database column | PostgreSQL type | Nullable |
| --- | --- | --- |
| `id` | `BIGINT`, auto-generated primary key | No |
| `clinic_id` | `BIGINT`, indexed foreign key | No |
| `full_name` | `VARCHAR(255)` | No |
| `birth_date` | `DATE` | No |
| `email` | `VARCHAR(254)` | No |
| `phone` | `VARCHAR(32)` | No |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | No |

The database enforces a nonblank name and a non-null birth date. Patient references
use Django's `PROTECT` deletion policy: the ORM blocks deletion of a clinic while
patients reference it. PUT and DELETE are not exposed and return 405. Patient
deletion, encounters, medical records, search, and pagination are outside this
delivery.

### Test with Insomnia

1. Register, sign in, and create a clinic using the preceding examples. Copy its
   actual ID and use the port configured in `API_PORT`.
2. Send `POST /api/v1/clinics/{clinic_id}/patients/` with **Auth → Bearer Token**:

   ```json
   {
     "full_name": "Taylor Patient",
     "birth_date": "1995-06-15",
     "email": "taylor@example.test",
     "phone": "+55 (11) 99999-0000"
   }
   ```

3. Expect 201 and copy the patient's ID. GET the list and the patient's detail URL.
4. PATCH that detail URL with `{"phone":"(11) 1234-5678"}`. The birth date remains
   unchanged. PATCH with `{"birth_date":null}` returns 400.
5. Try creating a patient without `birth_date`, then with a future date; expect 400.
6. Register another account and clinic. Accessing the first clinic's patient URLs
   with the second account returns 404. Requesting the patient under the second
   clinic's URL also returns 404.

Member permissions and membership revocation are covered by database-backed
tests; membership assignment endpoints are not yet available.


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
membership revocation, unsupported methods, and database constraints. Patient
tests cover required birth dates, contact validation, owner/member operations,
URL clinic isolation, immutable clinic assignment, membership revocation, and
protected clinic deletion.

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
apps/patients/              Clinic-scoped patients, migrations, and access rules
config/                     Settings, root URLs, WSGI and ASGI entry points
scripts/lock_dependencies.py Dependency lock regeneration
tests/                      Automated tests
compose.yaml                API and PostgreSQL services
Dockerfile                  Local development image
pyproject.toml              Dependencies and quality tool configuration
requirements.lock           Resolved dependency versions
```
