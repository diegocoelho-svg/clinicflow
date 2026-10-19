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
- [x] Run those checks automatically in GitHub Actions.
- [x] Provide optional Discord notifications for PR events and CI results.

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
- [x] Apply clinic isolation to encounters, including requests under a different clinic URL.
- [ ] Apply clinic isolation to charges, payments, and financial reports as those resources are implemented.

**Patients and encounters**

- [x] Register and manage fictional patients within a clinic, with a required name and birth date.
- [x] Record completed encounters linked to a patient in the same clinic.
- [x] Manage a clinic procedure catalog with nonnegative BRL prices and activation status.
- [x] Link procedures to encounters with positive quantities, unique procedure items, and historical name/price snapshots.
- [x] Reject encounter patient assignments that combine resources from different clinics.
- [ ] Reject cross-clinic references in charges, payments, and other future resources.

**Charges and payments**

- [ ] Generate encounter charges with an initial `PENDING` state.
- [x] Store procedure prices with `Decimal` and PostgreSQL numeric types.
- [x] Calculate encounter item totals with `Decimal` using the stored unit price.
- [ ] Calculate complete encounter and charge totals with `Decimal` and PostgreSQL numeric types.
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
| Procedure | Clinic catalog entry with a BRL unit price and activation status |
| EncounterItem | Procedure reference, quantity, historical name and unit price, and calculated item total |
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
completed encounter creation/listing/retrieval/updates, a clinic procedure catalog
with BRL prices, owner-only catalog management, encounter items with historical
prices and quantities, Pytest, Ruff, and GitHub Actions.
Charges, membership management, payment integrations, the Pub/Sub
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
deletion, medical records, search, and pagination are outside this delivery.
Encounter endpoints are documented in the following section.

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


## Encounters

All encounter endpoints require Bearer authentication and a current membership in
the URL's clinic. Both `OWNER` and `MEMBER` can register, list, retrieve, and
partially update completed encounters.

| Endpoint | Request | Success |
| --- | --- | --- |
| `POST /api/v1/clinics/{clinic_id}/encounters/` | JSON with `patient`, `performed_at`, and `description` | `201`, encounter JSON |
| `GET /api/v1/clinics/{clinic_id}/encounters/` | Bearer token | `200`, array of encounters in that clinic |
| `GET /api/v1/clinics/{clinic_id}/encounters/{id}/` | Bearer token | `200`, encounter JSON |
| `PATCH /api/v1/clinics/{clinic_id}/encounters/{id}/` | JSON with `performed_at` and/or `description` | `200`, updated encounter JSON |

Creation requires all three input fields. `patient` is the numeric ID of a patient
in the same clinic. A nonexistent patient or a patient from another clinic returns
400, including when the caller belongs to both clinics. The serializer restricts
its patient lookup to the clinic authorized by the ViewSet.

`performed_at` represents an already completed encounter and must not be in the
future. Timestamps accept ISO 8601 input, including timezone offsets, and are
returned in UTC. `description` is trimmed text and cannot be null, empty, or only
whitespace. PATCH can omit fields to retain their values but cannot clear required
fields. Validation failures return 400 without modifying the record.

The patient is fixed after creation. Supplying a different `patient` on PATCH
returns 400, even if the replacement belongs to the same clinic. Resubmitting the
same patient ID is allowed. The clinic is determined by the URL and cannot be
changed by the body. Client-supplied `clinic_id` and `patient_id` fields do not
override these rules. Identity, clinic, and timestamps are read-only.

Responses contain `id`, `clinic`, `patient`, `performed_at`, `description`,
`created_at`, and `updated_at`. Lists contain only encounters in the URL's clinic,
ordered by ID. An unrelated or nonexistent clinic returns 404, including for list
and create. An encounter requested under another clinic also returns 404, even
when the caller belongs to both clinics. Staff and superuser flags do not bypass
membership checks. Query parameters and clinic headers do not override the URL.
Removing a membership revokes access on the next request. Missing or invalid
Bearer authentication returns 401.

| Database column | PostgreSQL type | Nullable |
| --- | --- | --- |
| `id` | `BIGINT`, auto-generated primary key | No |
| `clinic_id` | `BIGINT`, indexed foreign key | No |
| `patient_id` | `BIGINT`, indexed foreign key | No |
| `performed_at` | `TIMESTAMP WITH TIME ZONE` | No |
| `description` | `TEXT` | No |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | No |

