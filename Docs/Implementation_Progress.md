# ZongoVita IMS: Implementation Progress

Living record of what is built, how it was verified, what was decided at implementation level, and what is unresolved. The HLD and LLD remain the authority for design; this file never overrides them.

Last updated: 19 November 2026.

## 1. Status

| # | Unit | State |
|---|---|---|
| 1 | Tenancy, licensing and transaction foundation | Done, verified (168 tests; 175 with the UI contract checks) |
| 2 | Identity and session: Login Directory, users, login, MFA, refresh, lockout | Done, verified (61 new tests; 236 in all) |
| 3 | Access control: permission catalogue, roles, user types, super-admin rules, authorisation stage, rate limits, `/me` | Done, verified (30 new Python tests, 266 in all; 14 browser tests against the real Core: 4 sign-ins and 10 tests, first reported as 15 in error) |
| 4 | Organisation (sites, locations, departments) and licence limits | Done, verified (13 new Python tests, 279 in all; 119 browser tests, 16 against the real Core) |
| 5 | Platform administration API, provisioning runs, platform users | Done, verified (20 new Python tests, 299 in all; 127 browser tests, 6 against the real Platform Service, 12 against the real Core) |
| 6 | Workers: job queue, outbox dispatch, work-pending index, service levels | Next |
| 7 | Workflow and approval engine | Pending |
| 8 | Catalogue; vendors and purchase records | Pending |
| 9 | Inventory Core; receiving; issuance; transfers; counts; returns and quality | Pending |
| 10 | Replenishment, alerts, reporting and export | Pending |
| 11 | Integration: public API, events feed, webhooks, connectors, sandbox | Pending |
| 12 | GxP signatures, support grants, break-glass | Pending (hooks for reason-for-change already in the kernel) |
| 13 | Next.js apps (Tenant Web App, Platform Console) | All 43 wireframe screens built. The Tenant Web App signs in to Core through its BFF; session, menus, screen guard, location selector, F21, F22 and F36 are live. The Platform Console signs in to the Platform Service through its own BFF; F51 and F52 read the registry, F53 shows sample data. Other screens show sample data until their units land (Docs/UI_Implementation.md) |
| 14 | Staged migration rollout, load test, deployment artefacts | Pending |

The order follows dependencies: every module needs the kernel (unit 1); authorisation needs identities (2 before 3); site-scoped permissions need sites (4); stock modules need workflow gates and the catalogue (7, 8 before 9).

Git: unit 1 and the UI are committed on local `main`; unit 2 on `unit-2/identity-session` (from `main`); unit 3 on `unit-3/access-control` (from unit 2); unit 4 on `unit-4/organisation-licence-limits` (from unit 3); unit 5 on `unit-5/platform-administration` (from unit 4), so each unit branch contains the units before it. No commit was pushed from this work; the earlier commits are unchanged.

## 2. What unit 1 delivered

**Why it came first.** Every request and job in the LLD runs through one pipeline (LLD 6.1): verified token, customer from the claim only, licence state gate, that customer's database through the pooler, one unit of work. The invariants the HLD reviewer asked to protect live there (AD-08, AD-13, AD-16, AD-18, AD-21, AD-34, AD-51).

| Area | Where | Design reference |
|---|---|---|
| Local PostgreSQL 16 + PgBouncer 1.24, transaction mode, per-role auth query | `deploy/local` | AD-80, LD-75, LLD 6.5 |
| Contracts: error codes and problem details, licence snapshot and state derivation, event envelope, Platform interface models | `packages/py-contracts` | LLD 12, 13, 6.4, 6.8 |
| Shared runtime: UUIDv7, Ed25519 key sets and JWTs with rotation, service tokens, secrets-store and object-store ports, signed snapshot bundle, problem-details handlers, allow-listed JSON logging, pooler-safe engines | `packages/py-common` | LLD 3, 6.2, 16; AD-63, AD-64, AD-74 |
| Control-Plane schema: customers, licences, modules, licence modules, customer databases, login directory, change feed, platform audit; guard triggers; `platform_app` grants | `services/platform/migrations` | LLD 4 |
| Licence Registry: customer status machine, licence activation and renewal, database registration and state, GxP lock, snapshot, commit-ordered change feed, audited commands | `services/platform/ims_platform/registry.py` | AD-12, AD-78 |
| Platform internal interface: snapshot and change feed, service-token only | `services/platform/ims_platform/api_internal.py` | LLD 6.8 |
| Snapshot bundle publisher (every 5 minutes) | `services/platform/ims_platform/bundle.py` | LD-78, AD-25 |
| Database pipeline: provision database and three roles per customer, role defaults, migrations in one transaction with 3 s lock timeout and retries, monthly partitions three months ahead, safe drop of expired partitions, CLI | `pipelines/database` | LLD 6.6, 6.7; AD-28, AD-29, AD-62, AD-68 |
| Customer baseline: 13 schemas, partitioned append-only audit log, partitioned outbox, idempotency keys, settings; column-level grants | `services/core/migrations/versions/0001_kernel_baseline.py` | LD-05, LD-06, LD-51, LD-67, AD-66, AD-67 |
| Kernel: tenant context, licence gate with last known-good and bundle fallback, database router, access tokens, request pipeline, unit of work, audit writer (with GxP reason-for-change hook), outbox writer, idempotency, typed settings registry, route declarations | `services/core/ims_core/kernel` | LLD 6.1, 6.4, 6.5, 7, 12; LD-02, LD-25, LD-61, LD-62, LD-77, LD-82 |

**Not in unit 1, deliberately.** Pipeline steps 6 to 8 (principal, rate limit, authorise) are defined as stages the kernel requires but does not implement; `create_app` refuses to mount tenant routes without them. The Core application therefore serves only health endpoints until units 2 and 3 land. Outbox dispatch, the events feed and work-pending hints belong to units 6 and 11; events are already written transactionally.

## 2a. What the UI work delivered

The wireframes (`Docs/ZongoVita-IMS.zip`, 43 frames) were added after unit 1. Both Next.js apps now draw every frame, on sample data, behind the same structure the real integration will use. Details, the frame-to-route map, the endpoint each screen waits for and the points to decide are in `Docs/UI_Implementation.md`.

| Area | Where |
|---|---|
| Design tokens and shared components taken from the frames (palette, type sizes, borders, buttons, pills, tables, forms, tabs, timeline, stepper, shell) | `packages/ui` |
| TypeScript contracts mirrored from `py-contracts` (error codes, licence state, permission catalogue, `/me` shape), checked against the Python side by a test | `packages/api-client` |
| Tenant Web App: 40 frames, three workspaces derived from permissions (not role names), licence banners, permission-aware controls | `apps/tenant-web` |
| Platform Console: 3 frames, separate deployment (AD-04) | `apps/platform-console` |
| Strict per-request nonce CSP, `frame-ancestors 'none'`, HSTS, no inline styles (LD-49) | `src/proxy.ts`, `next.config.ts`, lint rule |
| Browser tests on production builds: every frame, both widths (1440 px and a 390 px phone), menus, security headers | `e2e/`, `playwright.config.ts` |
| Dependency report generated from code, kept current by a test | `tools/ui-dependencies.mjs` |

What it is not yet: connected. Every read is served from `src/fixtures` through one function per screen in `src/data`, which names the Core endpoint it stands in for; every data-changing button says it is not connected and names its endpoint. Sign-in chooses a sample persona.

## 2b. What unit 2 delivered

