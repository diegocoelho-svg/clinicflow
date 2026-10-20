# ClinicFlow web

First local React/TypeScript/Vite interface for the existing Django API. The UI
is in Brazilian Portuguese; source and documentation are in English. It includes
registration, login, current-user identity, logout, clinic listing, creation,
selection and a read-only workspace for the selected clinic. All data must be
fictional. No cloud account or deployment is needed.

At the 2026-10-20 checkpoint, the frontend is stopped and the API/database
are paused. The corrected Docker image and dependency volume were verified
during an authorized preview, including 19 real HTTP checks with synthetic-data
cleanup. The addresses below describe the local environment; they do not imply
that a preview is currently running.

## Architecture and routes

React Router owns navigation and browser history. Nested layouts share the
authenticated shell and clinic directory; pages render the active route through
`Outlet`. The browser router is created once in `src/main.tsx`. Tests use the
same route definitions with `createMemoryRouter`.

| Route | Behavior |
| --- | --- |
| `/` | Redirects to clinics, then login if there is no in-memory session |
| `/entrar` | Login form; authenticated users are redirected to clinics |
| `/cadastro` | Registration form; success returns to a separate login |
| `/clinicas` | Protected clinic directory and selection prompt |
| `/clinicas/:clinicId` | Protected workspace; fetches detail to verify access |
| Other URLs | Recoverable not-found page with its own title and focused heading |

- `src/app/`: router, provider composition, route metadata and shared layouts.
- `src/features/auth/`: account contracts, feature error messages, memory-only
  session provider, route guard, and login/registration pages.
- `src/features/clinics/`: clinic contracts, feature error messages, directory
  provider, request hooks, components and nested workspace pages.
- `src/shared/`: generic HTTP, safe error adaptation, abortable form submissions
  and accessible UI controls. This layer does not depend on feature modules.
- `src/test/`: user interactions and review regressions against the real route
  tree, with only the HTTP transport mocked.

The HTTP layer handles status codes without knowing endpoint-specific wording.
Auth and clinic APIs map their own errors and validation keys into Portuguese;
raw server error values are never rendered. There is no persistent data cache.
Each in-flight list reconciles concurrent creations and access removals, keeping
valid clinics and reporting list failures rather than manufacturing an empty list.

## Run with Docker Compose

Use Docker Compose **2.24.4 or newer** (`!override` support). Run commands from the
repository root, using this project name and both files to keep this environment
isolated from the other development stages:

```sh
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml up -d --build --wait --wait-timeout 180
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml ps
```

First create an ignored root `.env` from `.env.example`, as described in the
repository README. Replace `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` with
independently generated local random values before starting. Do not reuse real
credentials. Keep `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`, `POSTGRES_HOST=db`
and `POSTGRES_PORT=5432`. Set `API_PORT=8008` for consistency; the overlay fixes
the API host mapping to loopback 8008 even if the base default is different.
Do not print the resolved Compose configuration: it includes environment values.

- UI: **http://127.0.0.1:5173**
- API, direct diagnostic access: http://127.0.0.1:8008
- Database: internal Compose network only.
- Project: `clinicflow-frontend`; named volumes are isolated by that project.

The `frontend` service builds from `web/Dockerfile` on Node 24 LTS, runs `npm ci`,
and waits for the API health check. The source bind mount supports Vite updates;
`node_modules` lives in a separate container volume, so a host Node installation
is optional. After changing the lockfile, update that volume and rebuild:

```sh
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml run --rm --no-deps frontend npm ci
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml up -d --build --wait
```

Stop only this environment with:

```sh
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml down
```

This preserves database data. Do not remove volumes containing records you want
to keep. The API and Vite development servers are local development services.
On this machine an unrelated IPv6 listener was found on `localhost:5173`; use
the explicit IPv4 address above and leave the unrelated process untouched.

Host `npm run dev` binds to `127.0.0.1`. Only the frontend container command
adds `--host 0.0.0.0` so Docker can reach Vite inside its network; Compose still
publishes ports 5173 and 8008 only on host loopback. A container `USER node`
change is deferred until volume ownership can be checked after runtime resumption.

## Proxy and API contracts

