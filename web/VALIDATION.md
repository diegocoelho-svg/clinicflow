# Frontend delivery and review corrections

Task: `task_300cc3d02e9e` · Dispatch: `ctx_90e76c8738fa`.
Branch/worktree: `clinicflow-frontend`, based on `c76f37f`.
Review correction date: 2026-10-19. Host Node: 24.21.0.
Branch checkpoint: 2026-10-20; frontend merge deferred for further feedback.

The application is in `web/`, as requested by the user, with React Router 8.4.0,
protected nested routes and modules for app composition, auth, clinics and shared
HTTP/UI. Registration, login, current-user identity, logout, clinic listing,
creation and selection call the existing Django API. No backend contracts,
dependencies, root Dockerfile, root Compose file or workflows changed during
the review corrections. This checkpoint keeps frontend work isolated from
backend development; frontend feedback will be addressed before merge.

## Confirmed review fixes

1. Host Vite defaults to `127.0.0.1`. The web Dockerfile explicitly adds
   `--host 0.0.0.0` inside the container; published Compose ports remain loopback.
2. AuthProvider waits for a pending logout before issuing another token request.
   Abort/generation guards prevent a cancelled queued login establishing a
   session. Logout still clears local state immediately. Network failure/timeout
   cannot confirm remote revocation order; that limitation is documented.
3. Each pending clinic list reconciles concurrent additions/removals using its
   own Map/Set. A detail 404 removes that clinic while preserving valid returned
   clinics, completed creations and list failures. No refresh polling was added.
4. Shared HTTP handles generic status errors. Auth and clinics supply their own
   messages/validation rules, so a missing login endpoint never reports a
   missing clinic. Raw server values are not rendered.
5. Route titles come from route metadata, including the not-found page. Actual
   authentication pages own the level-one heading; decorative copy is a
   paragraph. Workspace/clinic navigation focuses its heading, while a
   session-expiry alert keeps focus after the redirect. Field IDs are unchanged.
6. The English README now describes the real architecture, dependencies,
   loopback URL, test commands, historical HTTP validation and paused runtime.
   The smoke script's final print call received only a formatting correction;
   its behavior is unchanged.

## Current host checks

Run from `web/`:

```sh
npm run build
npm run format:check
npm exec --no -- vitest run --no-cache --silent --no-fsModuleCache --pool=threads --maxWorkers=1
```

- `npm run build`: **exit 0**, including `tsc --noEmit` and Vite production
  build. 130 modules transformed; JS 338.40 kB / gzip 105.65 kB, CSS 15.89 kB /
  gzip 4.40 kB. Build output is ignored by Git.
- `npm run format:check`: **exit 0**, all matched files use Prettier formatting.
- npm local cache-free Vitest: **32 tests in 2 files passed, exit 0, 33.98 seconds**
  on the final source snapshot. `npm exec --no --` used the installed local Vitest
  without attempting an install. An earlier pnpm invocation passed 30 tests in
  18.32 seconds before the final two review regressions were added.
- The 15 added regression cases exercise deferred logout/login ordering and
  cancelled queued login; initial-list/detail-404, list-error and creation races;
  auth/clinic/generic 404 messages and registration validation; actual DOM focus,
  heading levels, workspace navigation, stale form-alert focus, route error
  boundary title/focus and not-found titles. The original 17
  cases retain successful/invalid login, registration, logout/401 cleanup,
  protected/direct routes, history navigation and stale-response coverage.
- `git diff --check`: **exit 0**. Only the authorized root ignore file, overlay
  and `web/` appear in the delivered file inventory.

Before these corrections, the coordinator independently verified all 17 prior
tests with the same cache-free command (exit 0, 59.40 seconds), and independently
ran `npm audit --json --ignore-scripts --registry=https://registry.npmjs.org`:
exit 0, zero known vulnerabilities in 153 dependencies. Dependencies were not
added or updated in these corrections. Earlier default Vitest fork/thread
attempts executed zero tests because worker bootstrap timed out. Successful
independent Node IPC/thread probes rule out blaming Node worker creation in
general; the precise earlier Vitest/cache cause remains undetermined.

Offline-only Ruff checks from the repository root:

```sh
uv tool run --offline --from ruff==0.17.0 ruff check web/scripts/smoke.py
uv tool run --offline --from ruff==0.17.0 ruff format --check web/scripts/smoke.py
```

Both returned exit 1 **before lint/format execution** because Ruff 0.17.0 is not
in the host cache. No tool was downloaded or installed, and no container was
started. The script's final Ruff verification remains pending an authorized
environment with the repository's declared tool.

## Historical integration evidence and current limits

On 2026-10-17, before the Router/review corrections:

- Isolated project `clinicflow-frontend` built the API and frontend, installed
  the lockfile with `npm ci`, and reported API, PostgreSQL and Vite healthy.
