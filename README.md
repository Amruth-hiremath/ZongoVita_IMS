# ZongoVita IMS

Multi-tenant inventory management: one shared application, one PostgreSQL database per customer.

- Design: `Docs/` (HLD, LLD, Project Context). These are the authority.
- Implementation status, decisions and open issues: `Docs/Implementation_Progress.md`.
- Web apps: how the screens are built from the wireframes and what they wait for: `Docs/UI_Implementation.md`.

## Layout

| Path | What |
|---|---|
| `services/core/ims_core` | IMS Core (FastAPI): `kernel/` (request pipeline), `modules/` (business modules), `schema/` |
| `services/core/migrations` | Customer-database migrations |
| `services/platform` | Platform Service (Licence Registry) and Control-Plane migrations |
| `pipelines/database` | The only executor of provisioning DDL, migrations and partition maintenance |
| `packages/py-contracts` | Wire contracts: problem details, licence snapshot, event envelope, enums |
| `packages/py-common` | Shared runtime helpers: IDs, tokens, secrets and object-store ports, PostgreSQL engines |
| `apps/tenant-web` | Customer web app (Next.js) |
| `apps/platform-console` | ZongoVita staff web app (Next.js) |
| `packages/ui` | Shared React components and design tokens |
| `packages/api-client` | TypeScript API contracts |
| `e2e` | Browser tests for both web apps (Playwright) |
| `tools` | Repository scripts |
| `deploy/local` | Local PostgreSQL 16 + PgBouncer (transaction mode) |
| `tests` | `unit/`, `db/`, `kernel/`, `static/` |

## Prerequisites

Python 3.13, [uv](https://docs.astral.sh/uv/), Docker, Node.js 20.9 or later.

```bash
uv sync
```

```bash
npm install
```

```bash
npx playwright install chromium
```

## Running the tests

The database and kernel suites need a dedicated test stack. The suite wipes every IMS database
and role on it at the start of each run, and refuses to run against a cluster that is not marked
as the test cluster.

```bash
IMS_PG_PORT=54321 IMS_POOLER_PORT=64321 IMS_CLUSTER_PURPOSE=test docker compose -p ims-test -f deploy/local/docker-compose.yml up -d --build --wait
```

```bash
uv run pytest
```

```bash
uv run pytest -m "not slow"
```

PowerShell sets the variables differently:

```powershell
$env:IMS_PG_PORT=54321; $env:IMS_POOLER_PORT=64321; $env:IMS_CLUSTER_PURPOSE="test"; docker compose -p ims-test -f deploy/local/docker-compose.yml up -d --build --wait
```

## Lint and format

```bash
uv run ruff format .
```

```bash
uv run ruff check .
```

## Development stack

A separate stack for running the services locally (direct port 54320, pooler 64320):

```bash
docker compose -p ims-local -f deploy/local/docker-compose.yml up -d --build --wait
```

## Web apps

The Tenant Web App signs in to IMS Core through its BFF (`IMS_SESSION_SOURCE=core`, the default; `IMS_CORE_URL` points at Core). Screens whose Core module does not exist yet show the wireframes' sample data. To view every screen with the sample personas instead, set `IMS_SESSION_SOURCE=fixtures`.

The Platform Console signs ZongoVita staff in to the Platform Service through its own BFF (`IMS_CONSOLE_SESSION_SOURCE=platform`, the default; `IMS_PLATFORM_URL` points at the Platform Service, default `http://127.0.0.1:8081`). Overview and Licenses read the registry; Platform Config shows sample data. The console has no sign-in screen yet (no wireframe), so staff sign in through `/bff/auth/login` and `/bff/auth/mfa`, as the browser tests do. To view the screens on sample data instead, set `IMS_CONSOLE_SESSION_SOURCE=fixtures`.

The first system admin is created on the Platform Service host; it prints a one-time activation code to hand over, and later staff accounts are created through `/platform/v1/users`:

```bash
uv run ims-platform-admin create-system-admin --identifier admin@zongovita.example --name "First Admin"
```

```bash
npm run dev:tenant
```

```bash
npm run dev:platform
```

The tenant app runs on http://localhost:3000; the Platform Console on http://localhost:3100.

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
npm run test:e2e
```

The browser tests build both apps in production mode and serve the tenant app twice, on sample data (3200) and signed in to IMS Core (3201), and the console twice, on sample data (3300) and signed in to the Platform Service (3301). For the live ones, `tools/e2e_backend.py` serves Core on 8180 and the Platform Service on 8181 against the test stack: it wipes and re-provisions that stack, so do not run the browser tests and `uv run pytest` at the same time. It creates ZongoVita staff (a system admin and a support engineer) and onboards a demo customer through a real provisioning run; staff and customer people sign in with real passwords and authenticator codes, and their test credentials go to the git-ignored `e2e/.auth/`.
