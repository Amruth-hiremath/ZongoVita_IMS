# ZongoVita IMS: UI Implementation

How the Next.js apps are built from the wireframes (`Docs/ZongoVita-IMS.zip`), where sample data lives, how the Tenant Web App signs in to IMS Core, and what each screen still needs from it.

**Authority (product owner, 17 November 2026).** The wireframes decide visual design, layouts, labels and screen appearance. The HLD and LLD decide functionality, business rules, permissions, workflows, licensing and security. Where a frame gives a user type different rights from the LLD's seeded user types, the LLD wins and the UI shows effective permissions. Platform Console content that is not in the HLD or LLD (price plans, billing, seven-year audit retention and similar) is not built. Screens that have no wireframe (MFA, activation and others) are not invented; they stay listed as design gaps until designs exist.

## 1. Structure

| Path | What |
|---|---|
| `packages/ui` (`@ims/ui`) | Design tokens and shared components. The only place colours, borders and type sizes are defined |
| `packages/api-client` (`@ims/api-client`) | TypeScript side of the API contracts: error codes, licence state, permission catalogue, `/me` shape |
| `apps/tenant-web` | Customer app (LLD: Tenant Web App). Frames F03 to F50, F60, F61 |
| `apps/platform-console` | ZongoVita staff app, a separate deployment (AD-04). Frames F51 to F53 |

Inside each app:

| Path | Rule |
|---|---|
| `src/app` | Routes. Pages are server components; a `"use client"` file sits beside a page only where the screen has interaction |
| `src/data` | The data layer. Every read is a function here, and it names the Core endpoint it stands in for |
| `src/fixtures` | Sample data transcribed from the wireframes. Nothing outside `src/data` (and `src/session/server.ts`) may import it; ESLint enforces this |
| `src/session` | Who is signed in (`server.ts`), which workspace they see and their menu (`workspace.ts`), which screens they may open (`access.ts`), session cookies and token refresh (`tokens.ts`), reads from Core for server components (`core.ts`) |
| `src/app/bff`, `src/bff` | The backend-for-frontend (LD-49): `/bff/auth/*` for the credential steps, `/bff/[...path]` forwarding to Core's `/ui/v1` |
| `src/components` | App-level pieces shared by several routes |
| `src/lib` | Formatting helpers |

## 2. Rules

1. **Match the wireframe.** Same layout, labels, columns, order, pills and tones. Text is transcribed verbatim, including the designers' references such as `(FB-09)` or `(Q7)`.
2. **No new visual language.** Compose from `@ims/ui`. Use only the palette in `packages/ui/src/styles.css`. If a frame needs something the kit lacks, build it beside the route with the same tokens.
3. **No inline styles.** The apps run under a strict Content Security Policy (LD-49); `style` props are a lint error. Sizes are Tailwind classes; a computed width is an SVG attribute (see `Meter`).
4. **No fabricated backend.** Reads come from `src/data` functions. Where Core has the endpoint they call `fromCore({ endpoint, note }, path, live, sample)`, which reads Core when signed in to it; otherwise `fromFixture({ endpoint, note }, value)`. Actions that would change data and are not connected use `ActionButton endpoint="…"`, which says what it is waiting for: the endpoint, or (`waitingFor="design"`) a drawn form for an endpoint Core already has. No fake success states.
5. **Presentational interaction is real.** Tabs switch, filters narrow the rows on the page, toggles and checkboxes change, chips select, dialogs open and close. These need no backend.
6. **API-shaped data.** Types in `src/data` use `snake_case`, decimal strings for quantities and money, ISO 8601 UTC timestamps (LLD section 12). Format for display with `src/lib/format.ts`.
7. **Permission-aware.** Show a control only if `hasPermission(me, code)` allows it; label by action, not by role (LLD section 15). Which screens a person may open is one table, `src/session/access.ts`: the sidebar shows only those entries, and the `(app)` layout renders "Not available" for any other screen reached by its address.
8. **Responsive.** Frames are 1440 px wide. Layouts use grid and flex that stack below `lg`; nothing may overflow the page horizontally.

## 3. Shared kit (`@ims/ui`)

| Component | Use |
|---|---|
| `AppShell` | Top bar, sidebar, content frame. Mounted once in each app's layout |
| `PageHeader` | `title`, `subtitle`, `breadcrumbs`, `badges`, `actions`, `leading` |
| `Button`, `ButtonLink` | `variant`: `primary` (blue gradient), `secondary`, `danger` (pink), `soft` (pale blue), `link`; `size`: `md`, `sm` |
| `Card`, `CardHeader`, `CardBody` | White panel, 1.4 px gray border, 8 px radius |
| `StatCard` | KPI tile: `label`, `value`, `hint`, `badge` |
| `SectionLabel` | Small-caps heading above a table or field group |
| `KeyValue` | "label … value" row; wrap a group in `<dl>` |
| `NoteBox` | Tinted box inside a card; `tone`: blue, amber, green, red, violet, gray |
| `Pill` | Status pill; `tone`: green, amber, red, blue, violet, gray, dark; `small` |
| `Chip` | Selectable filter chip; `selected` turns it dark |
| `Table`, `THead`, `TBody` (`zebra`), `TR`, `TH`, `TD` | `TD` props: `align`, `numeric`, `muted`, `strong` |
| `Field`, `Input`, `Select`, `Textarea`, `Toggle`, `Checkbox` | `Input`: `leading`, `trailing`, `compact`; `Select`: `leading`, `compact`, `raised` |
| `Tabs` | `variant`: `underline` or `segmented`; items carry their `content` |
| `Callout` | Full-width bar; `tone`: info, warning, danger, success; `dismissible` |
| `Timeline` | Vertical event list; first entry highlighted |
| `Stepper` | Horizontal steps; `state`: done, current, upcoming |
| `Meter` | Thin progress bar |
| `Pagination` | Page tokens plus "Next" |
| `Modal` | Centred dialog over a dimmed page |
| `useNotice` | Bottom-right notice; used by `ActionButton` |

Measurements taken from the frames: content width 1136 px inside a 32 px gutter; rows of cards are 24 px apart; KPI tiles 16 px apart; the usual two-column split is a flexible left column with a 412 px right column (`grid-cols-[minmax(0,1fr)_412px] gap-6`).