- API/frontend published only `127.0.0.1:8008` / `127.0.0.1:5173`; the database
  remained internal. All five excluded generated `web/` paths were confirmed
  absent from the API image.
- `Get-Content -LiteralPath web/scripts/smoke.py -Raw | docker compose -p
  clinicflow-frontend -f compose.yaml -f compose.frontend.yaml exec -T api python
  manage.py shell` passed **19 HTTP requests through Vite to Django**.
- That smoke covered registration, invalid/successful login, identity, blank
  clinic name rejection, two clinic creations, list/detail, another user's
  isolation, logout and revoked-token 401. Its `finally` block removed both
  synthetic users and both clinics with all memberships/tokens; no credentials
  were printed or committed.
- Host IPv4 UI responded 200; unauthenticated `/api/v1/clinics/` on port 5173
  responded 401. An unrelated IPv6 listener on `localhost:5173` was left intact.

The corrected version was subsequently verified in the isolated frontend
Compose project. The frontend image was rebuilt and the dependency volume
synchronized with the lockfile. All three services were healthy, and the IPv4
UI plus the TypeScript entry/router modules responded with HTTP 200. The same
19 real HTTP checks passed through Vite to Django, covering authentication,
clinic creation and isolation; the generated users, clinics, memberships and
tokens were removed by the cleanup block.

Before that preview, the unrelated Vite listener occupying port 5173 was
stopped at the user's request. At the 2026-10-20 checkpoint the user requested
shutdown again: the ClinicFlow frontend is stopped, its API/database are paused,
and all data/volumes are preserved. The reserved address remains
**http://127.0.0.1:5173** for the next authorized preview.

Orca tab discovery previously worked, but snapshot returned
`browser_tab_not_found`; the coordinator also reported browser runtime errors.
Visual/responsive, real-browser and screen-reader QA remain unverified. Current
accessibility evidence comes from React DOM/user-event focus, labels, headings,
navigation and error-state regressions in jsdom. The README includes the
manual browser review and self-cleaning HTTP commands for authorized resumption.
Changing the web container to `USER node` is deferred until volume ownership
can be verified then. Token expiry/rotation, password recovery, clinic editing,
memberships, patients, encounters, procedures, charges and payments remain
outside this UI slice.

## Exact delivered file inventory

The `.dockerignore` change contains exactly the five coordinator-approved
generated `web/` exclusions. The ignored root `.env` contains only generated
local development values and is excluded from this inventory and Git.

```text
.dockerignore
compose.frontend.yaml
web/.dockerignore
web/.gitignore
web/.prettierrc.json
web/Dockerfile
web/README.md
web/VALIDATION.md
web/index.html
web/package.json
web/package-lock.json
web/tsconfig.json
web/vite.config.ts
web/scripts/smoke.py
web/src/main.tsx
web/src/styles.css
web/src/app/App.tsx
web/src/app/router.tsx
web/src/app/layouts/RouteLayout.tsx
web/src/app/layouts/WorkspaceLayout.tsx
web/src/app/pages/NotFoundPage.tsx
web/src/app/pages/RouteErrorPage.tsx
web/src/features/auth/AuthProvider.tsx
web/src/features/auth/RequireSession.tsx
web/src/features/auth/api.ts
web/src/features/auth/context.ts
web/src/features/auth/errors.ts
web/src/features/auth/types.ts
web/src/features/auth/useAuth.ts
web/src/features/auth/layouts/AuthLayout.tsx
web/src/features/auth/pages/LoginPage.tsx
web/src/features/auth/pages/RegisterPage.tsx
web/src/features/clinics/ClinicDirectoryProvider.tsx
web/src/features/clinics/api.ts
web/src/features/clinics/context.ts
web/src/features/clinics/errors.ts
web/src/features/clinics/types.ts
web/src/features/clinics/components/ClinicDetails.tsx
web/src/features/clinics/components/ClinicDirectory.tsx
web/src/features/clinics/components/CreateClinicForm.tsx
web/src/features/clinics/components/IdentityCard.tsx
web/src/features/clinics/hooks/useClinic.ts
web/src/features/clinics/hooks/useClinicAccess.ts
web/src/features/clinics/layouts/ClinicsLayout.tsx
web/src/features/clinics/pages/ClinicIndexPage.tsx
web/src/features/clinics/pages/ClinicWorkspacePage.tsx
web/src/shared/api/errors.ts
web/src/shared/api/http.ts
web/src/shared/hooks/useAsyncForm.ts
web/src/shared/ui/Brand.tsx
web/src/shared/ui/Field.tsx
web/src/shared/ui/Notice.tsx
web/src/test/App.test.tsx
web/src/test/review-regressions.test.tsx
web/src/test/setup.ts
```
