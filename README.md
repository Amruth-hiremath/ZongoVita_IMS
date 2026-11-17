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

Both apps show the wireframe screens on sample data until the backend endpoints exist.

```bash
npm run dev:tenant
```

```bash
npm run dev:platform
```

The tenant app runs on http://localhost:3000 (sign in with one of the sample personas); the Platform Console on http://localhost:3100.

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
npm run test:e2e
```

The browser tests build both apps in production mode and serve them on ports 3200 and 3300.