## 4. Workspaces

The wireframes are drawn for three people. The LLD makes access a matter of permissions, not role names, so the app derives a workspace from effective permissions (`src/session/workspace.ts`):

| Workspace | Derived from | Wireframe persona | Menu |
|---|---|---|---|
| admin | `access.user.manage` | Arjun Mehta, Super Admin · Type 1 | Dashboard, Items & Catalog, Categories, Vendors & Purchases, Quality Register, Locations, Users & Types, Privileges, Approvals, Audit Trail, Settings |
| manager | `issuance.request.approve` | Priya Sharma, User Type 2 | Dashboard, Items, Receive, Issuance, Approvals, Returns, Transfers, Stock Counts, Alerts & Reorder, Reports, Audit Trail |
| store | `issuance.issue.fulfil` | Suresh Patil, User Type 3 · Store | Dashboard, Fulfilment Queue, Scan & Issue, Receive, Quarantine, Returns, Counts, Transfers (the frame's Audit Trail entry needs `audit.log.view`, which the seeded Type 3 does not have) |
| requester | none of the above (User Type 4) | none | No wireframes exist |

Where one menu entry leads to a different screen per workspace, the route's `page.tsx` switches on `session.workspace`. Each menu is the drawn one minus the entries whose screen the person may not open (`src/session/access.ts`), so a custom role sees exactly what its permissions allow.

Sample personas (`fixtures` mode only) carry the LLD's seeded permissions (`packages/api-client/src/permissions.ts`, checked against Core). A fourth persona, `type3_audit`, is the store user with a customer-made role adding `audit.log.view`; it exists to show F50, which no seeded type can open.

## 5. Frame to route map

Tenant Web App (`apps/tenant-web`):

| Frame | Screen | Route | Workspace |
|---|---|---|---|
| F03 | Login | `/login` | — |
| F04 | Dashboard — Type 1 | `/dashboard` | admin |
| F05 | Inventory Overview | `/dashboard` | manager |
| F48 | Namaste, Suresh (store dashboard) | `/dashboard` | store |
| F07 | Items & Catalog | `/items` | admin, manager |
| F08 | Add / Configure Item | `/items/new` | admin |
| F09 | Item detail | `/items/[itemCode]` | manager |
| F60 | IT Asset Mapping | `/items/assets` | admin |
| F25 | Category & Subcategory Management | `/categories` | admin |
| F37 | Vendors | `/vendors` | admin |
| F38 | Vendor detail | `/vendors/[vendorCode]` | admin |
| F39 | Vendor Onboarding | `/vendors/onboarding/[vendorCode]` | admin |
| F40 | Purchase Records | `/purchase-records` | admin |
| F41 | Purchase Record detail | `/purchase-records/[poNumber]` | admin |
| F33 | Supplier Quality Register | `/quality-register` | admin |
| F21 | Locations | `/locations` | admin |
| F22 | Users & User Types | `/users` | admin |
| F36 | Privilege Matrix | `/privileges` | admin |
| F23 | Approval Workflow Configuration | `/approvals/configuration` | admin |
| F61 | Workflow Builder | `/approvals/workflows/[workflowId]` | admin |
| F27 | Approval Workspace | `/approvals` | manager |
| F28 | Locks & Reservations | `/issuance` | manager |
| F29 | Store Fulfilment Queue | `/fulfilment` | store |
| F11 | Issue Stock | `/scan-issue` | store |
| F12 | Issue — Guard-rail States | `/scan-issue/guard-rails` | store |
| F42 | Receiving — Inward Pipeline | `/receive` | manager |
| F10 | Receive Stock (GRN) | `/receive` | store |
| F32 | Quarantine Validation Queue | `/quarantine` | store |
| F43 | Returns — Lifecycle & Dispositions | `/returns` | manager |
| F49 | Returns — Store Processing | `/returns` | store |
| F15 | Transfer lifecycle | `/transfers`, `/transfers/[transferNo]` | manager |
| F14 | Transfer — New Request | `/transfers`, `/transfers/new` | store |
| F17 | Variance Review | `/stock-counts`, `/stock-counts/[countNo]/variance` | manager |
| F16 | Stock Count sheet | `/stock-counts`, `/stock-counts/[countNo]` | store |
| F18 | Alerts & Reorder Suggestions | `/alerts` | manager |
| F19 | Reorder Rule | `/alerts/reorder-rules/[itemCode]` | manager |
| F44 | Reports — Catalog & Deliveries | `/reports` | manager |
| F24 (1) | Audit Trail | `/audit` | admin |
| F24 (2) | Audit Trail | `/audit` | manager |
| F50 | Audit Trail — WH-BLR-01 | `/audit` | store |

Platform Console (`apps/platform-console`):

| Frame | Screen | Route |
|---|---|---|
| F51 | Platform Overview | `/overview` |
| F52 | Licenses & Plans | `/licenses` |
| F53 | Platform Config | `/config` |

## 6. Endpoint names

Use these when declaring a dependency in `fromFixture` or `ActionButton` (LLD section 12, UI API `/ui/v1`). If a screen needs something not listed, name the closest resource and say what is missing in `note`.

| Area | Endpoints |
|---|---|
| Session | `GET /ui/v1/me`; `GET /ui/v1/notifications`; reference data `GET /ui/v1/sites`, `/locations`, `/departments`, `/uoms`, `/reason-codes`, `/quality-categories`; `GET`/`PATCH /ui/v1/settings` |
| Organisation, access | `/ui/v1/sites`, `/locations`, `/departments`; `/users` (list, create, edit, deactivate); `/role-assignments`; `/roles`, `/privilege-matrix`, `PUT /roles/{id}/permissions`; `/super-admin/transfer`; `/api-clients`; `/support-grants`; `/recovery-approvers` |
| Catalogue | `GET /ui/v1/taxonomy`, `/items`, `/attribute-definitions`, `/scan/{code}`; `POST /taxonomy/proposals`; `POST /taxonomy/nodes/{id}/retire`; `POST /items`, `POST /items/{id}/submit`, `PATCH /items/{id}`, `/items/{id}/image`, `POST /items/{id}/deactivate`; `/numbering-schemes`; `PATCH /assets/{id}` |
| Inventory | `GET /ui/v1/stock`, `/items/{id}/lots`, `/assets`, `/transfers`, `/ledger` |
| Purchasing | `GET /ui/v1/vendors`; vendor writes, `/vendors/{id}/rates`, `/vendors/{id}/status-requests`; `GET`/`POST /purchase-records`, `POST /purchase-records/{id}/close-balance` |
| Receiving | `POST /ui/v1/grns`; `PUT /grns/{id}/records/{record_id}/inspection`; `POST /grns/{id}/post` |
| Issuance | `/ui/v1/issue-requests` (create, submit, cancel, list); `POST /issues/{id}/acknowledge`, `/dispute`; `GET /fulfilment-queue`; `POST /fulfilment-queue/{id}/scans`, `/complete`; `POST /emergency-issues` |
| Approvals | `GET /ui/v1/approval-tasks`; `POST /approval-tasks/{id}/approve`, `/reject`; `/approval-policies` |
| Transfers | `/ui/v1/transfers` (create, submit, cancel); `POST /transfers/{id}/dispatch-scans`, `/receive-scans` |
| Counts | `/ui/v1/count-sessions` (create, start, cancel); `/count-sessions/{id}/lines`, `/submit` |
| Returns, quality | `/ui/v1/returns`; `POST /returns/{id}/receive`; `GET /quarantine-queue`; `/returns/{id}/validation`, `/verdict`; `GET /quality-cases`, `/supplier-quality`; `POST /quality-cases/{id}/dispose` |
| Replenishment | `GET /ui/v1/planning`, `/reorder-suggestions`, `/formulas`; `PATCH /planning`; `/planning/threshold` |
| Alerts, reports, audit | `GET /ui/v1/alerts`; `POST /alerts/{id}/acknowledge`; `GET /reports`; `POST /exports`; `GET /audit` |
| Integration | `/ui/v1/webhook-subscriptions`, `/deliveries`, `/replay`; `/connectors`; `/mappings`; `/sync-logs` |
| Platform Console | `/platform/v1/customers`, `/licences`, `/provisioning-runs`, `/migrations`, `/break-glass-requests`, `/users`, `/audit` |

## 7. Status

All 43 frames are built: 40 in the Tenant Web App and 3 in the Platform Console. The sidebar entries that have no frame (tenant Settings; console Enterprises and Audit Trail) show a "No wireframe for this screen" panel instead of an invented screen.

**Two session modes** (`IMS_SESSION_SOURCE`, read at request time):

| Mode | Session | Screens |
|---|---|---|
| `core` (default) | IMS Core: the BFF keeps the access and refresh tokens in HttpOnly, Secure, SameSite=Lax cookies; the session is `GET /ui/v1/me` (name, role label, effective permissions per site, licence state); the proxy renews an expiring access token before a page renders | Shell, menu and screen guard from `/me`; F22 Users and F36 Privilege Matrix live (`GET /ui/v1/users`, `GET /ui/v1/privilege-matrix`, `PUT /ui/v1/roles/{id}/permissions`); every other screen still shows sample data, and a strip above the top bar says so |
| `fixtures` | A wireframe persona chosen on the sign-in card (an HttpOnly cookie, no credential) | Every screen on sample data, for viewing frames whose backend does not exist yet |

**Signing in** (`core` mode). F03 submits the work email and password to `POST /bff/auth/login`. Every sign-in then needs the authenticator step (LD-79): its screen, MFA enrolment, recovery-code entry and activation have no wireframes, so F03 reports "Password accepted" and states that the next screen has no approved design yet. The BFF endpoints for those steps exist and are exercised by the browser tests (`/bff/auth/mfa/enrol`, `/bff/auth/mfa`, `/bff/auth/activate`, `/bff/auth/logout`). Until the screens are designed, a person cannot finish signing in from the browser (Implementation_Progress U-06).

**BFF rules** (LLD 15): writes need `X-IMS-CSRF: 1` and an `Origin` equal to the app's (`IMS_PUBLIC_ORIGIN` behind a rewriting proxy); each write carries an `Idempotency-Key` (the page's, or one the BFF generates); `TOKEN_EXPIRED` refreshes once and replays with the same key; credential routes are never forwarded by the catch-all, so no token reaches page JavaScript. A refresh token is exchanged once per server process however many requests carry it (LD-26 revokes a session on reuse).