| Area | Where | Design reference |
|---|---|---|
| Login identifier normalisation (trim, NFKC, lower case) and keyed hashes | `packages/py-common/ims_common/identifiers.py` | LD-10, LLD 4 |
| Login Directory in the Platform Service: reserve (15 minutes), activate-or-re-reserve, disable, resolve, list; expired reservations can be taken over; one identifier per principal; every change audited and announced on the change feed | `services/platform/ims_platform/directory.py`, control-plane migration `0002` | AD-20, LLD 6.3 |
| Internal directory endpoints with per-endpoint caller rules (Core resolves and reserves; Core and Workers activate, disable, list) | `services/platform/ims_platform/api_internal.py` | LLD 6.8 |
| Snapshot bundle keyed by lookup hash, so a process can resolve identifiers during an outage | `registry.py`, `ims_contracts/platform_api.py` | AD-79, LD-78 |
| Core directory cache: 10 minutes, change-feed eviction, cached "unknown" entries, last known-good at any age, bundle fallback, back-off while the Platform Service is down | `services/core/ims_core/kernel/directory.py` | AD-79, LLD 6.3 |
| Customer schema: `iam.users`, `iam.mfa_factors`, `iam.mfa_recovery_codes`, `iam.sessions` (DELETE only past absolute expiry), `iam.api_clients` | `services/core/migrations/versions/0002_identity.py` | LLD 5.1, section 3 |
| Sign-in: password step with constant work (one Argon2id verification on every path), generic failure, lockout after five failures for 15 minutes, single-use MFA challenge | `modules/identity/service.py` | LD-80, LLD 6.2 |
| MFA: TOTP (RFC 6238, 30-second step, one step of tolerance, each step accepted once), mandatory enrolment at first sign-in, ten single-use recovery codes stored hashed, secrets encrypted with AES-256-GCM bound to their user, MFA failures count toward the lockout | `modules/identity/domain.py`, `credentials.py` | LD-79 |
| Sessions: access 15 minutes; refresh rotation on every use, reuse of an old refresh token revokes the session; idle 8 hours, absolute 7 days; sign-out | `service.py`, `kernel/authn.py` | LLD 6.2, LD-26 |
| Activation: one-time code for new users, password policy (12 characters, common-password list), single use, expiry, failures count toward the lockout | `service.py`, `domain.py` | LLD 6.2, section 16 |
| User creation: reserve -> create (with licence user-limit check under a transaction-level advisory lock, audit, `iam.user.created` event) -> activate after commit; "identifier in use" suspends the user | `service.py` | LLD 6.3 |
| API clients: 32-byte secrets shown once and stored hashed; client-credentials grant at `/api/v1/oauth/token` (form body or HTTP Basic), integration module required | `service.py`, `api_public.py` | AD-22, LLD 6.2 |
| Pipeline step 6 (principal stage): session live and user active, API client active; support principals refused until unit 12 | `modules/identity/public.py` | LLD 6.1, LD-28 |
| Credential routes `/ui/v1/auth/login`, `/mfa/enrol`, `/mfa`, `/refresh`, `/logout`, `/activate` | `modules/identity/api_ui.py` | LLD 12 route table |

Not in unit 2, deliberately: user and API-client management endpoints (they need the authorisation stage, unit 3), the Workers that activate directory entries and reconcile (unit 6), re-authentication for GxP signatures and support sessions (unit 12), rate limiting (unit 3), and the Next.js sign-in, MFA and activation screens (no wireframes exist; see U-06).

## 2c. What unit 3 delivered

| Area | Where | Design reference |
|---|---|---|
| Code-defined permission catalogue (62 codes, site scope, three reserved to Super Admin) and the seeded roles, shared by Core, the database pipeline and the web app (a static test keeps the TypeScript mirror equal) | `packages/py-contracts/ims_contracts/permissions.py`, `packages/api-client/src/permissions.ts` | LLD 5.1, 7; AD-45 |
| Customer schema: `iam.permission_catalog`, `iam.roles`, `iam.role_permissions`, `iam.role_assignments`, `iam.access_version`, with the built-in rules in the database: exactly one super admin (partial unique index, deferred commit-time trigger, held by an invited or active user), flag copied from the role, API clients never super admin, reserved permissions only with Super Admin, Super Admin role not editable or clonable, role identity immutable, assignments revoke-only, super admin user cannot be suspended or deactivated, every access change bumps the access version | `services/core/migrations/versions/0003_access_control.py`, `ims_core/schema/access.py` | LLD 5.1, 7; LD-53, LD-15 |
| Catalogue rebuilt from code after every migration (codes a release removes are revoked from roles, with a system audit entry); seeded roles inserted by natural key at provisioning and never overwritten | `pipelines/database/ims_db_pipeline/access_seed.py`, `migrate.py` | LLD 6.6 |
| Pipeline step 8: every access rule; effective permissions (union over assignments, per site; super admin holds all) cached per process by (principal, access version) for up to 60 s and placed on the unit of work for record-site checks and list filters | `modules/access/public.py`, `evaluation.py`, `kernel/grants.py` | LLD 6.1, 7, 16 |
| Pipeline step 7: token buckets per user (300/min), per API client (its own limit, 600 by default) and per customer (6,000/min); 429 with Retry-After | `modules/access/ratelimit.py` | LD-88, AD-84 |
| `GET /ui/v1/me`: principal, user type, super-admin flag, role label, effective permissions per site, licence state, grace end, GxP mode, modules | `modules/access/api_ui.py` | LLD 7, 15 |
| Users: list (cursor, status and text filters), read, create with role assignments in the same transaction, edit (If-Match), deactivate (sessions end, directory entry disabled) | `modules/access/service.py`, `modules/identity/service.py` | LLD 6.3, 12 |
| Role assignments (create, revoke; never Super Admin), roles (list, read, create, edit), privilege matrix, `PUT roles/{id}/permissions` writing the difference, auditing each change and returning an effective-permission preview per affected principal | `modules/access` | LLD 7, 12 |
| Super-admin transfer: locks the Super Admin role row, revokes and grants in one transaction; concurrent transfers leave exactly one | `service.py` | LLD 7, LD-53 |
| No self-escalation; no lock-out of the super admin; GxP reason for role and permission changes | `service.py` | LLD 7, LD-82 |
| API clients: list, create with role assignments, disable, rotate secret | `modules/access`, `modules/identity` | LD-13, LLD 16 |
| `If-Match` / `ETag` for master-data edits (428, 412) | `kernel/versioning.py` | LLD 12 |
| A route cannot declare a permission outside the catalogue (import-time error) | `kernel/routes.py` | LD-62 |
| The Core application with all modules so far (`ims_core.main.build_app`), used by the server, the tests and the browser-test backend | `ims_core/main.py` | — |
| Web app signed in to Core: BFF (`/bff/auth/*`, `/bff/[...path]` with CSRF and Origin checks, idempotency keys, refresh-once-and-replay), HttpOnly session cookies, token renewal in the proxy before render, session from `/ui/v1/me`, menus and screen guard from effective permissions, F22 and F36 live, F36 saves through Core | `apps/tenant-web/src/app/bff`, `src/bff`, `src/session`, `src/proxy.ts` | LLD 6.2, 15; LD-49 |
| UI aligned with the LLD where frames disagree: sample personas carry the seeded permissions; Platform Console without price plans, billing, seven-year retention, support tiers, residency choice, SSO or "expired blocks everything" | `apps/*`; Docs/UI_Implementation.md section 10 | Product owner's authority rule |

Not in unit 3, deliberately: support grants and support principals, recovery approvers and break-glass (unit 12); the provisioning run that creates the first super admin (unit 5; the service function exists and is used by the tests); sites, so `/me` returns no sites and assignment sites are not yet checked against `org.sites` (unit 4); notifications (unit 10); the screens the LLD needs but no wireframe draws (U-06).