The migration enforces non-null fields, foreign keys, and a nonblank description.
Patient and clinic references use Django's `PROTECT` deletion policy. The ORM
blocks deletion of a referenced patient or clinic. Future-time validation,
same-clinic patient selection, and fixed-patient updates are API rules; direct ORM
writes do not automatically run serializer validation. The database does not have
a constraint comparing the clinic IDs of two different tables.

A patient can have multiple encounters. PUT and DELETE on encounters return 405.
Encounter items are managed through the nested endpoints documented below.
Scheduling, charges, financial states, search, and pagination remain planned. Encounter edit rules will be revisited when charges depend on
encounter data.

### Test with Insomnia

1. Register, sign in, create a clinic, and register a patient using the preceding
   examples. Use the port configured in `API_PORT` and the actual IDs returned.
2. Send `POST /api/v1/clinics/{clinic_id}/encounters/` with **Auth → Bearer Token**:

   ```json
   {
     "patient": 1,
     "performed_at": "2020-01-01T10:00:00-03:00",
     "description": "Routine consultation"
   }
   ```

   Replace `1` with your patient's ID. Expect 201, with the timestamp normalized
   to `2020-01-01T13:00:00Z`.
3. GET the list and `/api/v1/clinics/{clinic_id}/encounters/{id}/`.
4. PATCH the detail URL with `{"description":"Corrected consultation"}`. The
   patient and performed time remain unchanged.
5. Omit `patient`, send an empty description, or use a future performed time in a
   creation request; each returns 400. A patient from another clinic also returns
   400.
6. PATCH with a different patient ID from the same clinic; expect 400.
7. Access the encounter using an unrelated account or under another clinic URL;
   expect 404.

Member permissions and membership revocation are covered by database-backed
tests; membership assignment endpoints are not yet available.

## Procedures

The procedure catalog belongs to a clinic and requires Bearer authentication.
`OWNER` can create and partially update procedures; `MEMBER` can only list and
retrieve them. Both roles can read active and inactive entries. The full catalog
remains visible so deactivated procedures can be inspected and reactivated.

| Endpoint | Request | Success | Access |
| --- | --- | --- | --- |
| `POST /api/v1/clinics/{clinic_id}/procedures/` | JSON with `name`, `unit_price`, and optional `is_active` | `201`, procedure JSON | Owner |
| `GET /api/v1/clinics/{clinic_id}/procedures/` | Bearer token | `200`, array of procedures | Owner or member |
| `GET /api/v1/clinics/{clinic_id}/procedures/{id}/` | Bearer token | `200`, procedure JSON | Owner or member |
| `PATCH /api/v1/clinics/{clinic_id}/procedures/{id}/` | JSON with fields to change | `200`, updated procedure JSON | Owner |

`name` is required, trimmed, nonblank, and limited to 255 characters. Names are
not unique; procedures are identified by their IDs. `unit_price` is required and
always represents BRL. Currency selection is not an input. Send monetary amounts
as decimal strings such as `"125.50"`; responses use strings with two decimal
places. The application stores amounts as Python `Decimal` and PostgreSQL
`NUMERIC(12,2)`, with at most ten integer digits and two fractional digits. Extra
fractional digits, non-finite values, negative amounts, and values exceeding
`9999999999.99` return 400. Amounts are validated without silently rounding them.

Zero is valid and represents a free procedure. Discounts will be modeled
separately when procedures are linked to encounters and charges. A future 100%
discount will preserve the original price rather than overwrite the catalog.

`is_active` defaults to true and can be set to false or true by an owner.
Deactivation retains the procedure and its ID. PATCH can omit fields to retain
their values, but cannot clear required fields. Responses expose `id`, `clinic`,
`name`, `unit_price`, `is_active`, `created_at`, and `updated_at`. ID, clinic, and
timestamps are read-only. The clinic is assigned from the URL; body values for
`clinic` or `clinic_id` cannot transfer an entry.