The browser always requests relative `/api/v1/...` URLs on port 5173. Vite proxies
`/api` to `http://api:8000` inside Compose, preserving the original loopback
Host header (`changeOrigin: false`). The API's existing allowed hosts work
without CORS changes. `API_PROXY_TARGET` is server-only, never a `VITE_` secret.
Vite's optional host workflow defaults to `http://127.0.0.1:8008`.

| Operation | Existing API contract |
| --- | --- |
| Register | `POST /api/v1/auth/register/` with `username`, `password`, `email`, `first_name`, `last_name`; returns a user, without a token |
| Login | `POST /api/v1/auth/token/` with `username`, `password`; returns `{token}` |
| Identity | `GET /api/v1/auth/me/` with opaque `Authorization: Bearer ...` |
| Logout | `POST /api/v1/auth/logout/`; revokes the current token and returns 204 |
| Clinics | `GET /api/v1/clinics/` returns an array of this user's clinics |
| Create | `POST /api/v1/clinics/` with trimmed `name`, at most 255 characters; creates owner membership |
| Select | `GET /api/v1/clinics/{id}/` confirms current access; 403/404 clears selection and removes the inaccessible list entry |

User fields are `id`, `username`, `email`, `first_name`, `last_name`. Clinic fields
are `id`, `name`, `created_at`, `updated_at`. Responses expose no membership role,
so this slice never infers ownership or offers role-dependent edit controls.
Server-side membership checks enforce isolation; selection never grants access.
List refresh clears the previous selection so it must be checked again.

## Sessions and safe states

Tokens, user identity and clinic detail exist only in React memory. The selected
clinic ID is a route parameter, not an authorization claim or a stored session. There is
no local/session storage, cookie authentication, JWT decoding or credential
logging. Reloading, closing or opening another tab requires login again. Refresh
does **not** revoke the server token: the current API has one token per user,
reuses it on login and has no expiration/rotation policy. Explicit logout revokes
that token for all clients sharing it.

Logout immediately removes local session and clinic state, then requests server
revocation. If the network fails, a Portuguese message explains that revocation
was not confirmed; the local session remains cleared. An authenticated 401 also
clears identity, token and selected clinic. Session generations, request ordering
and abort signals prevent late responses restoring old session/clinic state.
Requests time out after 15 seconds and are never automatically retried.

New login requests wait for a pending logout in the same session provider before
requesting a token: otherwise Django's token reuse would let a late logout revoke
the new session. Leaving the login form cancels that queued submission. This
ordering covers the pending local request only. A network failure or timeout
cannot prove whether Django has finished processing logout; delayed remote
revocation remains possible and a later 401 requires login again. The client
does not claim to solve this without a backend token lifecycle change.

Validation errors become Portuguese field messages linked with `aria-describedby`;
unknown server text and HTML are not rendered. Invalid login remains generic.
429 instructs the user to wait; Django limits registration and login separately
to 10/minute per client IP. Proxy clients share the proxy's address for this
local rate limit. Failed requests preserve deliberate retry controls; clinic
creation is disabled while the list cannot be read. No financial metrics or
unimplemented navigation actions are shown.

Route changes update the document title and focus the active heading. Error
alerts take priority so a session-expiry message keeps focus after redirecting
to login. Authentication pages each have one level-one heading; the decorative
brand text is not a heading. Clinic selection focuses its loaded detail heading,
and returning to the collection focuses the workspace heading. Field IDs and
their label/description associations stay stable.

## Dependencies

