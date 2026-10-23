# Backend conventions

Services own business rules and transactions. They raise plain exceptions from
`apps.core.exceptions` or an app's `exceptions.py`; they do not choose HTTP
responses. The configured `apps.core.api.exception_handler` translates known
business failures into the existing 400/403/404/409/503 contract and delegates
other DRF errors. Unexpected failures continue to propagate.

Serializers validate transport input. Views resolve authentication, clinic
membership, serializers and HTTP responses. Every nested clinic resource uses
`ClinicScopedViewSet`, whose cached membership lookup also serves role-based
permissions. Staff and superuser flags do not bypass membership; queryset filters
still scope the actual resource to that clinic.

Financial writers call `apps.encounters.locking.lock_encounter` inside
`transaction.atomic()` before inspecting or mutating the encounter's items and
charges. Item creation locks the catalog procedure after the encounter. Payment
processing additionally locks its provider identity before the encounter and its
event row after it. A new writer must follow the same order.

`ChargeQuerySet.active()` defines the non-cancelled charge query in one place.
Encounter item services use the related manager and their own
`EncounterItemsLocked` exception, without importing the charge model or its
exceptions. Service update arguments name the allowed change (`quantity`)
instead of accepting an unrestricted changes dictionary.

When changing these boundaries, retain endpoint status/body checks, clinic
isolation tests, transaction rollback tests and PostgreSQL concurrency tests.
