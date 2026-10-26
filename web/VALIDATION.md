# Pre-merge review corrections — 2026-10-22

- **62 interaction tests passed** across five files. The six new cases cover preserving another item's quantity draft, blocking duplicate patient/procedure creates after lost acknowledgements, recovering both inline forms without losing encounter drafts, and allowing retry after an explicit validation rejection.
- TypeScript, production build and Prettier checks passed.
- Real Orca browser QA on fictional encounter #11 in clinic #8 confirmed that saving quantity 6 for the first item retains the second item's unsaved quantity 5. The second quantity was then saved and editing completed; no charge was issued.
- Four real HTTP checks through the Vite proxy returned the expected status: newline reference 400, oversized reference with newline 400, unknown clinic 400, invalid signature 403. None created a payment event.
- Docker Desktop on Windows was serving cached Vite modules after host edits. The Compose frontend now enables polling through CLINICFLOW_WATCH_POLLING; native development retains Vite defaults. A temporary module probe confirmed invalidation after a host edit and was removed.
- Stack: main → charges (#10) → payments (#12) → frontend (#11). Both CI workflows accept the corresponding PR bases. Backend validation passed with 615 tests on the dependency branch.

The earlier validation records below describe the previous checkpoints.

# Paid charge guidance — 2026-10-22

The simulated-payment backend was exercised through 30 real HTTP assertions
and 597 PostgreSQL-backed tests. Orca's existing encounter list displayed
fictional encounters #9 and #10 under the paid filter, at BRL 46.90 and BRL 23.45.

The paid encounter panel still used generic cancellation advice for locked
items. It now explains that a paid charge preserves its items and values.
A route-level regression covers the transition from pending to paid on refresh:
items stay locked, cancellation/reissuance controls stay absent, and the panel
does not suggest cancelling a paid charge.

Final frontend validation: TypeScript/production build, Prettier and **56 tests
in 4 files passed**, exit 0, in 37.02s. Earlier counts below remain historical.
Frontend CI now runs formatting, build and tests automatically for the PR.

---

# Orca browser workflow validation — 2026-10-21

The current preview was tested through Orca's embedded browser using the
ordinary fictional demo account. Browser commands were scoped to page
`0c503232-e52c-42e0-b97c-c7cc4dff17ff` in `clinicflow-frontend`.

Initial inspection returned `runtime_unavailable`. Explicitly revealing the tab
with `orca tab switch --page <id> --focus` restored inspection and interaction;
Orca did not need a restart. Subsequent actions used snapshots, element refs,
fills, selects and clicks. Offscreen table actions were brought into view before
clicking. A temporary report assertion was corrected to count regex matches
directly; the cancellation itself had completed successfully.

## Passed scenarios

- Login and the five permanent sidebar entries on the clinic directory.
- Choosing an area before a clinic and entering that area directly.
- Breadcrumb returns from charge detail to its collection, then to the clinic
  overview and clinic directory.
- Sticky header after real scrolling: top 0, with no page horizontal overflow
  at the actual 975x723 browser viewport.
- Creating patient #5 and procedure #5 from their forms.
- Creating encounter #7 with 2 units at BRL 159.90: total BRL 319.80.
- Previous/next record navigation within the panel; closing and reopening
  preserved the search and its single matching row.
- Issuing charge #7 at BRL 319.80, with item editing disabled.
- Updating the catalog price to BRL 179.90 while existing encounter and charge
  snapshots remained at BRL 159.90 per unit.
- Cancellation required a reason, retained history, and enabled item editing.
- Updating quantity to 3 retained the original unit price and totalled BRL 479.70.
  Reissuing created charge #8 while cancelled charge #7 retained BRL 319.80.
- Cancelling charge #8 retained both historical charges and unlocked items.
- The existing free encounter #3 displayed no payment required; it was read only.
- New empty encounter #8 saved without items and disabled charge issuance with
  an explanation. Existing encounter #5 had already been filled, so its data was
  left intact and a separate fictional empty record was used.

No application failure was found in these scenarios. End-of-run Orca console
inspection returned an empty message list. This was a browser validation pass;
the earlier 55 automated test result below was not rerun because application
source was unchanged.

## Review records and evidence

Clinic #8 contains patient #5 and procedure #5 named with `QA Orca 21-10`,
encounter #7 (3 units, BRL 479.70, both test charges cancelled) and encounter #8
(no items or charges). The test records remain available for review. Changes
during this pass were limited to these newly created fictional records.

The Orca tab remains signed in at
http://127.0.0.1:5173/clinicas/8/atendimentos/7.
Local temporary evidence: `clinicflow-orca-qa-atendimento7.png` and
`clinicflow-orca-qa-encounter7.txt`. The three preview containers remain active.
No production source changes, merge or new commit were made in this pass.

---

# Persistent menu and breadcrumb navigation — 2026-10-21

The sidebar now keeps the same five entries before and after selecting a clinic.
Choosing a clinic area without an active clinic opens `/clinicas?area=<section>`;
selecting a clinic opens that area directly. Refreshing the directory preserves
the requested area. Only the four known clinic sections are accepted.

The header breadcrumb exposes links to the clinic directory, selected clinic
and collection, with the current page marked separately. It remains visible
on mobile and wraps long clinic names. The directory provider now belongs to
the authenticated shell, so both navigation and clinic pages share the same
session-scoped directory. The header remains sticky while scrolling.

Validation: production build/TypeScript, Prettier and git diff check passed.
The full suite passed **55 tests in 4 files**, exit 0, in 31.64s. Six additional
interaction regressions cover all four area-selection paths, stable menu
entries, directory refresh, breadcrumb returns and a missing charge detail.
Existing session, access-removal and asynchronous-response regressions pass.

Real browser validation used an isolated local Microsoft Edge headless session
against the running API, because automation in the existing Orca tabs returned
transient runtime connection failures. Demo login, direct area selection,
named clinic/directory breadcrumb returns and unchanged sidebar geometry passed.
At 1366x650, 1024x600, 800x600, 390x844 and 320x568, the breadcrumb stayed
visible, the header remained at top 0 after scrolling, and the page had no
horizontal overflow. An existing absolutely positioned table label escaped its
scroll container on mobile; positioning the table scroll container contains it
without hiding page content. The final CSS build and formatting checks passed.
No records were created or changed during this navigation validation.

Evidence is stored locally in the temporary files
`clinicflow-navigation-browser.json` and `clinicflow-navigation-desktop.png`.
The preview remains at http://127.0.0.1:5173. No merge or new commit.

---

# Daily clinic workflow and navigation — 2026-10-21

The frontend now includes patient registration/editing, procedure and price
registration/editing, encounter creation with quantities and an exact total,
and direct navigation between modules. These use the existing backend contracts
from the separate charges worktree; no backend source was modified in this step.

## Result and evidence

- Procedure prices accept decimal comma/point and are sent as exact strings.
  Existing encounter item prices remain historical snapshots.
- New encounters support inline patient and procedure creation. Description is
  required, matching the real API and its PostgreSQL constraint. The browser
  validation exposed an incorrect optional label; this was corrected and the
  transport fixture now also rejects missing descriptions.
- Encounter details open in a side panel over the same searchable/filterable
  list. Close preserves list state. Previous/next changes the record in place.
- Active charges can be cancelled from the encounter panel with an audit reason.
- Native nested dialogs preserve focus, restore screen-reader visibility and
  body scrolling, and prevent closing while saves are pending.
- A failed item submission can resume the existing encounter, reconciling saved
  items before adding missing ones. Unconfirmed creation requires checking the
  list rather than automatically posting another encounter.

Final validation: production build/TypeScript, Prettier and git diff check passed.
The complete frontend suite passed **49 tests in 4 files**, exit 0, in 21.67s.
This includes the earlier authentication, clinic and financial suites plus seven
workflow/price/accessibility checks. The same source was copied into a temporary
container directory and run with the documented single-worker, no-cache flags
and a 20-second per-test budget.

Real browser validation used the ordinary demo account and the existing API:
procedure #4 was created at BRL 145.75, patient #4 was registered inside the
encounter form, and encounter #6 was saved with two procedure units and total
BRL 291.50. It was left without a charge for review. Details opened in the side
panel and closing/reopening retained the searched encounter list. The procedure
and patient remain fictional demo records available for user review.

Preview remains http://127.0.0.1:5173 with healthy frontend, API and PostgreSQL.
All changes remain local in clinicflow-frontend. No merge or new commit.

---

Earlier delivery evidence follows; its previous counts and scope are historical.

# Charges frontend validation — 2026-10-21

Branch: `clinicflow-frontend`, checkpoint `40568b8`. No merge or new commit.
The preview builds the API from the separate `clinicflow-charges` worktree.

## Delivery and checks

- Encounter review/editing, charge issuance/detail/history/filter, cancellation
  audit, shared error/loading states, responsive styles and corrected encoding.
- Production build/TypeScript, Prettier and `git diff --check`: passed.
- Existing application/review suites: **32 tests passed**.
- New financial flow/precision suite: **10 tests passed**, covering issuance,
  retry after navigation, pending requests across navigation, cancellation and
  reissuance, permission denial, zero totals, empty/unavailable encounters and
  exact large monetary values/overflow.
- **41 real HTTP checks passed** through Vite to Django: fixtures, issuance
  replay/conflict, locked items, cancellation audit, immutable snapshots,
  reissuance, zero totals, empty-encounter rejection and access boundaries.
- Browser: login, clinic/encounter navigation and desktop layout inspected;
  charge #5 issued, items locked, cancellation completed with a reason, audit
  displayed with no error alert.

## Final complete run and runtime notes

The final full run passed **42 tests in 3 files**, exit 0, in 98.69 seconds.
It used an exact temporary copy of src and the Vite/TypeScript/package files
inside the frontend container, with the same installed dependencies and
`--maxWorkers=1 --fileParallelism=false --no-cache --testTimeout=20000`.
No assertions were changed to obtain this result. An earlier Windows repeat
hit worker-startup timeout; a direct bind-mount container run exceeded the
5-second limit in four existing tests, followed by one form lookup failure.
The increased per-test budget resolved those failures in the complete run.

## Running preview

- UI http://127.0.0.1:5173; API http://127.0.0.1:8008.
- Compose project `clinicflow-frontend`: API, PostgreSQL and frontend healthy.
- Existing database retained. Added ordinary demo account `demo.cobrancas`,
  one demo clinic, three fictional patients and five encounters. Examples cover
  ready-to-bill, pending, free, cancelled history and missing items. Browser
  charge #5 was also cancelled during validation. Unrelated records preserved.
- Frontend kept running for review. No merge performed.

Role metadata, payment confirmation/refunds and patient/encounter registration
UI are outside this delivery. The backend suite was not reexecuted for these
frontend changes; this run validated its integration over HTTP.

---

The following evidence belongs to the earlier authentication/clinic checkpoint;
its paused-runtime statements and test counts are historical.


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

## Integrated main and payment workspace — 2026-10-26

The local main checkout was fast-forwarded to `fceaa00`. The existing
`clinicflow-frontend` Compose project and database volume were preserved.
Only synthetic records were added in **QA fluxo integrado 26-10** (clinic #10):
patient #8, procedure #9 at BRL 125.50, encounters #12–14 and charges #11–13.

Real HTTP calls through Vite's proxy created the patient, procedure, encounters,
items and charges, then submitted signed receipts. All three charges initially
remained pending. A separate one-shot process reconciled only QA events #5–7:
- Event #5 reconciled charge #11, which became paid.
- Event #6 recorded an amount mismatch; charge #12 remained pending.
- Event #7 recorded a currency mismatch (USD); charge #12 remained pending.
- Event #8 remained received, and charge #13 remained pending.

The Orca browser showed the three encounters before and after reconciliation:
only encounter #12 changed to paid. Existing clinics and their records were
left intact. The feature preview reuses the main API and database and binds only
the frontend to the payment-workspace worktree.

Frontend validation passed with **85 tests in six files** (23 new payment cases),
TypeScript/production build and Prettier. Tests cover entering the area before
clinic selection, GET authentication, exact currency amounts, source-event links,
paid-charge links, status/search persistence, in-drawer refresh after reconciliation,
all five discrepancy reasons plus unknown codes, empty/error recovery, unavailable
IDs and clinic access/payload isolation.

Real Orca browser QA opened payment #3 and followed its source event #5. The
event list contained one reconciled, two discrepancy and one received record.
Filtering discrepancies showed only events #6 and #7. Event #7 displayed
**US$ 125.50** and the currency-mismatch explanation; refreshing and closing the
drawer retained the discrepancy filter and its two records. A local screenshot
was inspected. At the tested 975 CSS-pixel viewport, page and dialog scroll widths
matched their client widths, with no horizontal overflow.
