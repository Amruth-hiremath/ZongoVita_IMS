# ZongoVita IMS: Implementation Progress

Living record of what is built, how it was verified, what was decided at implementation level, and what is unresolved. The HLD and LLD remain the authority for design; this file never overrides them.

Last updated: 17 November 2026.

## 1. Status

| # | Unit | State |
|---|---|---|
| 1 | Tenancy, licensing and transaction foundation | Done, verified (168 tests; 175 with the UI contract checks) |
| 2 | Identity and session: Login Directory, users, login, MFA, refresh, lockout | Next |
| 3 | Access control: permission catalogue, roles, user types, super-admin rules, authorisation stage, rate limits, `/me` | Pending |
| 4 | Organisation (sites, locations, departments) and licence limits | Pending |
| 5 | Platform administration API, provisioning runs, platform users | Pending |
| 6 | Workers: job queue, outbox dispatch, work-pending index, service levels | Pending |
| 7 | Workflow and approval engine | Pending |
| 8 | Catalogue; vendors and purchase records | Pending |
| 9 | Inventory Core; receiving; issuance; transfers; counts; returns and quality | Pending |
| 10 | Replenishment, alerts, reporting and export | Pending |
| 11 | Integration: public API, events feed, webhooks, connectors, sandbox | Pending |
| 12 | GxP signatures, support grants, break-glass | Pending (hooks for reason-for-change already in the kernel) |
| 13 | Next.js apps (Tenant Web App, Platform Console) | Screens built from all 43 wireframes on sample data; each connects to Core as its backend unit lands (Docs/UI_Implementation.md) |
| 14 | Staged migration rollout, load test, deployment artefacts | Pending |

The order follows dependencies: every module needs the kernel (unit 1); authorisation needs identities (2 before 3); site-scoped permissions need sites (4); stock modules need workflow gates and the catalogue (7, 8 before 9).

Git: units 1 and the UI are committed on local `main`; later units are developed on their own local branches. Nothing is pushed.

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

## 3. Verification

`uv run pytest`: 168 passed (about 2 minutes). `uv run ruff check .`: clean.

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

Rows of section 17 that depend on later units (super admin, inventory rules, workflow, feeds, identity, signatures, work scheduling, API compatibility, webhooks) are not covered yet.

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

| D-11 | Wireframes and the LLD disagree on what seeded user types may do (Type 2 item creation, Type 3 exports, who decides quality verdicts and more) | Sample personas follow the wireframes for item creation and the LLD elsewhere; the table is in Docs/UI_Implementation.md section 10 |
| D-12 | The Platform Console frames show price plans, billing, an expired licence blocking all sites, 7-year audit retention and company SSO | Built as drawn; each statement is listed against the current design in Docs/UI_Implementation.md section 10 |

## 6. Findings

| # | Finding | Action |
|---|---|---|
| F-01 | PostgreSQL lets any role override its own user-level settings, including `statement_timeout`, by `SET` or `ALTER ROLE ... SET`. The per-customer timeouts of LD-08 / AD-84 are therefore defaults, not hard limits, if the application role were ever made to run such SQL | Application SQL never does this (static check forbids session `SET`). A pooler-level `query_timeout` is added as a backstop the role cannot change, and tested. Recommend stating it in LLD 6.5 / 16 and requiring it of the production pooler |
| F-02 | FastAPI 0.163 no longer copies routes when a router is included; it nests them | Route discovery uses `fastapi.routing.iter_route_contexts`. End-to-end tests prove every tenant route passes the pipeline |

## 7. Unresolved issues and external dependencies

| # | Issue | Impact | Needs |
|---|---|---|---|
| U-01 | Secrets manager and object storage on ZongoVita cloud are unknown (HLD section 4 capabilities; open item #31; Q32 not yet received) | Production adapters for `SecretsStore` and `ObjectStore` cannot be written. Everything else is unaffected: services depend on the ports | ZongoVita |
| U-02 | Managed PostgreSQL details: whether the pipeline identity is a superuser, pooler product and whether it supports auth query, per-database limits and `query_timeout` | The non-superuser path (`GRANT role TO CURRENT_USER`) is written but untested locally | ZongoVita |
| U-03 | Licensable module list (open item #5, Product) | Current tagging of LD-72 is seeded as four modules | Product |
| U-04 | Repository, CI/CD and environments (Q32) | No pipeline definition yet; `pipelines/database` is a CLI ready to be called from one | ZongoVita |
| U-05 | Design sign-off status | Project Context records development as gated on HLD/LLD sign-off, with the revised HLD's approval "not recorded". Development was started on the product owner's instruction of 16 November | Product owner aware |

Open items #8 to #37 in HLD section 11 are unchanged. Their defaults will be implemented as customer settings as each module is built.

| U-06 | Wireframes are missing for screens the LLD requires: MFA enrolment and challenge, activation, GxP signature dialog, support grants and break-glass, emergency issue, requester (Type 4) screens, several Platform Console screens | These cannot be built to a design until drawn; the identity backend (unit 2) does not depend on them | Design |
| U-07 | Points where frames disagree with the design or each other (Docs/UI_Implementation.md section 10) | Screens follow the frames as drawn until decided | Product owner |

## 8. Next unit: identity and session

Scope from LLD 5.1, 6.2, 6.3, 6.8:

- Platform Service: directory resolve, reservations, activate, disable, list; pepper and HMAC hashing; change-feed entries of type `directory`.
- Core: directory cache with change-feed eviction and bundle fallback (the listener hook already exists on `SnapshotStore`).
- Customer schema: `iam.users`, `iam.mfa_factors`, `iam.mfa_recovery_codes`, `iam.sessions`, `iam.api_clients`.
- Flows: login, MFA challenge and enrolment (TOTP, recovery codes), refresh with rotation and reuse detection, logout, activation code, client-credentials grant.
- Constant-time login (LD-80), lockout, password policy.
- The principal stage (pipeline step 6).
- Reserve, create, activate sequence for user creation needs the worker; until unit 6 exists the activation step will be callable directly and covered by reconciliation tests.

New dependencies within the approved stack: an Argon2id implementation and a TOTP implementation (LLD section 2).