## 2d. What unit 4 delivered

| Area | Where | Design reference |
|---|---|---|
| Customer schema: `org.sites` (code, name, IANA timezone, status staged / active / inactive), `org.locations` (site, code, name, default flag, status), `org.departments` (code, name, status), with the rules in the database: exactly one default location per site (partial unique index, deferred commit-time trigger that also covers a new site), the default location active, site transitions only along the defined ones, timezones PostgreSQL knows, codes unique per customer ignoring case and fixed once created, a location never moves site, nothing deleted | `services/core/migrations/versions/0004_organisation.py`, `ims_core/schema/access.py` | LLD 5.1, 3 |
| Foreign keys from `iam.users.department_id`, `iam.users.home_site_id` and `iam.role_assignments.site_id`, added `NOT VALID` and validated in the same migration | same | LLD 6.7; D-18, D-21 resolved |
| Licence site limit: staged and active sites count; creating a site or re-activating an inactive one is refused at the limit (409 LIMIT_EXCEEDED) under a transaction-level advisory lock, so concurrent creations cannot overshoot | `modules/organisation/service.py` | AD-27, #30 ("creation refused at the limit"), LLD 5.1 |
| Endpoints: `GET sites, locations, departments` (and by id, with ETag) for every authenticated principal; sites (create with their default location, edit, activate, deactivate) with `org.site.manage`; locations (create, edit, make default, activate, deactivate) with `org.location.manage`; departments (create, edit, activate, deactivate) with `org.department.manage`; edits need If-Match; lists use cursor pagination | `modules/organisation/api_ui.py`, `kernel/paging.py` | LLD 12 |
| Public API reference data: `GET /api/v1/sites`, `GET /api/v1/locations` (licence module ims.integration) | `modules/organisation/api_public.py` | LLD 12 public table |
| Identity and access integration: users carry a department (active when set) and a home site (staged or active when set) on create and edit; role assignments must name an existing site; `/ui/v1/me` returns the active sites the person works at and their home site | `modules/access/service.py`, `modules/identity` | LLD 5.1, 7, 15 |
| Web app: the shell's location selector from `/me`; F21 Locations live (sites, status, users assigned at each site by user type); F22 shows site codes; add and edit buttons say their forms are not designed | `apps/tenant-web/src/data/{sites,locations,users}.ts`, `src/app/(app)/locations`, `(app)/layout.tsx` | LLD 15; wireframes F21, F22 |
| Browser-test backend: the demo customer gets the four F21 sites (one active, three staged), two departments, and its people home sites, departments and site-scoped roles | `tools/e2e_backend.py` | — |

Not in unit 4, deliberately: anything that needs stock (staged sites hold no stock; whether a site or location with stock may be deactivated, U-15) arrives with Inventory Core (unit 9); site type and city, drawn in F21, are not in the LLD's site record (U-07); screens for creating and editing sites, locations and departments are not drawn (U-06); the Platform Console's sites-used figure needs Core to report usage to the Platform Service (unit 5, AD-13).

## 2e. What unit 5 delivered