An unrelated or nonexistent clinic returns 404 for every operation. A procedure
requested under another clinic also returns 404 when the caller is an owner of
both clinics. Members attempting to create or update in their clinic receive
403, including when the body is invalid. Authentication is checked first; missing
or invalid Bearer tokens return 401. Administrative flags and clinic headers do
not bypass membership checks. Membership revocation removes access on the next
request; the request's cached membership is not shared across requests.

| Database column | PostgreSQL type | Nullable |
| --- | --- | --- |
| `id` | `BIGINT`, auto-generated primary key | No |
| `clinic_id` | `BIGINT`, indexed foreign key | No |
| `name` | `VARCHAR(255)` | No |
| `unit_price` | `NUMERIC(12,2)` | No |
| `is_active` | `BOOLEAN` | No |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | No |

The migration enforces a nonblank name and a finite price between zero and 9999999999.99, including protection against direct SQL writes of NaN. Django's `PROTECT`
policy prevents deleting a clinic through the ORM while procedures reference it.
PUT and DELETE on catalog procedures return 405. The catalog supplies encounter
items documented below. Discounts, charges, search, and pagination remain planned.

### Test with Insomnia

1. Register, sign in, and create a clinic using the preceding examples. Use the
   port configured in `API_PORT` and the actual clinic ID returned.
2. As the owner, send `POST /api/v1/clinics/{clinic_id}/procedures/` with
   **Auth → Bearer Token**:

   ```json
   {
     "name": "Routine consultation",
     "unit_price": "125.50"
   }
   ```

3. Expect 201 with `unit_price: "125.50"` and `is_active: true`. GET the list and
   `/api/v1/clinics/{clinic_id}/procedures/{id}/`.
4. PATCH the detail URL with `{"unit_price":"0.00"}`; zero is accepted. A
   negative price or `"1.001"` returns 400 without modifying the procedure.
5. PATCH with `{"is_active":false}`, then GET the list and detail to confirm the
   entry remains. PATCH with `{"is_active":true}` reactivates it.
6. Access with an unrelated account; expect 404. Members can read but receive
   403 on POST or PATCH. Membership assignment is exercised by database-backed
   tests because member-management endpoints are not available yet.

## Encounter items

Encounter items record the procedures used in an encounter, their quantities, and
the catalog name and unit price captured when each item is created. Both `OWNER`
and `MEMBER` can create, list, retrieve, update quantities, and remove items in a
clinic to which they belong. All prices represent BRL.

| Endpoint | Request | Success |
| --- | --- | --- |
| `POST /api/v1/clinics/{clinic_id}/encounters/{encounter_id}/items/` | JSON with `procedure` and optional `quantity` | `201`, item JSON |
| `GET /api/v1/clinics/{clinic_id}/encounters/{encounter_id}/items/` | Bearer token | `200`, array of that encounter's items |
| `GET /api/v1/clinics/{clinic_id}/encounters/{encounter_id}/items/{id}/` | Bearer token | `200`, item JSON |
| `PATCH /api/v1/clinics/{clinic_id}/encounters/{encounter_id}/items/{id}/` | JSON with `quantity` | `200`, updated item JSON |
| `DELETE /api/v1/clinics/{clinic_id}/encounters/{encounter_id}/items/{id}/` | Bearer token | `204`, empty body |

`procedure` is required and must identify an active procedure in the encounter's
clinic. Missing, invalid, inactive, or foreign-clinic procedures return 400.
`quantity` defaults to 1 and must be an integer between 1 and 2147483647. Zero,
negative, null, fractional, or oversized quantities return 400. A procedure may
appear only once per encounter; duplicate creation returns 400. Use quantity to
record repeated units, or use the same procedure in a different encounter.

The server copies `procedure_name` and `unit_price` from the catalog. Request
values for those fields cannot set the price or overwrite the name. Item creation
uses `transaction.atomic()` and `select_for_update()` to recheck the current
procedure and copy its values under a row lock. The database enforces unique
encounter/procedure pairs; a concurrent duplicate conflict is returned as 400.
Unrelated database integrity errors are not misreported as duplicates.

Changing or deactivating the catalog entry does not modify existing snapshots.
The item can still be read, have its quantity adjusted, or be removed after the
procedure becomes inactive. Its procedure reference is fixed: PATCH with a
different procedure returns 400. Resubmitting the same ID is allowed, including
after catalog deactivation. Read-only body fields cannot transfer the item to
another encounter or clinic.

