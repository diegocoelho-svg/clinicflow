# ClinicFlow — Financial Automation API

ClinicFlow is a backend project for automating financial operations in clinics.
The intended workflow connects appointments, charges, simulated payment webhooks,
and asynchronous reconciliation, with data isolation between clinics.

## Current scope

The foundation includes Django REST Framework, PostgreSQL, Docker Compose,
liveness and readiness endpoints, Pytest, and Ruff. Business endpoints,
authentication flows, payment integrations, the Pub/Sub emulator, and its consumer
will be added in subsequent development steps.

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
apps/core/                  Health endpoints
config/                     Settings, root URLs, WSGI and ASGI entry points
scripts/lock_dependencies.py Dependency lock regeneration
tests/                      Automated tests
compose.yaml                API and PostgreSQL services
Dockerfile                  Local development image
pyproject.toml              Dependencies and quality tool configuration
requirements.lock           Resolved dependency versions
```