| Area | Where | Design reference |
|---|---|---|
| Control-plane schema: `platform_users` (role system_admin or support_engineer; status invited, active, suspended, deactivated; sealed TOTP secret, pending enrolment, single-use MFA challenge, activation code, lockout), `platform_recovery_codes`, `platform_sessions`, `provisioning_runs` (one per customer; step, status, attempts, last error, request, step results, sealed handover). No DELETE grant on any of them | `services/platform/migrations/versions/0003_platform_administration.py` | LLD 4 (platform_users, provisioning_runs), AD-13 |
| Staff sign-in, the same rules as customer users: password then TOTP (enrolment at first sign-in, ten recovery codes), one Argon2id verification on every path with the same generic failure, outside any transaction, five failures lock for 15 minutes, refresh rotation with reuse revoking the session, idle 8 h and absolute 7 days, sign-out, activation with a one-time code. Tokens carry issuer `ims-platform` and audiences `platform-console`, `platform-refresh`, `platform-mfa`, so Core refuses them | `ims_platform/accounts.py` | LLD 6.2 ("Platform: different issuer and audience"), AD-23, LD-26, LD-79, LD-80 |
| Credential helpers shared by Core and the Platform Service: Argon2id hasher, sealed-secret key ring, TOTP and code formats, common-password list (moved from Core's identity module, unchanged) | `packages/py-common/ims_common/{credentials,auth_codes}.py` | I-01 |
| `/platform/v1`: auth (login, mfa/enrol, mfa, refresh, logout, activate), `me`; customers (list, read, suspend, reinstate, terminate with a reason); licences (list, create a draft, activate: renewal or change is a new licence record); modules; provisioning runs (list, read, start, resume, reveal the handover once); staff users (list, create with a one-time activation code, deactivate, which revokes their sessions); platform audit with paging. Every change is in the append-only platform audit with the acting staff member | `ims_platform/api_platform.py`, `admin_queries.py`, `registry.py` | LLD 6.8, 4, 6.4 |
| Staff roles: the system admin manages customers, licences, provisioning and staff; the support engineer has no administration rights (support sessions under a customer's grant are unit 12). Enforced by the Platform Service on every route | `api_platform.py` (`SystemAdmin`) | HLD section 3 actors; D-34 |
| Licence state in the console is derived at read time from the customer status and the licence dates, exactly as Core derives it | `admin_queries.derive` | LLD 6.4 |
| Provisioning run: register (customer and draft licence) → database (pipeline job: database and roles) → register_database (location and secret reference) → migrate (pipeline job: schema, permission catalogue, seeded roles) → initial_users (IMS Core creates the super admin in the customer database) → activate (licence and customer active, change feed). Steps are recorded one by one; each is safe to repeat; a failed run keeps its error and resumes from the failed step; a run left `running` by a process that died can be resumed after 15 minutes; a resume is claimed once under a row lock; one run per customer; GxP customers need dedicated placement | `ims_platform/provisioning.py` | LLD 6.6, 6.7, AD-28, LD-85 |
| The Platform Service holds no DDL or customer-data credential: database work goes through the pipeline port (`SubprocessPipeline` runs `ims-db-pipeline provision-customer-db` and `migrate-customer-db`, the commands a CI/CD job runs), and the super admin is created by Core over a signed service call | `provisioning.py` (`PipelinePort`, `CorePort`, `HttpCore`) | AD-13, LLD 6.7, AD-64 |
| Core side of step 6: `POST /internal/v1/provisioning/super-admin` accepts only the Platform Service's service token, takes the customer from its `cid` claim, and builds a provisioning context (kernel) from a provisioning-only snapshot that the Platform Service returns only while that customer's run is at `initial_users` and running. Creates the super admin with the unit 3 bootstrap; repeating the step returns a fresh activation code for the same invited super admin | `ims_core/kernel/runtime.py` (`provisioning_context`), `kernel/licence.py`, `modules/access/api_internal.py`, `ims_platform/api_internal.py` | AD-21, AD-64, LLD 6.6; D-36, D-37 |
| Handover: the super admin's activation code is sealed on the run (AES-256-GCM, platform key ring, bound to the run) and shown once to a system admin, never cached | `provisioning.reveal_handover` | #21; D-38 |
| First system admin from the command line: `ims-platform-admin create-system-admin`, refused once one exists | `ims_platform/cli.py` | D-40 |
| Shared BFF package for both web apps: HttpOnly token cookies, refresh once per process, CSRF header and Origin check on every change, Idempotency-Key added to writes, sign-in handlers that keep tokens in cookies, a catch-all that never forwards `auth/*`, token renewal before a page renders. The Tenant Web App now uses it unchanged in behaviour | `packages/web-session` | LD-49, LLD 15, I-33 |
| Platform Console on real data: `platform` session mode (default; `fixtures` keeps the sample administrator), its own BFF to `/platform/v1` with its own cookie names, session from `/platform/v1/me`, menu and screen guard by staff role, enterprise selector from the registry; F51 shows customers by status, licensed users, each customer's database or provisioning step, and the platform audit as activity; F52 shows the licence registry (validity, limits, modules, database, derived state) and the licence nearest expiry with its grace and read-only dates. Figures the Platform Service does not have (users and sites in use, API calls, last activity, uptime, NFR health) show as not reported (U-17). Onboarding and licence assignment say their forms are not designed; sign-in shows a design-gap notice (U-06) | `apps/platform-console/src/{session,bff,data}`, `app/(console)`, `app/sign-in` | LLD 15, AD-04 |
| Browser-test backend: the demo customer is now onboarded through the real provisioning run started by a system admin, its super admin activates with the handed-over code; a system admin and a support engineer exist with real passwords and authenticators; the Platform Service is served on 8181 | `tools/e2e_backend.py`, `tools/e2e-servers.mjs` | — |

Not in unit 5, deliberately: migration runs (`/platform/v1/migrations`, staged rollout) are unit 14; break-glass requests, recovery approvers (LLD 6.6 step 6) and support sessions are unit 12 (U-16); usage reporting from Core to the Platform Service has no interface in the LLD (U-17); the console's sign-in, onboarding, licence and staff forms are not drawn (U-06).

## 3. Verification

`uv run pytest`: 299 passed (about 9 minutes on this machine). `uv run ruff check .`: clean. `npm run test:e2e`: 127 passed: 16 against the real Core (4 sign-ins, 12 tests) and 8 against the real Platform Service (2 sign-ins, 6 tests), run after the Python suite, never alongside: both use the test database stack. `npm run typecheck`, `npm run lint`: clean.

| LLD section 17 row | Covered now | Tests |
|---|---|---|
| Tenant isolation | Token alone selects the database; no header, query or host selects another customer; tampered `cid` fails the signature; another customer's credential cannot connect to the database (pooler and direct) | `tests/kernel/test_tenancy_and_licence.py`, `tests/db/test_customer_database.py` |
| Tenant context, permissions, licence modules, read-only flags (static) | Engines only in the router; `TenantContext` only in the kernel; undeclared routes fail at import; module boundary rule (LD-01); deployables do not import each other | `tests/static`, `tests/unit/test_routes.py` |
| No hard deletes; immutable history | Catalogue privileges compared with the access registry; UPDATE, DELETE, TRUNCATE on audit refused for the application role and for the table owner; application cannot supply time, sequence or transaction ID; outbox can only be marked dispatched | `tests/db/test_customer_database.py` |
| Duplicates act once; first write wins | Ten concurrent duplicates give one effect; replay header; key reuse refused; in-progress duplicate gets 409 after the lock timeout; eight concurrent writers on one version give one winner; all through the pooler | `tests/kernel/test_unit_of_work.py` |
| Licence state | Grace starts on the end date; read-only refuses writes except `read_only_ok` routes; suspended and terminated refuse everything; renewal returns to active; change notice and 60 s refresh both propagate; Registry outage keeps known customers on last known-good and logs the on-call alarm once; a process started during an outage serves from the signed bundle; forged bundle ignored | `tests/unit/test_snapshot_store.py`, `tests/unit/test_licence_state.py`, `tests/kernel/test_tenancy_and_licence.py` |
| Migrations, skew and partitions | Pipeline-only migration credentials (Core and Platform identities are denied them; migration role unusable through the pooler); schema head matches the application; unsupported version gives 503; repeatable provisioning and migration; partitions attach and expire correctly | `tests/db`, `tests/static` |
| GxP mode | Reason for change required for GMP-relevant audit entries; GxP lock irreversible in the Registry; GxP implies dedicated placement | `tests/kernel/test_unit_of_work.py`, `tests/db/test_control_plane.py` |
| One transaction per command (AD-08) | Change, audit, event and key share one transaction ID; a failure after every write leaves nothing; GET runs in a read-only transaction | `tests/kernel/test_unit_of_work.py` |
| Deadlock retry (LLD 9.1) | A real deadlock is retried transparently | `tests/kernel/test_unit_of_work.py` |

Unit 2 adds the LLD section 17 "Identity" row:

| Requirement | Covered | Tests |
|---|---|---|
| MFA enforced for every local login | No token before the second factor; enrolment is mandatory at first sign-in; every later sign-in asks for a code | `tests/kernel/test_identity.py` |
| TOTP steps cannot be replayed | The enrolment step is refused at the next sign-in; RFC 6238 vectors; window and once-only rules | `tests/kernel/test_identity.py`, `tests/unit/test_identity_domain.py` |
| Unknown and known identifiers take indistinguishable time | Wrong password, unknown identifier, invited account, malformed identifier and suspended customer give the identical answer after exactly one Argon2id verification each | `tests/kernel/test_identity.py` |
| Support tokens stop when the grant ends | Not yet: support grants are unit 12; support tokens are refused outright meanwhile | — |

Also covered: lockout after five password or MFA failures and unlock at exactly 15 minutes; recovery codes once each; refresh rotation and reuse revoking the session; idle and absolute expiry; sign-out; inactive users refused at pipeline step 6; tokens of one customer reach only that customer; activation code rules; identifiers unique across customers regardless of case; licence user limit; sign-in during a Platform Service outage from the cache and, for a process started mid-outage, from the signed bundle; "identifier in use" suspension; client-credentials grant, disabled clients, and audiences kept apart. The Login Directory has its own database tests (`tests/db/test_directory.py`): lifecycle, uniqueness, takeover of expired reservations, one identifier per principal, audit and change feed, only hashes stored, bundle contents, the pepper never readable by Core, and caller rules on every internal endpoint.

Unit 3 adds the access rows of section 17:

| Requirement | Covered | Tests |
|---|---|---|
| Exactly one super admin (database) | Never two (index); never zero at commit; revoking the last assignment fails; API-client super admin fails; reserved-permission grants fail; the holder cannot be suspended or deactivated; a transfer in one transaction succeeds | `tests/db/test_access_schema.py` |
| Exactly one super admin (concurrency) | Two concurrent transfers through the pipeline: one succeeds, one is refused, one holder remains | `tests/kernel/test_access_control.py` |
| Permissions, static | Every route's permission is in the catalogue (import-time); TypeScript catalogue and seeded roles equal Python's | `tests/unit/test_access_rules.py`, `tests/static/test_typescript_contracts.py` |
| Tenant isolation | Customer A's administrator cannot read customer B's user by ID (404) | `tests/kernel/test_access_control.py` |

Also covered: catalogue and seeded roles equal the code; the application role cannot write the catalogue or the access version; a release that drops a code revokes it from roles with an audit entry and never re-seeds an edited role; role identity immutable; assignments revoke-only and never deleted; every access change moves the access version; `/me` per seeded type with site scope; declared permission and record-site checks (PERMISSION_DENIED, SITE_SCOPE_DENIED); user create, list, filter, page, If-Match edit, deactivation ending sessions; no self-escalation by site and by permission; super-admin protections; matrix submit writing the difference, auditing each change, returning the preview, and taking effect on the holder's next request with the same token; GxP reason; API clients holding permissions through roles, never Super Admin, secret rotation and disabling; rate limits per principal and per customer with Retry-After. In the browser against the real Core: sign-in through the BFF with real TOTP codes, F03 password step, shell and menus per seeded type, screen guard plus Core's refusal, F22 live users, F36 save reaching another person's menu, CSRF and Origin refusals, token renewal before render.

Unit 4 adds:

| Requirement | Covered | Tests |
|---|---|---|
| Licence limits (AD-27, #30) | Site limit at creation and re-activation, inactive sites not counted, staged to active not counted twice, three concurrent creations for two places give two sites and one LIMIT_EXCEEDED | `tests/kernel/test_organisation.py` |
| Licence state | Read-only state serves organisation reads and refuses organisation writes | `tests/kernel/test_organisation.py` |
| Database guards | Exactly one default location (never none at commit, never two), default active, defined site transitions only, IANA timezones, codes unique ignoring case and fixed, location never moves site, no deletes; users and assignments refer to real departments and sites | `tests/db/test_organisation_schema.py`, `tests/db/test_customer_database.py` (grants) |

Also covered: sites created with their default location; If-Match edits (428, 412); duplicate codes and unknown timezones refused with field errors; location default moved by one command; the default cannot be deactivated; departments; reference data for every principal and changes only with the organisation permissions; assignments at unknown sites and inactive departments refused; `/me` sites per scope (one site, every active site, a deactivated site leaving); public API reference data with a client-credentials token. In the browser against the real Core: F21 sites, status and assigned users, F22 site codes, the location selector per person.

Unit 5 adds:

| Requirement | Covered | Tests |
|---|---|---|
| Provisioning (AD-28) | A run from start to an active customer whose super admin activates and signs in to Core; the customer invisible to Core until activation; a failed pipeline job leaves the run failed with its error and the resume continues from that step; a lost answer from Core after it committed is safe to repeat (same super admin, new code); a stale run is resumed after the executor died; a resume is claimed once; a completed run cannot be resumed; a second start for the customer is refused; GxP needs dedicated placement. In the browser: a customer onboarded through the console's BFF and the real pipeline, handover shown once | `tests/kernel/test_provisioning.py`, `e2e/console-platform.spec.ts` |
| Tenant isolation and AD-13 | Core's provisioning endpoint trusts only the Platform Service's token, takes the customer only from it, and only while that customer's run is at step 6; the Platform Service's secrets store cannot read customer database credentials | `tests/kernel/test_provisioning.py`, `tests/kernel/test_platform_admin.py` |
| Staff identity (MFA, constant work, TOTP replay) | No token before the second factor; one Argon2id verification on every failing path; a TOTP step accepted once; lockout and unlock; refresh rotation and reuse revocation; deactivation ends sessions; platform tokens refused by Core and Core tokens refused by the Platform Service | `tests/kernel/test_platform_admin.py` |
| Permissions | Support engineers refused every administration route; staff creation by system admins only. In the browser: menu and screens by role, the Platform Service's 403 behind them | `tests/kernel/test_platform_admin.py`, `e2e/console-platform.spec.ts` |
| Licensing | Licence state derived from dates and status (active, grace, read-only, suspended, terminated); renewal by a new licence; suspend, reinstate and terminate with the change feed; two racing suspends give one change | `tests/kernel/test_platform_admin.py` |
| Database guards | Run state consistency (completed only at `done`, failed only with an error, handover sealed as a pair), roles, no deletes for the application role | `tests/db/test_platform_schema.py` |
| BFF (LD-49) | Changes without the CSRF header or from another origin refused before forwarding; tokens never readable by page JavaScript; the catch-all never forwards sign-in routes; no session means the sign-in notice | `e2e/console-platform.spec.ts` |
| Contracts | Staff roles, customer statuses and provisioning steps equal on the Python and TypeScript sides | `tests/static/test_typescript_contracts.py` |

Rows of section 17 that depend on later units (inventory rules, workflow, feeds, signatures, work scheduling, API compatibility, webhooks, support tokens) are not covered yet.

## 4. Implementation decisions

These are implementation-level choices consistent with the design. None changes an AD or LD decision.

| # | Decision | Reason |
|---|---|---|
| I-01 | Added `packages/py-common` next to `py-contracts` | Tokens, secrets port, engines and error handling are needed identically by Core, Platform Service and the pipeline; `py-contracts` stays pure data. LLD section 2 lists `py-contracts` only |
| I-02 | Async driver is psycopg 3 with `prepare_threshold=None` | LD-75 requires no prepared statements through a transaction-mode pooler; this driver setting disables them completely and does not depend on a pooler feature |
| I-03 | SQL is written explicitly with `sqlalchemy.text` on `AsyncConnection`, no ORM | LLD gives SQL-level rules (conditional updates, row locks, column grants) that must be visible and exact |
| I-04 | Module boundaries (LD-01) are enforced by an AST check in `tests/static` | LLD asks for "an import-rule linter"; the custom check encodes the three rules exactly, including relative imports |
| I-05 | Change feed: writers take a transaction-scoped advisory lock before the sequence number is assigned | Makes sequence order equal commit order, so a poller using `after_seq` can never skip a late-committing change. Registry writes are rare, so there is no contention. LLD 6.4 only says the 60 s refresh covers a missed notice |
| I-06 | Renewal is a new licence record; terms and modules of an activated licence are immutable (trigger) | Follows "at most one active licence per customer" and `superseded`; keeps licence history auditable |
| I-07 | History columns (`occurred_at`, `seq`, `txid`) are protected by column-level INSERT grants | The application cannot choose when or in what order history happened, in addition to the append-only trigger |
| I-08 | Application role has an empty `search_path` | Forces schema-qualified SQL and removes object-shadowing risk |
| I-09 | GET and HEAD run in a `READ ONLY` transaction | AD-08 "reads write nothing" enforced by PostgreSQL, not by convention |
| I-10 | The response is built before commit and sent only after commit | The idempotency record stores the response in the business transaction (LD-61) |
| I-11 | Service-token verification selects the key set by the claimed issuer, then verifies | Deterministic errors; nothing is trusted before the signature holds |
| I-12 | Inbound `X-Request-ID` is accepted only with a valid BFF service token | Realises "accepted only from the BFF" (LLD 6.1 step 1) using AD-64 service credentials |
| I-13 | File-backed secrets and object stores refuse to start outside `local` and `test` environments | They are development adapters; see open issue U-01 |
| I-14 | Tests run on a dedicated stack marked `ims.cluster_purpose=test` | The suite wipes the cluster; the marker makes that impossible on any other cluster |

| I-15 | Next.js 16 App Router with Tailwind CSS 4; npm workspaces for `apps/*`, `packages/ui`, `packages/api-client` | Within the approved stack (AD-02); one toolchain for both apps |
| I-16 | The three wireframe "Type" workspaces are derived from effective permissions (`access.user.manage`, `issuance.request.approve`, `issuance.issue.fulfil`), not from user-type names | HLD section 3: workflow actors are privileges, not fixed roles; custom roles get the right screens |
| I-17 | Sample data is reachable only through `src/data`, and each data function declares its endpoint | Connecting a screen is a one-place change; the dependency report is generated from these declarations |
| I-18 | Argon2id runs between two short transactions (read, verify, then lock and record) | A customer has four pooled server connections (LLD 6.5); holding one for a ~250 ms hash per sign-in would cap sign-ins at about 16 per second per customer |
| I-19 | The single-use MFA challenge is the challenge token's ID stored on the user row, cleared on success or lockout | Single use without a separate table or deletes |
| I-20 | TOTP secrets are encrypted with AES-256-GCM from a key ring in the secrets store, with the user ID as associated data | At-rest encryption with rotation; a secret copied to another user's row does not decrypt |
| I-21 | Core caches "unknown identifier" answers too, cleared by any directory change | Unknown and known identifiers then cost the same lookups |
| I-22 | Credential-only modules can be mounted without the access stages | Lets the identity routes run before unit 3; the app still refuses tenant routes without all three stages |
| I-23 | TOTP is implemented in the module (about 20 lines, checked against the RFC 6238 vectors) rather than a library; Argon2id comes from `argon2-cffi` | LLD section 2 asks for "a TOTP (RFC 6238) implementation"; no dependency is needed for HMAC-SHA1 |
| I-24 | The permission catalogue and seeded roles live in `ims_contracts.permissions` | Pure data needed identically by Core, the database pipeline (which rebuilds the catalogue) and the web app's mirror |
| I-25 | Super Admin holds every permission by definition and has no `role_permissions` rows; a trigger refuses any row for that role | Nothing to keep in step when the catalogue grows; the role cannot be edited by construction |
| I-26 | Readings of LLD 5.1's seeded types: Type 2 "view all" is every `.view` and `.view_all` permission (including `audit.log.view`, `integration.sync.view`); Type 3 "view stock" adds `catalog.item.view` (stock is read against items), "receive" is `receiving.grn.create`, `.inspect`, `.post`, "validate returns" includes `returns.return.receive` (taking returns in comes first); Type 4 acknowledging and viewing its own records needs no permission (requester-only routes) | The LLD names activities, not codes. Customers can edit every seeded type (#10) |
| I-27 | No lock-out of the super admin: other users cannot edit, deactivate or change the assignments of the super admin; the super admin may edit their own name and email; nobody can deactivate or demote the super admin except by transfer | LLD 7 "changing that user is refused until a transfer completes"; a person editing their own display name cannot lock anyone out |
| I-28 | Rate-limit buckets are kept in each Core process | LLD 16: "No shared cache; any cache can be lost safely". With N instances the ceiling is N times the limit; database limits per customer hold regardless (U-14) |
| I-29 | No self-escalation: adding a permission to a role needs it held at every site (a role can be assigned anywhere); granting a role needs every permission of the role at the assignment's site, or everywhere for an all-sites assignment. Removing is always allowed | LLD 7 "cannot grant permissions they do not hold", applied to site scope |
| I-30 | The first super admin is given Super Admin and User Type 1 at every site | The super admin role is separate from user types (#10); after a transfer the former super admin stays an administrator. Matches the frames' "Super Admin · Type 1" |
| I-31 | Assignment `granted_at` and `revoked_at` both come from the database clock | A check constraint compares them; mixing application and database clocks could fail it |
| I-32 | Effective permissions are a kernel data type (`Grants`) placed on the unit of work by step 8; `Permission(code)` passes at route level when the code is held at one site, and handlers check the record's site | LLD 7: site checks use the loaded record, never a request parameter; lists filter with the allowed sites |
| I-33 | The BFF exchanges a refresh token once per server process and shares the result for 30 s with requests still carrying it | Refresh rotation revokes the session when a spent token is presented (LD-26); a page and its parallel requests would otherwise trip it (U-13 for several BFF instances) |
| I-34 | The web app has two session modes, `core` (default) and `fixtures`, chosen at run time | Screens whose backend does not exist yet stay viewable; nothing switches to sample personas unless asked |
| I-35 | One table maps each screen to the permission of the endpoint it is built on; it drives both the menu and the screen guard | Menu and guard cannot disagree; custom roles get exactly the screens their permissions allow |
| I-36 | Organisation is its own module; access reads sites and departments through `organisation.public`, and the application mounts identity, organisation, then access | Module boundaries (LD-01); access depends on organisation, not the reverse |
| I-37 | A site is created with its default location in one request (`default_location` in `POST /ui/v1/sites`) | The database requires exactly one default location per site at commit (LLD 5.1); a site without one cannot exist even briefly |
| I-38 | The site limit is checked under the advisory lock `org.licensed_sites` at creation and at inactive to active; staged to active is not checked again | Staged sites already count (LLD 5.1); AD-27 checks "at creation or activation" |
| I-39 | Site timezones are validated by PostgreSQL (`pg_timezone_names`), in the service and in a trigger | Daily jobs and site-time display convert in PostgreSQL; Python's time-zone data differs (F-05) |
| I-40 | Site, location and department codes are set at creation and never change (trigger); names and the site timezone are edited with If-Match | Integrations address locations by code (LLD 12 public API) |
| I-41 | List endpoints share one cursor-pagination helper (`kernel/paging.py`): ordered by id, `next_cursor` is the last id | LLD 12: limit 50, maximum 200, next_cursor |
| I-42 | `/ui/v1/me` lists active sites only: every active site for the super admin and for any all-sites assignment, otherwise the active sites of the person's assignments | Staged sites hold no stock and inactive ones are closed; the location selector offers where work happens |
| I-43 | Staff accounts mirror Core's identity rules (Argon2id, TOTP, recovery codes, lockout, rotation) in the Platform Service's own tables, with the credential helpers moved to `ims_common` | One implementation of the security rules for both sign-ins; the Platform Service keeps its own database (AD-13) |
| I-44 | Provisioning steps are recorded one transaction each; the run row is the checkpoint | A step either completed (recorded) or will be repeated; every step is written to be repeatable, as LLD 6.6 requires |
| I-45 | Runs execute in the Platform Service process in the background (`provisioning_in_background`); the API answers 202 and the console polls the run | The steps take seconds to minutes (database creation, migration). Stale runs (no progress for 15 minutes) can be resumed, covering a process that died |
| I-46 | The pipeline port has a subprocess adapter that runs the pipeline CLI with the pipeline's own environment and secrets root | It is what a CI/CD job runs; the Platform Service process never loads migration or cluster credentials (U-04 for the real job trigger) |
| I-47 | `@ims/web-session` holds the BFF logic for both apps; each app passes its backend, cookie names and refresher | Same security rules in both apps; cookie names differ so the apps never mix on a shared host |
| I-48 | The console's session source is chosen at run time like the Tenant Web App's: `platform` (default) or `fixtures` | Same pattern as I-34 |
| I-49 | Console reads go through `fromPlatform()` with a per-request cache, so the layout and the page share one `/customers` read | One read per request; the dependency tables list connected reads |

## 5. Deviations and points to confirm

Small gaps in the LLD that had to be filled to write code. Each is a narrow choice; none is a business rule. Listed so they can be confirmed or corrected.

| # | Point | What was implemented |
|---|---|---|
| D-01 | LLD 6.4 `state()` does not use `valid_from` | Followed literally: a licence is active until `valid_until`. `valid_from` is carried in the snapshot but not evaluated |
| D-02 | A verified token whose customer the Registry positively does not license | 401 AUTH_REQUIRED. The LLD names 503 LICENCE_UNVERIFIABLE only for "no snapshot ever held", which is the outage case and is implemented as such |
| D-03 | Database status `creating`, `failed` or `retired` at pipeline step 5 | 503 DB_BUSY with Retry-After. `migrating` keeps serving (online migrations) |
| D-04 | LLD 12 requires Idempotency-Key on every POST, PUT, PATCH, DELETE | Credential endpoints (access rule "no permission") are exempt: there is no principal to scope the key to |
| D-05 | 405 responses | Added protocol-level code METHOD_NOT_ALLOWED to the error catalogue |
| D-06 | Outbox `subject` column | Stored as `subject_type` and `subject_id` (queryable); the envelope's `subject {type, id, version}` is assembled on the way out |
| D-07 | Customer status transitions | provisioning to active; active and suspended both ways; active or suspended to terminated; terminated is final. Suspended and Terminated behaviour is an AI-filled assumption in the HLD (Project Context 9.2) |
| D-08 | GxP customers on dedicated placement | Enforced by a database CHECK, per HLD section 8. Also an AI-filled assumption (Project Context 9.2) |
| D-09 | Pooler-level `query_timeout` 20 s and `idle_transaction_timeout` 35 s | Added to the local pooler. See finding F-01 |

| D-11 | Wireframes and the LLD disagree on what seeded user types may do (Type 2 item creation, Type 3 exports and audit trail, who decides quality verdicts and more) | **Resolved** by the product owner (17 November): the LLD decides. Personas, menus, screen guard and buttons follow the seeded permissions (Docs/UI_Implementation.md section 10) |
| D-12 | The Platform Console frames show price plans, billing, an expired licence blocking all sites, 7-year audit retention and company SSO | **Resolved** by the product owner: content outside the HLD and LLD is not built. Removed from F51 to F53; the licence note states grace then read-only (Docs/UI_Implementation.md section 10) |
| D-13 | **Conflict in the LLD.** LD-10 says the login pepper is known only to the Platform Service; LLD 6.3 (AD-79) says Core resolves uncached identifiers from the bundle's directory hashes during an outage, which Core cannot do without the hash key | A second keyed hash, `lookup_hash`, with a separate key that products hold (`shared/directory-lookup-key`). The pepper stays platform-only and the bundle carries only lookup hashes. Control-plane migration 0002 adds the column. Both statements now hold. Alternatives would be to share the pepper with Core (breaks LD-10) or to give up bundle-based sign-in for uncached users (breaks AD-79) |
| D-14 | New users' one-time activation code: the LLD names it but not its form or lifetime | 12 characters from an unambiguous alphabet, shown once, stored as SHA-256; valid 72 hours (`activation_code_hours`); failures count toward the lockout. Columns `activation_code_hash` and `activation_expires_at` on `iam.users` |
| D-15 | Suspended and terminated customers at sign-in | Refused with the same generic failure as a wrong password, after the same work. Answering LICENCE_SUSPENDED before authentication would tell anyone that the identifier exists. Refresh, which proves identity, does return the licence codes |
| D-16 | MFA enrolment sequence | `POST /ui/v1/auth/mfa/enrol` creates the secret; the first code sent to `POST /ui/v1/auth/mfa` confirms it, issues the ten recovery codes and opens the session. Both routes are in the LLD list; the split of work between them is not specified |
| D-17 | `iam.sessions.user_id` has no foreign key | Support sessions (LD-83) are for support principals, who are not rows of `iam.users` |
| D-18 | `iam.users.department_id` and `home_site_id` have no foreign keys yet | **Resolved in unit 4**: migration 0004 adds the keys (`NOT VALID`, then validated) |
| D-19 | New error code `PLATFORM_UNAVAILABLE` (503) | Creating a principal needs the Login Directory; no code in LLD section 12 fits an unreachable platform service. Added on both contract sides |
| D-20 | An API client's login identifier is its client ID | AD-22 says API credentials resolve "through the same directory" without naming the identifier |
| D-21 | Role-assignment sites and `/me` sites before the organisation module | **Resolved in unit 4**: assignments refer to real sites (foreign key and a field error), `/me` lists the person's active sites and home site, F22 shows site codes |
| D-22 | "Exactly one super admin … held by an active user" (LLD 7) | Read as invited or active: provisioning creates the super admin as an invited user who activates later. Transfers require an active target (the new holder must be able to sign in) |
| D-23 | Error codes for the built-in rules (not named by the LLD) | PERMISSION_DENIED for super-admin protections, Super Admin role edits and self-escalation (SITE_SCOPE_DENIED when only the site is missing); VALIDATION_FAILED for unknown or reserved permission codes and an inactive transfer target; INVALID_STATE_TRANSITION for a duplicate assignment or repeated deactivation |
| D-24 | Endpoints beyond the LLD 12 route table's resource names | `GET /ui/v1/users/{id}` and `GET /ui/v1/roles/{id}` (they return the ETag an edit needs), `POST /ui/v1/api-clients/{id}/disable` and `/rotate-secret` (LLD 16: "rotatable"). Users carry `last_active_at` (latest session refresh) for F22 |
| D-25 | API client rate limit on creation | Accepted from 1 to 600 per minute: the LLD gives 600 per API client as the limit |
| D-26 | GxP reason for access changes | Role edits, permission changes, assignments and transfers are GMP-relevant ("role and permission changes", LD-82): a reason is required in GxP mode. User profile edits and deactivation are not |
| D-27 | `unread_notifications` in `/me` | `null` until notifications exist (unit 10); the shell draws no count rather than a sample one |
| D-28 | Site status transitions (the LLD lists the statuses only) | staged to active, staged to inactive, active to inactive, inactive to active; nothing returns to staged. Enforced by the service and a trigger |
| D-29 | Status values of locations and departments (the LLD names the column only) | active and inactive. The default location must be active and cannot be deactivated until another location is the default |
| D-30 | Code format and uniqueness | 1 to 32 letters, digits, `.`, `_` or `-`; unique per customer ignoring case. Location codes are unique across the customer, not only per site, because the public API accepts a location code on its own (LLD 12) |
| D-31 | Validity of a user's department and home site | When set or changed, the department must be active and the home site staged or active; a value a user already has is kept if it is later deactivated. Role assignments may name a site in any status |
| D-32 | Organisation changes and the outbox | Audited in the same transaction; no events, because the event catalogue (LLD 13) has none for organisation |
| D-33 | Who sees the reference lists | `GET sites, locations, departments` return every record to any authenticated principal, not only the caller's sites: they are reference data (LLD 12 "Authenticated"), needed for example to pick a transfer destination |

| D-34 | Staff roles (LLD section 4 names `platform_users` without roles) | Two roles from the HLD section 3 actors: `system_admin` (every administration route) and `support_engineer` (no administration rights; support sessions arrive with unit 12) |
| D-35 | Idempotency-Key on `/platform/v1` changes (LLD 12 states the rule for the customer APIs) | Not stored. Each platform command is safe to repeat by its state: one run per customer (a second start is 409), a resume claims a failed or stale run once, transitions already applied are refused, licence numbers are unique. The console's BFF still sends a key with every write |
| D-36 | Internal endpoints the LLD 6.8 table does not list | `POST /internal/v1/provisioning/super-admin` (Platform Service → Core, step 6) and `GET /internal/v1/customers/{id}/provisioning-snapshot` (Core → Platform Service). LLD 6.6 has Core-side work in the run but the Platform Service holds no customer credential (AD-13), so it must ask Core |
| D-37 | **Ordering in LLD 6.6.** The super admin is created before activation, but Core serves only customers with an active licence snapshot | The provisioning snapshot is returned only for a customer in status provisioning whose run is at `initial_users` and running; Core builds a `system` context from it in the kernel. Outside that window Core refuses the call |
| D-38 | Handing over the first super admin's activation code (#21, no email channel) | Sealed on the run and revealed once to a system admin (audited); a second reveal is 409. A repeated step 6 replaces the code |
| D-39 | Runs left running by a process that stopped | A run with no progress for `provisioning_stale_minutes` (15) may be resumed by a system admin |
| D-40 | The first platform staff account (the LLD does not say how it is created) | A command-line tool on the Platform Service host (`ims-platform-admin create-system-admin`), refused once any system admin exists; later accounts are created through `/platform/v1/users` |
| D-41 | Console figures the Platform Service does not hold (users and sites in use, API calls, last activity, uptime, NFR health) | Shown as "—" or "not reported", never estimated (U-17). F52's "Expiring 12 d" pill is replaced by the derived licence state, because the LLD defines no expiry warning period |

## 6. Findings

| # | Finding | Action |
|---|---|---|
| F-01 | PostgreSQL lets any role override its own user-level settings, including `statement_timeout`, by `SET` or `ALTER ROLE ... SET`. The per-customer timeouts of LD-08 / AD-84 are therefore defaults, not hard limits, if the application role were ever made to run such SQL | Application SQL never does this (static check forbids session `SET`). A pooler-level `query_timeout` is added as a backstop the role cannot change, and tested. Recommend stating it in LLD 6.5 / 16 and requiring it of the production pooler |
| F-02 | FastAPI 0.163 no longer copies routes when a router is included; it nests them | Route discovery uses `fastapi.routing.iter_route_contexts`. End-to-end tests prove every tenant route passes the pipeline |
| F-03 | `str.isdigit()` accepts digits of other scripts, and the constant-time comparison then raises | Found by a test: an authenticator code typed in Arabic-Indic digits would have produced a 500. Codes are now ASCII digits only |
| F-04 | A process's first change-feed poll only records the current position | Changes made before that first poll arrive through the 60-second snapshot refresh instead. This is the designed behaviour (LLD 6.4); noted because tests must poll once before making a change they expect as a notice |
| F-05 | Python's time-zone database and PostgreSQL's differ: Python accepted the legacy alias `Asia/Calcutta`, which this PostgreSQL build does not know, so the service accepted a site the database then refused (a 500, found by a test) | PostgreSQL alone decides which timezones are valid (I-39). Recommend stating in LLD section 3 that the database's time-zone data is the reference |

## 7. Unresolved issues and external dependencies

| # | Issue | Impact | Needs |
|---|---|---|---|
| U-01 | Secrets manager and object storage on ZongoVita cloud are unknown (HLD section 4 capabilities; open item #31; Q32 not yet received) | Production adapters for `SecretsStore` and `ObjectStore` cannot be written. Everything else is unaffected: services depend on the ports | ZongoVita |
| U-02 | Managed PostgreSQL details: whether the pipeline identity is a superuser, pooler product and whether it supports auth query, per-database limits and `query_timeout` | The non-superuser path (`GRANT role TO CURRENT_USER`) is written but untested locally | ZongoVita |
| U-03 | Licensable module list (open item #5, Product) | Current tagging of LD-72 is seeded as four modules | Product |
| U-04 | Repository, CI/CD and environments (Q32) | No pipeline definition yet; `pipelines/database` is a CLI ready to be called from one. Provisioning calls it through a port whose current adapter runs the CLI as a subprocess with the pipeline's own secrets; a CI/CD job trigger replaces it once the CI/CD system is known. Dedicated placement (GxP) also needs a dedicated cluster reference: until one is configured, a GxP run stops at the database step with the error kept on the run | ZongoVita |
| U-05 | Design sign-off status | Project Context records development as gated on HLD/LLD sign-off, with the revised HLD's approval "not recorded". Development was started on the product owner's instruction of 16 November | Product owner aware |
| U-06 | Wireframes are missing for screens the LLD requires: MFA enrolment and challenge, recovery-code entry, activation, user and role forms (add, invite, edit, assign), site, location and department forms (create, edit, change status, move the default location), GxP signature dialog and reason field, support grants and break-glass, emergency issue, requester (Type 4) screens, Platform Console screens (sign-in, authenticator and activation; customer onboarding; licence assignment; staff accounts; Enterprises; Audit Trail F54) | Not invented (product owner, 17 November). Consequence: in `core` mode nobody can finish signing in from the browser, because the authenticator step has no screen; the BFF endpoints exist and the browser tests sign in through them. F22's add, invite and edit buttons say their form is not designed. The console shows a notice instead of a sign-in screen; staff sign in through its BFF, and the browser tests do | Design |
| U-07 | Points where frames disagree with the design or each other (Docs/UI_Implementation.md section 10) | Permissions and Platform Console scope are decided (LLD wins; out-of-scope console content removed). Still open: approval policy shape and the F23/F61 chain (#8), taxonomy depth (#11), the console's platform-wide module flags (no `/platform/v1` resource); F21's site type and city, which the LLD's site record does not have (shown as a dash) | Product owner |
| U-08 | The common-password list is a seed of well-known long passwords | Production needs a full breached-password corpus; which one, and whether checked offline, is not decided (LLD section 16 names only "a common-password list") | Product owner / security |
| U-09 | No email channel (#21): activation codes are returned to the creator, to hand over | Works as the LLD describes "until an email channel exists" | ZongoVita |
| U-10 | Argon2id cost must be tuned to about 250 ms on the target hardware (section 16) | Defaults are RFC 9106's second recommendation (3 passes, 64 MiB, 4 lanes) until the hardware is known | ZongoVita cloud |
| U-11 | Permissions added to the catalogue by a later release | They reach Super Admin automatically; they are not added to existing seeded or custom roles, because customers may have edited those (#10). Whether a new permission should join User Type 1 (or others) needs a product rule | Product owner |
| U-12 | The BFF's own service credential (AD-64) for passing request IDs to Core | Not wired: Core assigns request IDs to BFF calls. The BFF's signing key needs the secrets manager (U-01) | ZongoVita |
| U-13 | Refresh-token rotation behind several BFF instances | One process exchanges a refresh token once (I-33); two instances could each present it and revoke the session. Needs session affinity at the load balancer or a shared exchange. The console's BFF uses the same exchange (`@ims/web-session`), so the same applies to it | ZongoVita (deployment) |
| U-14 | Rate limits are per Core instance (I-28) | A customer behind N instances can reach N times the limit. A shared limiter would need a shared store, which the LLD rules out (section 16) | Architecture, if exact limits matter |
| U-15 | Deactivating a site or location that holds stock | The LLD says staged sites hold no stock and that receiving needs an active site, but not whether a site or location with stock may be deactivated. Unit 4 cannot check stock (no stock tables yet); Inventory Core (unit 9) needs the rule | Product owner |

| U-16 | Recovery approvers (LLD 6.6 step 6, LD-84) | Provisioning does not designate them yet: they live in the break-glass tables of unit 12, which will add the step | Unit 12 |
| U-17 | Usage per customer for the Platform Console (users and sites in use, API calls, last activity) and platform health figures | The LLD defines no interface from Core to the Platform Service for usage, and the platform tier holds no customer data (AD-13). F51 and F52 show these as not reported. Needs a decision on whether Core reports aggregate usage, and how | Architecture / product owner |

Open items #8 to #37 in HLD section 11 are unchanged. Their defaults will be implemented as customer settings as each module is built.

U-11, U-13, U-14 and U-15 are unchanged by unit 5: nothing in it needed them decided (U-13 is noted as applying to the console's BFF too).

## 8. Next unit: workers

Scope from LLD 14 (background jobs), 5.4 (jobs tables) and 6.3:

- Job queue (`jobs.jobs`, `jobs.periodic_runs`): claim with `FOR UPDATE SKIP LOCKED`, leases extended each minute, lapsed leases requeued, back-off 30 s × 2^attempt up to 8 attempts, dead jobs alerted; every job idempotent (LD-48); periods claimed before queuing (LD-24).
- Work-pending index (LD-76, AD-10): Core's hints to `POST /internal/v1/work-hints`, workers polling `GET /internal/v1/work-pending` every second, a 60-second safety sweep, fair service across customers, jobs by licence state (LLD 6.4).
- Outbox dispatch and the Login Directory activation worker (LLD 6.3: reserve → create → activate), which units 2 and 3 currently complete inline.