Responses contain `id`, `encounter`, `procedure`, `procedure_name`, `quantity`,
`unit_price`, `total`, `created_at`, and `updated_at`. Unit price and total are
decimal strings with two fractional digits. `total` is computed with Python
`Decimal` as quantity times the stored unit price; it is not a database column.
Zero-price procedures produce zero totals. The total serializer accommodates
22 digits to represent the full product of supported quantities and prices.

Removing an item returns 204; subsequent retrieval returns 404. If its procedure
is active, it can then be added again, producing a new ID and a fresh snapshot
of the current catalog values. Invalid PATCH requests leave the item unchanged.
PUT returns 405.

Both the clinic and encounter in the URL are checked before input validation.
An unrelated clinic, an encounter under another clinic, or an item under another
encounter returns 404, including when the caller belongs to both clinics. Missing
or invalid Bearer authentication returns 401. Administrative flags, query
parameters, and clinic headers do not bypass these rules. Removing a membership
revokes access on the next request without revoking the authentication token.

| Database column | PostgreSQL type | Nullable |
| --- | --- | --- |
| `id` | `BIGINT`, auto-generated primary key | No |
| `encounter_id` | `BIGINT`, indexed foreign key | No |
| `procedure_id` | `BIGINT`, indexed foreign key | No |
| `procedure_name` | `VARCHAR(255)` | No |
| `quantity` | `INTEGER`, positive constraint, default 1 in Django | No |
| `unit_price` | `NUMERIC(12,2)` | No |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | No |

Database constraints enforce a positive quantity, a nonblank name snapshot, a
finite nonnegative price, and uniqueness per encounter/procedure. Django's
`PROTECT` policy blocks ORM deletion of referenced encounters and procedures.
The item's clinic is derived from its encounter. Same-clinic selection and
snapshot copying are API rules; direct ORM writes do not automatically execute
serializer validation. Charge generation, discounts, complete encounter totals,
and restrictions after billing will be specified in subsequent deliveries.

### Test with Insomnia

1. Register and sign in, then create a clinic, patient, encounter, and active
   catalog procedure. Use `API_PORT` and the actual returned IDs.
2. POST the items collection URL with **Auth → Bearer Token**:

   ```json
   {
     "procedure": 1,
     "quantity": 2
   }
   ```

   Replace `1` with the procedure ID. A procedure priced at `"125.50"` returns
   `unit_price: "125.50"` and `total: "251.00"`.
3. GET the list and detail, then PATCH the item with `{"quantity":3}`. The total
   becomes `"376.50"`; the stored name and unit price remain the same.
4. As the owner, change the catalog name, price, and active flag. GET the item
   again: its original name and unit price remain unchanged.
5. Try quantity zero, a different procedure on PATCH, and a duplicate POST;
   expect 400. A procedure from another clinic also returns 400.
6. DELETE the item; expect 204. Retrieving that ID now returns 404. Re-adding an
   active procedure captures its current catalog values.
7. An unrelated user or an incorrect clinic/encounter URL returns 404.

## Continuous integration

The [CI workflow](.github/workflows/ci.yml) runs on pull requests targeting `main`,
pushes to `main`, and manual dispatches. It builds the existing Docker image and
starts the API and PostgreSQL through the same `compose.yaml` used locally. The
startup command applies migrations to a fresh database; Compose waits for both
services to become healthy before running the checks.

The `Backend checks` job runs Django system checks, migration consistency,
Ruff lint and formatting checks, the PostgreSQL-backed Pytest suite, and
`python -m pip check`. A failed command fails the job. Container logs are shown
on failure, and a final cleanup step always attempts to remove that run's
containers, network, and database volume.

Each run has a unique Compose project name and disposable development-only
credentials. It does not need a committed `.env`, application secrets, or a
payment provider. The workflow token has read-only repository contents access,
checkout does not retain credentials, and the checkout action is pinned to a
verified commit. New runs cancel older runs for the same workflow and Git ref;
the job has a 20-minute timeout.

To validate on GitHub, open a PR targeting `main` and inspect **Checks**, or open
**Actions > CI** after a push to `main`. Once the workflow is present on the
default branch, **Run workflow** also starts a manual run. Making this check
mandatory for merging is a separate repository ruleset or branch-protection
setting; adding the workflow does not change repository policies.

