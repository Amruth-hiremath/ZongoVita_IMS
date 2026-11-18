# ZongoVita IMS: working notes for Claude

## Start here

1. `Docs/Implementation_Progress.md`: what is built, what is next, decisions, deviations, open issues. Update it at the end of every unit of work.
2. `Docs/ZongoVita_IMS_Low-Level_Design_LLD.docx` and `..._High-Level_Design_HLD.docx`: the authority. `Docs/ZongoVita_IMS_Project_Context.md` explains why decisions were made and who made them.

The `.docx` files are not directly readable. Extract them to text (zip + `word/document.xml`, keeping headings and tables) into the scratchpad before working on a new area; the diagrams are in `word/media/`.

## Rules of the project

- Implement the HLD and LLD. Do not redesign, do not invent business requirements, do not leave placeholders for complex behaviour. Raise genuine conflicts or missing specifications instead of assuming.
- Stack is fixed: Next.js, Python FastAPI (every backend service), PostgreSQL. Nothing else.
- Git: commit only locally; never push. Each implementation unit gets its own branch from `main`.
- Cite the design in code and tests by its IDs (AD-nn, LD-nn, #n open items, LLD section numbers).
- Values the LLD "assumes" for open items are customer settings (`kernel/tenant_settings.py`) unless they are code rules.
- A feature is done when it works through the real pipeline against real PostgreSQL through the pooler, with tests. A route or screen existing is not done.

## Invariants that must never be weakened

- The customer comes only from a verified token or API credential. No endpoint accepts a customer or database identifier (AD-21).
- `DatabaseRouter.transaction(ctx)` is the only way to a customer database, and `TenantContext` is built only in `ims_core/kernel` (static tests enforce both).
- One transaction per command: change + audit + outbox event + idempotency key (AD-08). Services never commit.
- Platform Service holds no customer-data or DDL credential (AD-13). DDL runs only in `pipelines/database`.
- Audit, ledger and similar history are append-only by grant and by trigger. No hard deletes outside the LLD exception list (`ims_core/schema/access.py`).
- No session state in SQL: no session `SET`, `LISTEN/NOTIFY`, session advisory locks, temp tables, prepared statements (LD-75).
- Every tenant route goes through `ImsRouter` with `@declare(access=..., read_only_ok=...)`.
- Every sign-in path does exactly one Argon2id verification and fails with the same generic answer (LD-80); tests count verifications. Argon2id never runs inside a database transaction.
- The login pepper never leaves the Platform Service; products resolve identifiers by the separate lookup hash (D-13).
- Exactly one super admin, reserved permissions only with Super Admin, Super Admin role not editable, assignments revoke-only: enforced in the database (migration 0003), not only in services. Every role, permission or assignment change bumps `iam.access_version` by trigger (permission caches depend on it).
- Licence limits (AD-27): users and sites are counted under a transaction-level advisory lock at creation or activation (`iam.licensed_users`, `org.licensed_sites`). Exactly one default location per site, defined site transitions and fixed codes are enforced in the database (migration 0004). Valid timezones are whatever PostgreSQL knows (F-05).
- A route's `Permission(code)` must be in `ims_contracts.permissions.CATALOGUE`; the TypeScript mirror (`packages/api-client/src/permissions.ts`) must stay equal (static test). Site-scoped checks use the loaded record's site through `uow.grants`, never a request parameter.
- The web app never gives page JavaScript a token: tokens live in HttpOnly cookies handled by `/bff` route handlers and the proxy; the BFF catch-all never forwards `auth/*`; writes need `X-IMS-CSRF` and a matching `Origin`.

## Commands

- Install: `uv sync`
- Test stack: see `README.md` (project `ims-test`, ports 54321 / 64321).
- Tests: `uv run pytest` (about 5 minutes; `-m "not slow"` skips the two tests that wait on real timeouts).
- Browser tests: `npm run test:e2e` (starts `tools/e2e_backend.py`, which wipes the test stack: never run it alongside pytest).
- Lint: `uv run ruff format .` then `uv run ruff check .`

## Conventions

- SQL is explicit (`sqlalchemy.text`), schema-qualified, upper-case keywords. The application role has an empty `search_path`.
- Migrations are plain SQL lists run through `ims_common.ddl.execute_statements`; they only expand; `downgrade()` raises. New tables must be classified in `ims_core/schema/access.py`, and partitioned ones registered in `ims_core/schema/partitions.py`.
- When the schema head changes, update `ims_core/schema/version.py` (a test compares it with the migrations).
- Errors: raise `DomainError(ErrorCode.X)`; status and title come from `ims_common.problem.ERROR_CATALOGUE`.
- Windows: the async PostgreSQL driver needs a selector event loop (`ims_common.pg.use_selector_event_loop_on_windows`; the test suite sets it).
- After `ruff format` rewrites files, re-read them before editing.

## Web apps

- Read `Docs/UI_Implementation.md` before touching `apps/` or `packages/ui`. The wireframes (`Docs/ZongoVita-IMS.zip`, SVG with outlined text) are the visual authority: render them to PNG in the scratchpad to read them.
- Next.js 16: read the bundled docs in `node_modules/next/dist/docs/` rather than relying on memory (`proxy.ts`, async `params`, CSP nonces).
- Wireframes decide look and labels; the HLD/LLD decide behaviour and permissions (product owner, 17 November 2026). Do not invent screens the wireframes lack (MFA, activation, user forms): leave a design-gap notice.
- Session source: `IMS_SESSION_SOURCE=core` (default, Core through the BFF) or `fixtures` (sample personas). Which screens a person may open is `src/session/access.ts` (menu and guard).
- No inline styles (strict CSP). Reads only via `src/data` functions that name their endpoint: `fromCore` once Core has it, `fromFixture` until then; unconnected data-changing buttons are `ActionButton` (`waitingFor="design"` when only the form is missing). Regenerate the dependency tables with `node tools/ui-dependencies.mjs --write` (a test checks them).
- Commands: `npm run typecheck`, `npm run lint`, `npm run test:e2e`.

## User preferences

Concise, no emojis. Distinguish stakeholder decisions from AI proposals and label assumptions. Involve the user only for business decisions, conflicting requirements, significant architectural change or external dependencies.