## 8. Verification

| Check | How | Result |
|---|---|---|
| Every frame renders, with the drawn title, the menu and the sample-data marker | `e2e/tenant-screens.spec.ts`, `e2e/platform-screens.spec.ts` (Playwright, production build) | Passing |
| No console errors and no Content Security Policy violations on any screen | Same tests; the production build runs the strict policy (no `unsafe-inline`, no `unsafe-eval`) | Passing |
| Nothing scrolls sideways at 1440 px or on a 390 px phone (LLD 15) | Same tests, at both widths | Passing |
| Menus, names and roles per persona; every menu entry opens a screen; signed-out visitors are sent to sign-in | `e2e/tenant-shell.spec.ts`, `e2e/platform-screens.spec.ts` | Passing |
| Detail routes know only the drawn record (others 404); the console has no route into customer screens | Same | Passing |
| Actions that need the backend say so and name the endpoint | `e2e/tenant-shell.spec.ts` | Passing |
| Security headers: per-request nonce CSP, `frame-ancestors 'none'`, HSTS, `nosniff` | `e2e/tenant-shell.spec.ts` | Passing |
| Screens outside a persona's permissions are not rendered; menus follow the LLD's seeded permissions | `e2e/tenant-shell.spec.ts` | Passing |
| Signed in to the real IMS Core: F03 password step, shell and menu from `/ui/v1/me` per seeded type, screen guard plus Core's own refusal, F22 live users, F36 save reaching another person's menu at once, BFF CSRF and Origin checks, token renewal before render | `e2e/core.setup.ts` (sign-in through the BFF with real TOTP codes), `e2e/core-access.spec.ts`, against `tools/e2e_backend.py` | Passing |
| Visual match with the wireframes | Each screen captured at 1440 × 900 beside its frame and compared section by section | Layouts, labels, columns, pills and tones match. Remaining differences are listed in section 10 |
| TypeScript contracts match the Python ones; sample data reached only through `src/data`; no inline styles | `tests/static/test_typescript_contracts.py` | Passing |
| Types and lint | `npm run typecheck`, `npm run lint` | Clean |