References: [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [checkout action](https://github.com/actions/checkout).

### Discord notifications

The separate [Discord notifications workflow](.github/workflows/discord.yml)
sends selected repository events through an incoming Discord webhook. It reports
notifications separately from the `CI` workflow, so a Discord outage does not
change the result of the backend checks.

| Event | Notification |
| --- | --- |
| PR targeting `main` is opened or reopened | PR number, title, author, branches and link |
| Draft PR becomes ready for review | Review-ready status and PR link |
| PR is merged or closed | Merge/closure status, author and PR link |
| `CI` fails, times out or needs action | Result, branch, commit, attempt and run link, including fork PR failures |
| `CI` succeeds on this repository's `main` after a push or manual run | Confirmation that the main branch passed |
| Manual notification workflow run | Connection-test message |

Cancelled, skipped and neutral CI runs are ignored. Successful PR runs and
ordinary PR edits/commits do not send messages. Messages are in Portuguese and
disable all user, role and everyone mentions. PR bodies, logs and artifacts are
not sent. Metadata is escaped and bounded before JSON serialization.

Setup:

1. Create an incoming webhook for the intended Discord text channel.
2. In this GitHub repository, open **Settings > Secrets and variables > Actions**
   and add a repository secret named **`DISCORD_WEBHOOK_URL`** containing that URL.
   Keep the URL out of source, `.env.example`, PR descriptions and chat messages.
3. Merge the workflows into the default branch. These notification events use
   the default-branch workflow; they will not notify the initial opening of the
   PR that first introduces this integration.
4. Open **Actions > Discord notifications > Run workflow** and confirm the test
   message arrives. Missing secrets produce an explicit skip message in Actions;
   they do not fail the CI or send any request.

The sender accepts HTTPS `discord.com` webhook URLs, including an optional
`thread_id` query for an existing thread. It requests `wait=true` to confirm
delivery, uses a 10-second timeout and refuses redirects. Failed deliveries mark
only the notification workflow as failed. HTTP response bodies, exception text
and the secret URL are never printed. POSTs are not automatically retried because
an uncertain response may already have produced a message.

PR metadata is handled with `pull_request_target`, and CI results with
`workflow_run`. The job has read-only repository permissions and checks out only
this repository's default branch with a pinned action. It never executes PR-head
code or consumes PR artifacts, caches, or interpolated shell commands. This lets
fork events be reported without exposing the webhook to their code. The Python
sender uses the standard library and does not require a Discord bot account.

Unit tests cover event selection, fork failures, payload bounds, mention
suppression, endpoint restrictions, HTTP delivery construction and secret-safe
failure handling without contacting Discord. A real delivery can be verified
only after the secret is configured and the workflow is on the default branch.

References: [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
and [Discord webhooks](https://docs.discord.com/developers/resources/webhook).


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
protected clinic deletion. Encounter tests cover same-clinic patient selection,
fixed patient assignment, performed time validation, owner/member operations,
clinic isolation, membership revocation, and protected patient deletion. Procedure
tests cover exact decimal prices, free procedures, negative-price rejection,
owner/member permissions, activation changes, clinic isolation, and database constraints.
Encounter item tests cover stored price/name snapshots, exact totals, positive
quantities, removal, nested access isolation, catalog revalidation, database
constraints, and concurrent duplicate requests.

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
.github/workflows/ci.yml     Automated backend checks with Docker Compose
.github/workflows/discord.yml PR and CI notifications through a secret webhook
apps/accounts/              Registration, Bearer login, user profile, and logout
apps/clinics/               Clinics, memberships, migrations, and access rules
apps/core/                  Health endpoints
apps/encounters/            Completed encounters, procedure items, snapshots, and access rules
apps/patients/              Clinic-scoped patients, migrations, and access rules
apps/procedures/            BRL procedure catalog, migrations, and owner permissions
config/                     Settings, root URLs, WSGI and ASGI entry points
scripts/lock_dependencies.py Dependency lock regeneration
scripts/notify_discord.py    Selected GitHub event delivery to Discord
tests/                      Automated tests
compose.yaml                API and PostgreSQL services
Dockerfile                  Local development image
pyproject.toml              Dependencies and quality tool configuration
requirements.lock           Resolved dependency versions
```