All direct versions are exact; `package-lock.json` records transitive versions.
React, React DOM and React Router are runtime dependencies. The development stack is
Vite 8, its official React plugin 6, TypeScript 7, Vitest 5, jsdom and Testing
Library, with Prettier for consistent source formatting. Node 24 is compatible
with their declared engines/peers. Versions were
verified against the public npm registry and official documentation:
[React versions](https://react.dev/versions),
[React Router routing](https://reactrouter.com/start/data/routing),
[Vite guide](https://vite.dev/guide/),
[Vitest guide](https://vitest.dev/guide/),
[React Testing Library](https://testing-library.com/docs/react-testing-library/intro/),
[Node release policy](https://nodejs.org/en/about/previous-releases).
No additional state library, component framework, external font, icon package or
remote asset service is used.

## Validation commands

Container checks, from the repository root, **only after runtime resumption is
authorized**:

```sh
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T frontend npm run typecheck
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T frontend npm test
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T frontend npm run build
```

Optional host workflow with Node 24, from `web/`:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run format:check
npm run dev
```

The pnpm command for the full interaction suite, from `web/`, is:

```sh
pnpm exec vitest run --no-cache --silent --no-fsModuleCache --pool=threads --maxWorkers=1
```

When only npm is available, run the repository's local Vitest without allowing
npm to install a missing package:

```sh
npm exec --no -- vitest run --no-cache --silent --no-fsModuleCache --pool=threads --maxWorkers=1
```

Both commands have passed on this host; the npm command is the latest result in
the verification table below. The default runner previously timed out during
worker bootstrap without executing tests. The cache-free command disables both
caches; the exact cause of the earlier startup timeouts is still unknown. No
package scripts or dependencies were changed to work around the runner.

The interaction suite mocks HTTP only at the transport boundary. It covers exact
registration payloads, separate login, identity/Bearer requests, invalid login,
logout and failed revocation, authenticated 401 cleanup, stale login/detail
responses, clinic selection and 404, list retry, clinic creation and safe field
errors. Review regressions also cover deferred logout/login ordering and abort,
list/detail/creation races, feature-specific 404 wording, registration validation,
session-expiry and stale-form focus, heading hierarchy, workspace navigation,
render-error boundary focus/title and not-found titles. The suite contains
**32 tests in 2 files**. No mock responses ship in the application.

Real HTTP smoke check through the Vite proxy, in PowerShell, **when services may
be resumed**:

```powershell
Get-Content -LiteralPath web/scripts/smoke.py -Raw | docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T api python manage.py shell
```

Linux/macOS equivalent:

```sh
docker compose -p clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T api python manage.py shell < web/scripts/smoke.py
```

The smoke check generates random credentials in memory and calls registration,
invalid/successful login, identity, clinic creation/list/detail, blank-name
validation, a second user's isolation, logout and revoked-token rejection. It
uses Django ORM only in `finally` to remove the exact synthetic users and their
exclusive clinics, memberships and tokens; it refuses to delete shared/foreign
clinics. Never run this against another Compose project or real records.

## Manual review

Use this checklist when reviewing a running local preview. Coordinator visual,
responsive and screen-reader QA remain unverified; frontend feedback will be
addressed before merge:

1. Open http://127.0.0.1:5173 at desktop and narrow phone widths. Navigate with
   Tab/Shift+Tab and check visible focus, readable labels and error messages.
2. Create a fictional account using all five fields. Check native email/required
   validation and a weak-password or duplicate-username server error. Registering
   should return to the login form, clear the password and explain the next step.
3. Try an invalid login, then the correct login. Confirm profile identity and an
   empty clinic state. Create two fictional clinics and open each workspace.
4. Refresh the list, then select again. In browser network tools, confirm requests
   go to port 5173 `/api/...`, with detail requested at each selection. Do not
   copy or screenshot passwords or Authorization headers.
5. Click Sair. Confirm login returns and clinic/profile data disappears. If a
   second login is submitted before logout finishes, confirm the token request
   waits for it. Login again, reload a clinic URL and verify login is required
   with no previous identity or clinic restored.
6. For 401 cleanup, revoke the token from another client then refresh the clinic
   list in this tab. Simulate offline/503 in developer tools to inspect connection
   errors and retry. Do not create an automatic retry loop around POST requests.
7. Remove only your created synthetic records via Django ORM, deleting your
   synthetic clinics before the corresponding users. The current API has no
   DELETE clinic endpoint; use the automated smoke for self-cleaning checks.

## Verification record

Current correction validation date: 2026-10-19. Host Node: 24.21.0.

| Check | Result and provenance |
| --- | --- |
| Host `npm run build` | Passed typecheck and production bundle after the review corrections |
| Host `npm run format:check` | Passed after formatting the corrections; final check recorded in `VALIDATION.md` |
| npm local cache-free Vitest command above | Final snapshot: 32 tests in 2 files passed, exit 0, 33.98 seconds; `npm exec --no --` used the local Vitest without installing packages |
| Dependency audit | Coordinator independently ran `npm audit --json --ignore-scripts --registry=https://registry.npmjs.org`: exit 0, zero known vulnerabilities in 153 dependencies; no dependency additions in this correction |
| Ruff 0.17.0 check/format on `scripts/smoke.py` | Offline host attempt unavailable because the declared tool is not cached; no container was started or tool downloaded |
| Corrected Docker/HTTP validation | Frontend image rebuilt and dependency volume synchronized; all three services healthy, UI and TypeScript entry/router modules returned HTTP 200, and 19 real API checks passed through Vite with synthetic-data cleanup |
| Visual/responsive and screen-reader validation | Coordinator browser automation unavailable; frontend feedback remains open |
| Runtime at the 2026-10-20 checkpoint | Frontend stopped; API and database paused; data and volumes preserved |

Earlier validation on 2026-10-17, before the Router/review corrections: Docker
builds and `npm ci` succeeded, all three services were healthy, loopback mappings
were confirmed and generated `web/` paths were absent from the API image.
`scripts/smoke.py` passed **19 real HTTP requests** through Vite to Django,
including registration, login, identity, clinic creation/list/detail, outsider
isolation and logout/401. It removed its two synthetic users and two clinics,
including their memberships and tokens, in `finally`. Host IPv4 UI returned
200 and unauthenticated proxy access returned 401. Those are historical results,
not a new runtime verification of the corrected code. Orca browser tab discovery
worked but the attempted snapshot failed with `browser_tab_not_found`; visual,
responsive and screen-reader review remain pending. DOM focus/accessibility
regressions are automated interaction checks, not browser or screen-reader QA.

## Changed files and limits

The exact delivered file inventory is below; `VALIDATION.md` records commands,
results and the same ownership boundaries. Generated `node_modules`, `dist`,
tool caches, screenshots and credentials are ignored and excluded.

```text
.dockerignore
compose.frontend.yaml
web/
  .dockerignore
  .gitignore
  .prettierrc.json
  Dockerfile
  README.md
  VALIDATION.md
  index.html
  package.json
  package-lock.json
  tsconfig.json
  vite.config.ts
  scripts/smoke.py
  src/
    main.tsx
    styles.css
    app/
      App.tsx
      router.tsx
      layouts/RouteLayout.tsx
      layouts/WorkspaceLayout.tsx
      pages/NotFoundPage.tsx
      pages/RouteErrorPage.tsx
    features/
      auth/
        AuthProvider.tsx
        RequireSession.tsx
        api.ts
        context.ts
        errors.ts
        types.ts
        useAuth.ts
        layouts/AuthLayout.tsx
        pages/LoginPage.tsx
        pages/RegisterPage.tsx
      clinics/
        ClinicDirectoryProvider.tsx
        api.ts
        context.ts
        errors.ts
        types.ts
        components/ClinicDetails.tsx
        components/ClinicDirectory.tsx
        components/CreateClinicForm.tsx
        components/IdentityCard.tsx
        hooks/useClinic.ts
        hooks/useClinicAccess.ts
        layouts/ClinicsLayout.tsx
        pages/ClinicIndexPage.tsx
        pages/ClinicWorkspacePage.tsx
    shared/
      api/errors.ts
      api/http.ts
      hooks/useAsyncForm.ts
      ui/Brand.tsx
      ui/Field.tsx
      ui/Notice.tsx
    test/
      App.test.tsx
      review-regressions.test.tsx
      setup.ts
```

A coordinator
approved exception adds exactly five generated `web/` exclusions to root
`.dockerignore`; no API contracts or backend source changed. The ignored local
`.env` contains generated development values and is never part of the delivery.

The branch remains `clinicflow-frontend` in its dedicated worktree. The user
requested the application directory name `web/`; the reserved Compose project,
service and overlay name remain stable for coordination. Frontend work stays
on this branch while backend work progresses separately. Merge is deferred until
frontend feedback has been addressed. Patients, encounters, procedures, charges, payments, clinic
editing and memberships remain outside this first interface. Production hosting,
token expiry, automated persistent sessions and password recovery are not
implemented.