Commands (the Core-mode project starts `tools/e2e_backend.py`, which wipes and re-provisions the `ims-test` database stack, so do not run it alongside `uv run pytest`):

```bash
npm run test:e2e
```

```bash
IMS_SCREENS_DIR=.screens npm run screens:capture
```

The second saves one screenshot per frame into `.screens/` for side-by-side review with the wireframes.

## 9. What the screens need from the backend

The tables below are generated from the code (`node tools/ui-dependencies.mjs --write`): every `fromCore` and `fromFixture` read and every `ActionButton` endpoint. The third column is the gap each screen found between what it shows and what the LLD's endpoint describes. Many screens show summary figures (dashboard tiles, KPI rows) for which the LLD has no summary resource; those notes say which data the summary needs.

Screens the LLD requires but the wireframes do not draw. These have to be designed before they can be built:

| Screen | LLD reference |
|---|---|
| MFA enrolment (authenticator QR code, recovery codes) and MFA challenge (code or recovery code) | 6.2, LD-79, section 15 "Sign-in includes MFA enrolment, MFA challenge and recovery-code entry" |
| Account activation with the one-time code; password change | 6.2 |
| Add, invite and edit a user; assign and revoke roles at sites; create and edit custom roles; super-admin transfer; API clients (create, show the secret once, rotate, disable). Core has every endpoint (unit 3) | 7, 12 |
| GxP signature dialog (password, TOTP, meaning) and the reason-for-change field | 8, section 15 |
| Support grants and recovery approvers (super admin); pending break-glass approvals | 7, section 15 |
| Emergency issue in read-only licence state | LD-86, section 15 |
| Requester (User Type 4) screens: raise requests and returns, acknowledge receipt | 5.1, 9.2 |
| Platform Console: enterprises, platform audit trail ("F54"), onboarding wizard ("F35"), provisioning runs, migrations, break-glass requests, staff users | 6.8, section 15 |

<!-- generated: ui-dependencies begin -->
### Tenant Web App

Reads connected to IMS Core (2):

| Endpoint | Data function file | Notes |
|---|---|---|
| `GET /ui/v1/privilege-matrix` | `data/privileges.ts` | Rows are the permission catalogue grouped by the LLD's module groups; F36's twelve capability rows are not in the LLD. |
| `GET /ui/v1/users` | `data/users.ts` | Rows show role assignments (user types, custom roles, site scope), last activity (latest session refresh) and status. Site codes need the organisation module (unit 4). |

Reads served from sample data (59):

| Endpoint | Data function file | What the screen needs beyond the LLD's description |
|---|---|---|
| `GET /ui/v1/alerts` | `data/alerts.ts` | Rows join open alerts with GET /ui/v1/reorder-suggestions (suggested qty, lead PO + vendor days); channel switches come from GET /ui/v1/settings; the formula and dead-stock explainers need GET /ui/v1/formulas and the per-SKU dead-stock threshold, which no endpoint returns yet. |
| `GET /ui/v1/alerts` | `data/dashboard.ts` | Open stock alerts with on hand and minimum per item and location. |
| `GET /ui/v1/approval-policies` | `data/approval-config.ts` | One policy per activity with its workflow id, trigger condition, escalation and on/off state; the chain of the selected policy with its options; and the tenant-wide reminder cadence, escalation target and override rule. |
| `GET /ui/v1/approval-policies/{id}` | `data/workflows.ts` | The builder needs the policy as a graph (trigger, condition split, approver steps per branch, outcomes) plus its version history; the LLD describes policies as chains, so the branch shape is to be confirmed. |
| `GET /ui/v1/approval-tasks` | `data/approvals.ts` | Tasks scoped to the approver's sites, with the request's lines, live free stock per location for each line, the lock that approval would create (free before/after, other pending requests for the SKU), out-of-stock lines' external purchase-request reference, and the queue's median wait. |
| `GET /ui/v1/approval-tasks` | `data/dashboard.ts` | Open tasks across all sites with the user type the task waits on. |
| `GET /ui/v1/approval-tasks` | `data/dashboard.ts` | Tasks assigned to the caller, with a one-line summary of the requested lines and free stock. |
| `GET /ui/v1/assets` | `data/assets.ts` | Rows need serial, item code and name, status and custodian with location; the summary needs counts by status and the item codes holding assets; the drill-in needs the item's numbering, category path, stock on hand, asset counts and next warranty expiry. |
| `GET /ui/v1/attribute-definitions` | `data/item-form.ts` | Custom attributes required for the selected category (Q5). |
| `GET /ui/v1/audit` | `data/audit.ts` |  |
| `GET /ui/v1/audit` | `data/audit.ts` |  |
| `GET /ui/v1/audit` | `data/audit.ts` | {…} The store view is limited to the user's granted site (FB-23) and also needs an action kind per row (issue, receipt, count, transfer, approval, quality, quarantine) and a month filter. |
| `GET /ui/v1/audit` | `data/dashboard.ts` | Latest four entries, newest first. |
| `GET /ui/v1/audit` | `data/dashboard.ts` | Today's entries by the caller and on the caller's requests, newest first. |
| `GET /ui/v1/connectors` | `data/dashboard.ts` | Connector state, API version, last sync and today's event and failure counts (GET /ui/v1/sync-logs); free connector slots from the licence. |
| `GET /ui/v1/count-sessions` | `data/dashboard.ts` | The caller's count session in progress, if any. |
| `GET /ui/v1/count-sessions/{id}/lines` | `data/stock-counts.ts` | Needs the session header (type, location, scope, blind flag, counted / total) with the lines; system quantity must be withheld for blind counts; cursor pagination with an uncounted-first order. |
| `GET /ui/v1/count-sessions/{id}/lines` | `data/stock-counts.ts` | Variance view of a submitted session: system and counted quantity, variance and value impact per line, the reason entered, the adjustment each approval would post, and the adjustment approval policy from GET /ui/v1/approval-policies (Q3). |
| `GET /ui/v1/formulas` | `data/reorder-rules.ts` | Per-SKU formula with its variables and their sources, the category template it overrides, the propagation flag, and a live preview from GET /ui/v1/planning (values per location, lead time split into internal PO and vendor supply, FB-18). |
| `GET /ui/v1/fulfilment-queue` | `data/dashboard.ts` | No dashboard summary resource. Needs queue size with earliest SLA, POs due (GET /ui/v1/purchase-records), open and overdue quarantine lines, counts in progress and whether they are blind. |
| `GET /ui/v1/fulfilment-queue` | `data/dashboard.ts` | Approved and locked requests at the caller's site. |
| `GET /ui/v1/fulfilment-queue` | `data/fulfilment.ts` | Rows need the lock time and SLA; each entry needs its pick list with lot and bin per stocked line, scan status, and lines that left as external purchase requests (FB-10) with their reference; the acknowledgement reminder rule comes from GET /ui/v1/settings. |
| `GET /ui/v1/fulfilment-queue` | `data/issues.ts` | The issue form needs the queue entry with its next issue number, issue-from location, issue-to targets (user, production line, retail sale, linked Asset Maintenance work order), the request and lock it releases, and per line the free and locked stock at that location and the lot; line value comes from item cost. |
| `GET /ui/v1/issue-requests` | `data/issuance.ts` | The LLD has no list of locks; this needs approved requests with their lock (item, location, quantity, locked at, by whom, state), including locks released today. |
| `GET /ui/v1/items` | `data/item-detail.ts` | Single item by code with attributes, flags and creator. Stock by location from GET /ui/v1/stock, lots from GET /ui/v1/items/{id}/lots, thresholds and lead time from GET /ui/v1/planning, movements from GET /ui/v1/ledger. |
| `GET /ui/v1/items` | `data/item-form.ts` | Item lifecycle states are not enumerated in the UI API; the form needs the allowed set. |
| `GET /ui/v1/items` | `data/item-form.ts` | Sample values as drawn; a new item starts empty. |
| `GET /ui/v1/items` | `data/items.ts` | List rows need on-hand, locked and quarantined totals, location count and a stock-status summary per item; search, category, location and status become query parameters with cursor pagination. |
| `GET /ui/v1/ledger` | `data/dashboard.ts` | Latest movements and lock events in scope, newest first. |
| `GET /ui/v1/numbering-schemes` | `data/item-form.ts` | Prefix and next running number for the selected category (Q6). |
| `GET /ui/v1/purchase-records` | `data/dashboard.ts` | Expected POs for the site plus today's posted GRNs in one list. |
| `GET /ui/v1/purchase-records` | `data/purchase-records.ts` | Rows need inward date or due date, inspection result and expected-use date; the summary needs quarter count and value, awaiting-inward and exception counts and average internal and vendor lead time. Search, status, vendor and department become query parameters. |
| `GET /ui/v1/purchase-records` | `data/receiving.ts` | Needs purchase records awaiting inward with inspection outcome, plus a GRN list (no GET /ui/v1/grns in the LLD route table), the KPI counts and the inspection review of an exception PO (findings and the store's note). |
| `GET /ui/v1/purchase-records/{id}` | `data/purchase-records.ts` | Detail with the vendor's rate, MOQ and lead time at the time of the PO, the GRN inspection (by, when, verdict, comments), the record lifecycle and stock provenance (ledger movements traced to this record, GET /ui/v1/ledger). |
| `GET /ui/v1/quarantine-queue` | `data/dashboard.ts` | Open validations with their ageing state. |
| `GET /ui/v1/quarantine-queue` | `data/quarantine.ts` | Needs the held lines with reason, hold start, vendor and PO attribution, the KPI counts (units held, awaiting validation, average hold time against the validation window, released today) and each line's validation checklist as last saved through /ui/v1/returns/{id}/validation. |
| `GET /ui/v1/reorder-suggestions` | `data/dashboard.ts` | Top four by urgency; lead time split into internal PO days and vendor days. |
| `GET /ui/v1/reports` | `data/dashboard.ts` | No dashboard summary resource in the UI API. Needs: site count with live/staged split (GET /ui/v1/sites), item and category counts, active users by user type, pending approval tasks and requests, stock value across all locations. |
| `GET /ui/v1/reports` | `data/dashboard.ts` | System health (uptime this month vs NFR-1, concurrent users vs NFR-2, last backup / PITR per NFR-6) has no UI API resource; it comes from platform monitoring. |
| `GET /ui/v1/reports` | `data/reports.ts` | Needs the report catalogue scoped to the caller's user type and site (FB-23) with last run, schedule and a state summary per report; recent outputs with format, recipients and delivery state; scheduled deliveries; the month's run counts and KPI tiles; and the vendor quality roll-up preview (also served by GET /ui/v1/supplier-quality). |
| `GET /ui/v1/returns` | `data/returns.ts` | Needs returns in flight with stage and state, the KPI counts, the quarantine record of a return awaiting verdict (store validation, hold since, vendor and PO), disposition options from GET /ui/v1/settings, and per-vendor FAIL roll-up from GET /ui/v1/supplier-quality. |
| `GET /ui/v1/returns` | `data/returns.ts` | Store queue: returns at this site with the store's last action, the return being validated (ordered vs supplied), routing by reason code (GET /ui/v1/reason-codes) and per-vendor poor-quality rates from GET /ui/v1/supplier-quality. |
| `GET /ui/v1/settings` | `data/item-form.ts` | Internal PO lead time, the manual part of total lead time (FB-18). |
| `GET /ui/v1/sites` | `data/locations.ts` | The frame calls sites 'locations'. Each row needs type, city, item count, stock value, SKU numbering rule, go-live status (live / staged) and a count of assigned users by user type. |
| `GET /ui/v1/stock` | `data/dashboard.ts` | No dashboard summary resource. Needs stock value, item and location counts, low-stock alert count with critical count (GET /ui/v1/alerts), requests to approve, locked units and live locks, dead-stock value. |
| `GET /ui/v1/stock` | `data/issuance.ts` | Rows need locked and quarantined split out of on hand, free, and the reference holding the lock (issue request or return) with its state; the tiles need counts of active locks, units locked by UoM, over-issue attempts blocked at scan (Q7) and the lock timeout setting (GET /ui/v1/settings). |
| `GET /ui/v1/stock` | `data/transfers.ts` | Free stock per source location (locked units excluded) for each line; also needs GET /ui/v1/locations for the from/to lists, GET /ui/v1/reason-codes for reasons, and the routing preview from GET /ui/v1/approval-policies, which no endpoint returns for a draft yet. |
| `GET /ui/v1/supplier-quality` | `data/quality-register.ts` | Per-supplier poor-item counts for month, quarter and year, poor rate, claims, last feedback event, CAPA and review status; feedback events and corrective actions come from GET /ui/v1/quality-cases. Publishing a feedback event has no endpoint in the LLD route list yet. |
| `GET /ui/v1/taxonomy` | `data/categories.ts` | Each node needs item count and a short line summary; deeper levels load per parent on expand. The latest near-duplicate rejection with its matched node is shown under the tree. |
| `GET /ui/v1/taxonomy` | `data/item-form.ts` | Four-level path; options at each level depend on the parent chosen. |
| `GET /ui/v1/taxonomy/proposals` | `data/categories.ts` | Not in the endpoint list (only POST /taxonomy/proposals is); the queue needs status, proposer, parent and the dedupe result. Approve and reject go through the approval task (WF-014). |
| `GET /ui/v1/transfers/{id}` | `data/transfers.ts` | Needs the step chain with timestamps, lines with sent and received quantities and value, the transfer's audit entries and the type-aware stage actions (who acts at each step and its state). |
| `GET /ui/v1/uoms` | `data/item-form.ts` |  |
| `GET /ui/v1/vendors` | `data/item-form.ts` | Approved vendors (F37) for the preferred-vendor list. |
| `GET /ui/v1/vendors` | `data/vendors.ts` | List rows need catalogue size, smallest MOQ, lead-time range and this month's poor-item count (from GET /ui/v1/supplier-quality) per vendor; the summary needs pending rate revisions. Search, status and supplies-item become query parameters. |
| `GET /ui/v1/vendors/{id}` | `data/vendors.ts` | Detail with catalogue and MOQ, rate revisions (GET /ui/v1/vendors/{id}/rates), per-item lead times and poor-item counts per month, quarter and year. |
| `GET /ui/v1/vendors/{id}` | `data/vendors.ts` | A vendor in the onboarding state, with the wizard step reached and the catalogue lines captured so far. |
| `POST /ui/v1/fulfilment-queue/{id}/complete` | `data/issues.ts` | The three states are this call's outcomes: a problem response for negative stock (Q7) carrying free, locked and on-hand figures; a problem response for a concurrent write (Q20) naming the competing movement; and success. |
| `POST /ui/v1/grns` | `data/receiving.ts` | Reading a draft GRN has no route in the LLD table (GET /ui/v1/grns/{id} is assumed); site, vendor and PO options come from GET /ui/v1/sites, /vendors and /purchase-records; the linked purchase record panel needs purchaser, approver and expected use. |

Actions that are not connected (53):

| Endpoint | Screens |
|---|---|
| `GET /ui/v1/grns/{id}` | `/purchase-records/[poNumber]` |
| `GET /ui/v1/scan/{code}` | `/receive`, `/scan-issue`, `/stock-counts` |
| `GET /ui/v1/scan/{code} · GET /ui/v1/items` | `/receive` |
| `GET /ui/v1/transfers/{…} (delivery challan)` | `/transfers` |
| `PATCH /ui/v1/assets/{id}` | `/items/assets` |
| `PATCH /ui/v1/attribute-definitions/{id}` | `/items/new` |
| `PATCH /ui/v1/items/{id}` | `/items/[itemCode]` |
| `PATCH /ui/v1/items/{id} (generated barcode)` | `/items/new` |
| `PATCH /ui/v1/planning (reset {…} to category template)` | `/alerts/reorder-rules/[itemCode]` |
| `PATCH /ui/v1/reports/{id}/schedule` | `/reports` |
| `PATCH /ui/v1/sites/{id}` | `/locations` |
| `PATCH /ui/v1/users/{id}` | `/users` |
| `PATCH /ui/v1/vendors/{id}` | `/vendors/[vendorCode]`, `/vendors/onboarding/[vendorCode]` |
| `POST /ui/v1/approval-tasks/{…}/approve` | `/approvals` |
| `POST /ui/v1/approval-tasks/{…}/reject` | `/approvals` |
| `POST /ui/v1/approval-tasks/{id}/approve` | `/categories`, `/dashboard` |
| `POST /ui/v1/approval-tasks/{id}/approve (count adjustments, {…})` | `/stock-counts` |
| `POST /ui/v1/approval-tasks/{id}/reject` | `/categories`, `/dashboard` |
| `POST /ui/v1/attribute-definitions` | `/items/new` |
| `POST /ui/v1/connectors/{id}/sync` | `/dashboard` |
| `POST /ui/v1/count-sessions/{…}/submit` | `/stock-counts` |
| `POST /ui/v1/exports` | `/alerts`, `/audit`, `/categories`, `/items`, `/items/assets`, `/purchase-records`, `/purchase-records/[poNumber]`, `/quality-register`, `/quarantine`, `/receive`, `/returns`, `/stock-counts`, `/vendors` |
| `POST /ui/v1/exports (deliver to purchasing)` | `/reports` |
| `POST /ui/v1/exports (format: pdf)` | `/reports` |
| `POST /ui/v1/exports (format: xlsx)` | `/reports` |
| `POST /ui/v1/exports (pick lists)` | `/dashboard` |
| `POST /ui/v1/fulfilment-queue/{…}/complete` | `/fulfilment`, `/scan-issue` |
| `POST /ui/v1/fulfilment-queue/{…}/problem (not in the LLD route table)` | `/fulfilment` |
| `POST /ui/v1/fulfilment-queue/{id}/complete` | `/scan-issue/guard-rails` |
| `POST /ui/v1/grns` | `/receive` |
| `POST /ui/v1/grns/{id}/post` | `/receive` |
| `POST /ui/v1/items` | `/items/new` |
| `POST /ui/v1/items (bulk import)` | `/items` |
| `POST /ui/v1/purchase-records` | `/purchase-records`, `/purchase-records/[poNumber]`, `/vendors/[vendorCode]` |
| `POST /ui/v1/quality-cases/{id}/feedback-events` | `/quality-register` |
| `POST /ui/v1/reorder-suggestions (push to procurement API)` | `/alerts` |
| `POST /ui/v1/returns/{id}/verdict` | `/returns` |
| `POST /ui/v1/sites` | `/locations` |
| `POST /ui/v1/taxonomy/proposals` | `/categories` |
| `POST /ui/v1/transfers` | `/transfers` |
| `POST /ui/v1/transfers/{…}/receive-scans` | `/transfers` |
| `POST /ui/v1/transfers/{id}/submit` | `/transfers` |
| `POST /ui/v1/users` | `/users` |
| `POST /ui/v1/vendors/{id}/rates` | `/vendors/[vendorCode]` |
| `POST /ui/v1/vendors/{id}/status-requests` | `/quality-register`, `/vendors/[vendorCode]` |
| `PUT /ui/v1/approval-policies/{id}` | `/approvals/configuration`, `/approvals/workflows/[workflowId]` |
| `PUT /ui/v1/count-sessions/{…}/lines` | `/stock-counts` |
| `PUT /ui/v1/formulas/{id} (per-SKU rule)` | `/alerts/reorder-rules/[itemCode]` |
| `PUT /ui/v1/fulfilment-queue/{…} (save draft; not in the LLD route table)` | `/scan-issue` |
| `PUT /ui/v1/grns/{id}/records/{record_id}/inspection` | `/receive` |
| `PUT /ui/v1/grns/{id}/records/{record_id}/inspection (fail lines → quality case)` | `/receive` |
| `PUT /ui/v1/returns/{id}/validation` | `/quarantine`, `/returns` |
| `PUT /ui/v1/returns/{id}/validation (photo evidence)` | `/returns` |

### Platform Console

Reads served from sample data (4):

| Endpoint | Data function file | What the screen needs beyond the LLD's description |
|---|---|---|
| `GET /platform/v1/customers` | `data/overview.ts` | Needs, per customer, the database name or provisioning state, users used / licensed, 7-day API call count and last activity; plus platform totals (customers by status, users, uptime, API calls today), recent platform activity (GET /platform/v1/audit) and NFR health figures, which no /platform/v1 resource in LLD section 12 provides. |
| `GET /platform/v1/licences` | `data/config.ts` | Module flags, environment rails and the tenant override boundary have no /platform/v1 resource in LLD section 12; the frame's plan entitlement rails are not part of the design. |
| `GET /platform/v1/licences` | `data/licences.ts` | Registry rows need validity, sites and users used / licensed, modules, the customer database and a status; the grace and read-only dates of the customer nearest expiry are derived from its licence (LLD 6.4). |
| `Platform Console sign-in (Platform Service, MFA mandatory)` | `data/session.ts` | No staff login or session endpoint exists yet. |

Actions that are not connected (4):

| Endpoint | Screens |
|---|---|
| `GET /platform/v1/customers (usage report export)` | `/overview` |
| `PATCH /platform/v1/config (no such resource in the LLD yet)` | `/config` |
| `POST /platform/v1/customers` | `/overview` |
| `POST /platform/v1/licences` | `/licenses` |
<!-- generated: ui-dependencies end -->

## 10. Wireframes against the design

Resolved by the product owner's authority rule (17 November 2026, top of this document) unless marked open. "Built" says what the screens now do.

**Platform Console.** Content outside the HLD and LLD is removed, not built:

| Frame | Drawn | Built |
|---|---|---|
| F51, F52, F53 | Price plans (Starter ₹499, Growth ₹899, Enterprise ₹1,499 per seat per month), plan column, plan upgrades, seat add-ons, billing sync and export, "Plan entitlement rails" | Removed. F52 is titled "Licenses"; the registry shows validity, sites, users, modules (LLD tags), database and status. "Seats" reads "users" (the licence user limit, LLD 5.1) |
| F52 | "EXPIRED → every site of that customer is blocked"; "Renewal & dunning" with reminder, "Grace period 7 d", "Auto-suspend" | The note states LLD 6.4: grace (14 days by default, per contract), then read-only with emergency issue. The panel is "Licence expiry": valid until, grace until, after grace. Suspension is a ZongoVita action, not automatic |
| F53 | Audit retention "7 years"; support tier "Priority · 4 h SLA"; data residency "choice" | Removed. The override boundary keeps "Audit retention · lifetime (Q22)" |
| F51, F53 | "the enterprise's own sign-in"; "OAuth2 + PKCE · company SSO (Q24)"; F03 "Continue with Company SSO" | Password and authenticator (MFA); SSO is Phase 2 (AD-23). The F03 button explains this when pressed |
| F53 | "v1.4 · X-API-Version header"; webhooks "3 retries → dead-letter queue" | `/api/v1`, additive changes only (LLD 12); retries up to 24 h, then parked (LLD 13) |
| F51, F53 | Trials; platform-wide module flags (developer console, SMS, accounting connector) | Trials removed (customer statuses are LLD 4's). Module flags stay as drawn sample data: there is no `/platform/v1` resource for them (open, U-07) |

**Permissions of the seeded user types.** The LLD decides (LLD 5.1); the screens show effective permissions:

| Point | Frames | Built |
|---|---|---|
| Type 2 creates and edits items | F07 "+ Add item"; F22 "Create / configure items: Yes" | Type 2 has no `catalog.item.create`; the button is not shown and F22's summary reads "No" |
| Type 2 issues stock and takes in returns | F22 "Receive / issue / return stock: Yes" | Type 2 approves; Type 3 receives, issues and validates. F22 reads "No" for Type 2 |
| Type 2 manages vendors | F22 and F36: no | Type 2 "manage vendors and formulas": `purchasing.vendor.manage` |
| Type 3 exports | F32 "Export hold report", F49 "Returns log", F50 "Export CSV" | Type 3 has no `reporting.export.run`; export buttons follow the permission |
| Type 3 decides quality verdicts | F32 "Fail → quality-hold", "Override → restock" | The store submits its validation (recommendation); `returns.verdict.decide` is Type 2's |
| Type 3 sees an audit trail | F50, and "Audit Trail" in the store menu | Type 3 has no `audit.log.view`: the entry is hidden and `/audit` is refused. F50 is shown to a store user whose role adds that permission |
| Type 2 issues from the item page | F09 "Issue stock" | A link to the issuance screen |
| Type 2 confirms transfer receipt | F15 "Confirm receipt" | Hidden: `transfers.transfer.receive` is Type 3's |
| Sign in "as Type 2 / Type 3" | F03 two sign-in buttons | One "Sign in": what a person may do comes from their role assignments, not a choice at sign-in (`fixtures` mode keeps the persona buttons) |
| Type 1 is the super admin | F36 "Type 1 · super admin"; F22 Type 1 pill dark | The super admin is one person holding the separate Super Admin role (HLD, #10); F36 shows a fixed Super Admin column and Type 1 as "all but reserved" |

**F22 and F36 on the LLD's permission model.**

| Point | Frames | Built |
|---|---|---|
| F36 rows | Twelve capabilities ("Raise issuance request", "Configure privileges", …) | The LLD's matrix is per permission (section 7): rows are the 62 permission codes in the LLD's module groups, site-scoped ones marked "per site", reserved ones locked to Super Admin. A capability label maps to several codes or to none, so ticking one could not be stored faithfully |
| F36 editing | Every box tickable | The Super Admin column is fixed; reserved permissions cannot be ticked for other roles; a permission you do not hold at every site cannot be added (no self-escalation, LLD 7). Core refuses all three again. After saving, a panel lists each changed role and who it now applies to (the LLD's effective-permission preview) |
| F36 "How privileges work" | "assigned a type · effective privileges are that type's set"; guard "One super-admin type" | "assigned one or more roles, at every site or at one · effective privileges are their union"; guard "One super admin: exactly one person, always … changed only by transfer" (LLD 7) |
| F22 summary | Capability rows with Yes / No per type | The drawn capability rows, each read as the LLD permissions listed in its "Applies to" cell; "Yes" when a type holds all of them, "Partly" when some, from the live matrix |
| F22 list | Location codes, "last active", Active / Inactive | Site scope shows "All locations" or a site count until the organisation module provides site codes (unit 4); last active is the latest sign-in or session refresh; statuses Active, Invited, Inactive (suspended or deactivated) |
| F22 "+ Add user", "Invite user", "Edit" | Buttons | Core has the endpoints (`POST /ui/v1/users`, `PATCH /ui/v1/users/{id}`) but no form is drawn; the buttons say so (open, U-06) |

**Workflow and catalogue** (open; unchanged).

| Point | Detail | Open item |
|---|---|---|
| Approval chains or approval graphs | F61 draws a policy as a graph (condition split, branches, "posts instantly" path). LLD 8 defines a policy as ordered levels, each with an optional condition | #8 |
| F23 and F61 disagree on the transfer chain | F23: step 2 "value > ₹5,000 only", escalation "24 h → Ops". F61: split at ₹5,000, step 2 "second signature if value > ₹25,000", escalation "24 h → Ops Head" | #8 |
| Taxonomy depth | F25 subtitle says "Two-level taxonomy"; its tree says "4 levels", L0 to L3; F08 draws a four-level path | #11 |
| F25 duplicate match | Proposal queue says "94% similar → Bearings & Bushings"; the tree says "94% match → Deep Groove" | — |

**Endpoints the screens need that the LLD route table does not list.** Each is declared in code with a note (section 9): summary figures for dashboards and KPI rows; a list of active locks (F28); GRN list and detail (F41, F42); saving a fulfilment draft and reporting a fulfilment problem (F11, F29); pushing suggestions to procurement (F18); report schedules (F44); connector "Sync now" (F04); publishing supplier feedback events (F33); taxonomy proposal queue (F25); platform configuration (F53).

**Sample data that disagrees with itself.** Transcribed as drawn, not corrected. Examples: free stock of SPB-6204 at WH-BLR-01 is 52 in F27 and F28 but 12 in F11 and F12; F17's net impact "−₹1,065" against line impacts of −555 and +620; several pagers show ten pages for five records. These matter only as sample data and disappear with real data.

## 11. Results

Latest run, 17 November 2026:

| Suite | Result |
|---|---|
| Browser tests (`npm run test:e2e`, production builds of both apps; tenant app on sample data and signed in to the real Core) | 117 passed (15 against the real Core) |
| Python suite including the TypeScript-contract and UI checks (`uv run pytest`) | 266 passed |
| `npm run typecheck`, `npm run lint` | Clean |

Problems the browser tests found and the fixes:

| Problem | Fix |
|---|---|
| Platform Console pages were prerendered at build time, so their scripts had no CSP nonce and the browser blocked them | Both root layouts render per request (`connection()`); Next.js applies nonces only to dynamically rendered pages |
| Screen-reader-only header labels escaped the tables' scroll box and widened the page on phones | The kit's table scroll wrapper is a positioning context |
| Responsive grids with no base column grew to their widest table on phones | Every responsive grid has a shrinkable base column |
| Under parallel load, navigation and sign-in took longer than the test timeout because every page view prefetched every menu entry | Sidebar links no longer prefetch: every screen is rendered per user, so prefetching only multiplied server work |
| Dates printed as "26 Sept 2026" (the runtime's en-GB month), not the frames' "26 Sep 2026" | One date module (`src/lib/dates.ts`) with its own month names |
| Signed in to Core, a page and its data reads render in parallel with the layout's guard, so a signed-out or unpermitted visit still asked Core for the screen's data (refused, logged as a server error) | Pages that read Core check the session and the screen permission first |
| Next.js's route announcer also has `role="alert"`, so tests looking for "the" alert found two | Tests select the alert that has text |
