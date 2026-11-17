# ZongoVita IMS — Project Context and History

Compiled on 16 November 2026 from the full project conversation history and project files. All dates are 2026.

This file explains how the project evolved and why decisions were made. It does not replace the HLD and LLD, which are provided separately. Where this file and those documents differ on a current design detail, the documents win. Where they differ on who decided something, this file records the origin.

## How to read this file

Every decision or statement is labelled with its origin:

| Label | Meaning |
|---|---|
| **[Stakeholder]** | Stated or decided by ZongoVita: Ravi, Kshethra CH, the mentor team, a meeting speaker, or the HLD reviewer |
| **[User]** | Decided by the project intern who owns this conversation, on the project's behalf |
| **[AI proposal]** | Proposed by an AI assistant (ChatGPT or Claude). Not a stakeholder decision unless later confirmed |
| **[Superseded]** | No longer current; kept only to explain history |

## 0. Status snapshot (16 Nov)

- **Phase:** design. No code has been written. Development starts only after the design documents are signed off **[Stakeholder, 26 Oct]**.
- **Wireframes:** handled separately by the team. Their final sign-off status is not recorded in this history.
- **HLD:** revised to incorporate the HLD reviewer's November feedback. The reviewer withheld sign-off pending that revision; whether the revised HLD has been sent back and approved is not recorded.
- **LLD:** updated to match the revised HLD.
- **System Design Specification:** not started.
- **Current files (latest):**
  - `ZongoVita_IMS_High-Level_Design_HLD.docx`: HLD, in the team's own document format.
  - `ZongoVita_IMS_Low-Level_Design_LLD.docx`: LLD, in the team's own document format.
- **Stale copies (do not use as current):**
  - `ZongoVita_IMS_HLD.docx`, a first rendering of the revised HLD in a different layout, replaced by the file above.
  - The "ZongoVita IMS — High-Level Design (HLD)" and "ZongoVita IMS — Low-Level Design (LLD)" Claude Docs artifacts. They hold the condensed design from *before* the reviewer's November feedback.

---

## 1. Project objectives and original PRD

### People

| Person | Role (as evidenced in the history) |
|---|---|
| Anant and Amruthesh | Third-year BTech interns assigned the project. The user is one of them; which one is not stated |
| Kshethra CH | ZongoVita Tech Private Limited coordinator; sent the PRD on 9 Sep; receives deliverables |
| Ravi | Principal requirements reviewer. Authored the 15 Sep PDF comments (annotation author "Ravi") and the 25 Oct wireframe comments |
| Mentor team | Supplied the written clarifications folded into Revision B (vendor data, lead time, privileges) |
| 26 Oct meeting "Speaker 1" | Senior ZongoVita person, name not recorded. Confirmed the stack, shared the multi-tenant details and set the deliverable sequence |
| HLD reviewer (November) | Name not stated in the conversation. Issued formal decisions on the HLD open items |

### Original request (9 Sep) [Stakeholder]

Kshethra's email asked the interns to review the requirements document and share an execution plan (approach, timeline, milestones, dependencies, risks) by 10 Sep EOD. The document covered stock tracking, multi-location support and a plug-and-play integration architecture.

### PRD: `ZV_Intern_RD_InventoryManagement.pdf` [Stakeholder]

- **Purpose:** track stock levels, movements and valuation across one or more warehouse/store locations, reducing stockouts, overstocking and manual tracking errors.
- **Scope:** the full inventory lifecycle (receiving, storage, sales/issuance, reporting) for a "small-to-mid-sized business". It must be a modular, plug-and-play component that can be integrated into other systems (Asset Maintenance, ERP, POS, e-commerce) with minimal custom development.
- **Stakeholders named:** warehouse/store staff, inventory/operations manager, purchasing, finance, IT administrator.
- **Functional requirements:**
  - FR-1 items (SKU, name, category, unit, cost, price)
  - FR-2 receipts
  - FR-3 issuance/sales
  - FR-4 multiple locations
  - FR-5 transfers with audit trail
  - FR-6 min/max thresholds and low-stock alerts
  - FR-7 purchase-order suggestions
  - FR-8 barcode/SKU scanning
  - FR-9 batch/lot/expiry (if applicable)
  - FR-10 cycle counts with variance
  - FR-11 roles Admin/Manager/Staff
  - FR-12 dashboard
  - FR-13 reports (valuation, movement, low-stock, dead stock)
  - FR-14 CSV/Excel export and basic API
  - FR-15 documented REST/GraphQL API
  - FR-16 webhooks
  - FR-17 standard JSON data schema
  - FR-18 pluggable connectors
  - FR-19 standalone containerised service
  - FR-20 configurable field mapping
  - FR-21 sandbox and API keys for third parties
  - FR-22 backward-compatible API versioning
- **Non-functional requirements:**
  - NFR-1 99.5% uptime in business hours
  - NFR-2 at least 50 concurrent users
  - NFR-3 encryption in transit and at rest
  - NFR-4 mobile-responsive UI
  - NFR-5 full audit log
  - NFR-6 daily backups with point-in-time recovery
  - NFR-7 loosely coupled modular architecture
  - NFR-8 new integrations in days via configuration
  - NFR-9 OAuth2 / API keys / SSO / SAML compatible
  - NFR-10 core separated from connector layer
- **Integration rules:** the core works independently of any host; connectors translate between the IMS schema and host systems; new connectors are added by configuration or lightweight scripting. The example first connector is Asset Maintenance: spare-part stock sync, work orders linked to consumption, reorder alerts.
- **Assumptions:** accounting/POS integration "required but details TBD"; one warehouse initially, with multi-location within 6 months; budget and go-live TBD.
- **Out of scope (Phase 1):** full ERP/accounting, supplier/vendor portal, demand forecasting/AI.
- **Success criteria:** 90% fewer stock discrepancies within 3 months; 75% fewer stockouts; all staff trained within 2 weeks of launch.

---

## 2. Initial doubts and stakeholder clarifications (9–15 Sep)

**9 Sep [User, AI-assisted].** The user and ChatGPT judged the PRD under-specified for a team that had not yet had a single meeting. A clarification document was produced with questions placed under each PRD point (Q1–Q28) plus general questions (Q29–Q32), and sent to ZongoVita. The questions recorded uncertainty only; they were not requirements.

**15 Sep [Stakeholder].** Ravi answered as PDF comment annotations (`IMS_Requirements_Doubts-withComments.pdf`). The answers, verified against the annotation layer:

| Q | Topic | Answer (verbatim or close) | Status today |
|---|---|---|---|
| Q1 | Industry | Manufacturing | Current |
| Q2 | Inventory type | "Does not matter for the software design" | Current (model stays generic) |
| Q3 | Approvals | Configurable; all activities can be mapped for approval; enterprise defines through UI | Current principle; detail still open (#8) |
| Q4 | Cost vs price | "Same" | Ambiguous; still open (#20) |
| Q5 | Item attributes | Configurable, add/delete per user needs | Current |
| Q6 | SKU generation/uniqueness | "Role based access, only admin users can. Unique to location only" | Partly superseded; see #12 in section 9 |
| Q7 | Over-issue | Blocked | Current |
| Q8 | Returns | Include | Current |
| Q9 | Multi-location | Multi-location (from the start) | Current; replaces the PRD's one-warehouse assumption |
| Q10 | Transfers | Multi-step, configurable | Current; stages still open (#19) |
| Q11 | Reorder logic | Custom formula per SKU, user-decided, linkable to lead time to procure | Current, refined by Revision B |
| Q12 | Alert channels | **No answer** | Still open (#21) |
| Q13 | Purchase orders | Suggestions only; expose API for purchasing | Current |
| Q14 | Batch/expiry | Include; only if applicable per item | Current |
| Q15 | Permissions | Role-based access | Refined by Revision B (user types, IAM-style engine) |
| Q16/Q17 | Valuation / dead stock | "Stock levels - frequency and cost"; dead stock X days defined per SKU | Valuation still open (#20); dead-stock rule current |
| Q18 | REST or GraphQL | "Yes" | Ambiguous then; closed in November: REST + OpenAPI |
| Q19 | Deployment | ZongoVita cloud | Current |
| Q20 | Concurrent updates | First write wins | Current |
| Q21 | Mobile | Web app (responsive, not native) | Current |
| Q22 | Edit/delete history | No; permanent; lifetime | Current |
| Q23 | Tech stack | "Relational DB, React" (no backend named) | **Superseded** 26 Oct: Next.js / FastAPI / PostgreSQL |
| Q24 | Auth standard | OAuth2 | Current; extended in November (MFA in Phase 1, SSO in Phase 2) |
| Q25 | First integration | Asset Maintenance; "API will be shared" | Current; API not yet received |
| Q26 | Connector meaning | Microservice | Current |
| Q27 | Accounting/POS | Optional | Current; replaces the PRD's "required" |
| Q28 | Phase 1 FR boundary | "Answered through comments" | Never given as a list; still open (#33) |
| Q29 | Existing architecture | Standalone | Current |
| Q30 | Existing data | Clean slate | Current |
| Q31 | Test data | Will be shared | Not yet received |
| Q32 | Repo/env/credentials | ZongoVita will share all | Not yet received |

---

## 3. Chronological evolution of requirements and scope (Sep–Oct)

- **15 Sep [User request, AI proposal].** The user asked for a two-month execution plan from the 4th week of September to the 2nd week of November 2026: AI-enabled Agile, MVP first, a fixed deadline in the 2nd week of November. ChatGPT produced it. This was a planning artefact, not a stakeholder decision. Development is now gated behind design sign-off, so that timeline has effectively lapsed. A revised timeline has not been discussed.
- **23 Sep [Stakeholder].** ZongoVita asked for wireframes. These were interpreted as UI/UX wireframes of the application.
- **25 Sep [User].** First wireframe draft shared (screens F03–F34).
- **25 Sep [AI proposal, Superseded].** ChatGPT drafted a preliminary HLD: React, a generic relational DB, OAuth2 + RBAC, REST/GraphQL pending, a connector microservice, Mermaid diagram. On 28 Oct the user said this diagram "was just for initial meeting" and should be ignored.
- **26 Sep [User].** Learning sessions on the architecture (first principles, IMS-specific), then preparation for a 5–10 minute HLD presentation to ZongoVita.
- **Review meeting (date not recorded; between 26 Sep and 13 Oct) [Stakeholder].** The v1.1 wireframe pack (35 frames) was presented. The reviewers traced the item lifecycle end to end and probed:
  - who requests, approves and hands over items;
  - what happens when two people want the same stock;
  - the reorder maths;
  - poor-quality items;
  - whether two companies could share the deployment in isolation (v1.1 had not considered this).

  Revision A of the review response captured 24 feedback items.
- **13 Oct [Stakeholder content, team-authored document].** Revision B shared (section 4). The user then updated the wireframes accordingly.
- **13 Oct [AI proposal, Superseded].** ChatGPT proposed changes to the September HLD Mermaid diagram.
- **15 Oct [AI review].** ChatGPT audited the v2.0 wireframe ZIP (38 screens). Verdict: not ready for the next stage. The problems found:
  - inconsistent quantities across screens;
  - GRN–PO–vendor traceability gaps;
  - permission mismatches, such as a Type 3 user seeing quarantine verdict actions that the privilege matrix does not grant;
  - a restock path still offered after a FAIL verdict, which breaks the one-way quality-hold;
  - an off-spec return defaulting to PASS;
  - missing screens: issuance request, receipt acknowledgement, requester dashboard, returns intake, enterprise onboarding, integration screens and responsive frames.

  The user also asked why "Add Item" appears for both Type 1 and Type 2. The answer: valid only if Type 2 holds that privilege in the matrix.
- **25 Oct [Stakeholder].** Ravi's wireframe comments and the multi-tenant standard arrived (section 5).
- **26 Oct [Stakeholder].** Meeting confirmed the stack and the deliverable sequence (section 5).
- **26 Oct [User].** The user said wireframes were "mostly done" and the main work was now architecting the system. Because the product "is gonna serve lot of orgs/enterprises and tons of users", everything must be planned carefully. The user set the baseline decisions in section 5.

---

## 4. Revision B (October; shared 13 Oct)

`IMS-v2-Review-Response-Feedback-Register-and-Revised-Workflows_updated.pdf`, "Rev. B". This document was prepared by the intern team. It records the review meeting's feedback (FB-01 to FB-24) and the mentor clarifications that followed (FB-25 and FB-26 added, FB-05 corrected). It defines 26 feedback items in 7 themes, 8 diagrams (D1–D8), 11 lifecycle states across 7 stages, and grows the v2.0 screen plan from 12 to 15 new screens. None of the 26 items was rejected or deferred.

**Theme A — Taxonomy (FB-01 to FB-03).**
- Categories become a configured, tenant-scoped tree.
- A semantic duplicate check runs on every proposal.
- New nodes pass an approval gate; retiring a node shows its usage counts and needs approval.
- Revision B fixed the depth at exactly **two levels**. **[Superseded 25 Oct: four subcategory levels.]**

**Theme B — Item onboarding (FB-04, FB-05).**
- An item image can be uploaded.
- FB-05 was corrected in Revision B. It was first heard as "optional external identifier" but actually meant expiry tracking where applicable: structured, alertable per-batch expiry that feeds expiry alerts and first-expiry-first-out guidance.
- The external identifier remains an optional attribute.

**Theme C — Issuance (FB-06 to FB-12).**
- Four actors: requester (raises the request), approver (commits stock), store admin (fulfils by barcode scan), system (enforces the rules).
- Requester and approver both see live availability.
- **The first approval locks the stock.** Locks are released only by issue, rejection, cancellation or a configurable timeout.
- Over-issue is blocked.
- The requester must acknowledge receipt before the issue is complete; pending acknowledgements are reminded.
- A request for an unavailable item is still allowed, is flagged, and raises an external purchase-request event. IMS never creates a PO.
- Alerts carry vendor context.

**Theme D — Returns and quality (FB-13 to FB-16).**
- Every return needs a mandatory reason code: mismatch, wrong item issued, poor quality or damaged.
- Returned units enter quarantine: visible and counted but never issuable, and excluded from reorder.
- Validation compares specification-level attributes, using a checklist pre-filled from the inward inspection. The verdict is binary: OK restocks; FAIL sends the units to **quality-hold, which is one-way**.
- Quality-hold ends in scrap, rework or supplier return.
- A supplier quality register shows results per vendor by month, quarter and year, and raises external feedback events.
- The poor-quality vs damaged distinction is configurable.

**Theme E — Replenishment (FB-17 to FB-19).**
- Thresholds are suggestions that the approver-equivalent user type accepts or overrides per SKU.
- A default formula plus a selectable library.
- Reviewer verdict: "You have used a right formula in a wrong manner". Lead time = vendor supply time + internal PO generation time.
- PO generation time is entered by users: a tenant default with a per-SKU override. Vendor supply time is set per vendor-item on the vendor master.
- Worked example kept as demo data: usage 10/day, supply 10 days, safety 5, on hand 5 gives 100 units. Adding 3 PO days gives **130 units**.

**Theme F — Multi-tenancy and privileges (FB-20 to FB-24).**
- The platform licenses enterprises.
- Onboarding chain: enterprise → sites → users, each created by the level above.
- A ZongoVita system admin runs the platform with no visibility into tenant inventory.
- **Exactly one super admin per enterprise.**
- Numbered user types 1–4 replace Admin/Manager/Staff labels. A privilege matrix screen (user types × capabilities, tick and submit) sits on an **IAM-style configurable engine**: permissions are grouped into roles, user types are seeded roles, and tenants can add custom roles. The mentor team confirmed this direction.
- Three guards cannot be configured away: tenant isolation, read-only audit, and a single super-admin equivalent.
- **[Superseded 25 Oct]** Revision B assumed one shared deployment with tenant scoping "at the query layer", replaced by one database per customer.

**Theme G — Vendor and purchase records (FB-25, FB-26; mentor-specified).**
- No existing ZongoVita module can be integrated, so the records are built natively.
- **Vendor master:** a lifecycle (onboarding → active → suspended/retired) with company registration, the items the vendor supplies, MOQ per item, a rate list, lead time per item, and quality history.
- **Purchase record:** created when the PO is raised and completed at inward. It carries item code, PO number, user department, purchased by, purchase approved by, date of inward, inspection details (by whom, when, comments), and expected usage or issue date.
- The module plugs into five places: item onboarding (preferred vendors), receiving, returns/quality attribution, reorder lead time, and vendor-context alerts.

**Lifecycle states (D1):**
1. Registered (SKU unique per warehouse in Revision B's wording)
2. In Stock
3. Locked
4. Issued
5. In Use
6. Returned
7. Quarantined
8. Restocked
9. Quality-Hold
10. Disposed
11. Reorder-Triggered

**Availability:** free stock = on-hand − locked − quarantined, everywhere.

---

## 5. Late-October stakeholder changes and decisions

### 25 Oct — Ravi's wireframe comments [Stakeholder]

The original comment images are **not available**; only an assistant's paraphrase survives. The six changes:

1. Item codes can be entered manually or auto-generated as running numbers in a user-defined format.
2. **Four subcategory levels**, replacing Revision B's two.
3. Multiple IT assets map to one item code; each asset keeps its own identity.
4. One vendor can supply multiple items, each with its own MOQ, rate and lead time.
5. The supplier quality register is incomplete. What is missing was not stated.
6. Approvals and workflows must be custom-defined.

### 25 Oct — "Multi-Tenant Handling — Standard Approach" diagram [Stakeholder]

Shared by the 26 Oct meeting's Speaker 1; the diagram is `multiTenant.png`. It says the approach "applies to every ZongoVita product": one application for all customers, separate data for each. The application flow is: login → identify customer → check licence → use that customer's database only. The Licence Registry holds customer → licence (validity, number of sites, users, modules) and customer → database, and no customer business data.

The diagram's five rules:

1. One database per customer; never mix two customers' data in the same table.
2. Sites stay inside their customer's database.
3. The customer is identified at login, never accepted from user input.
4. The licence is checked on every request; if expired, all of that customer's sites are blocked. **[Rule 4's expiry behaviour was changed for IMS by the November HLD reviewer; see section 6.]**
5. A new customer = a new database + one Licence Registry entry, with no change to existing customers.

### 26 Oct — meeting [Stakeholder]

- **Stack:** front end **Next.js**; back end **Python, FastAPI only** ("Don't use other than FastAPI"); database **PostgreSQL**. The interns had suggested a relational DB / Postgres; ZongoVita confirmed PostgreSQL.
- **Multi-tenant licensing** must be considered "for each function" developed.
- **Deliverables, in sequence:**
  1. revised wireframes (with Ravi's comments and everything discussed);
  2. high-level system architecture diagram;
  3. low-level design including tech stack, database, data storage and workflows;
  4. the full specification documents.
- Share each deliverable as soon as it is ready; do not wait to send everything at once.
- **Sign-off gates:** wireframe sign-off first; then design and specification sign-off; then development.

### 26 Oct — the user's baseline decisions [User]

- The multi-tenant diagram settles multi-tenancy and licensing.
- Taxonomy: the newer requirement wins, so **four subcategory levels**.
- Item codes and assets: the approach as described above is agreed.
- Custom workflows: **TBD**.
- Scale: **follow the original PRD**. **[Superseded in November: 5,000 concurrent users.]**
- Integrations and security: **TBD**.

ChatGPT then read "four subcategory levels" as four levels beneath a top category, five in total. That was an **[AI proposal]**; the depth question remains open (#11).

---

## 6. Multi-tenancy, licensing and architecture discussions (chronological)

1. **Revision B (Oct) [Superseded]:** one deployment, tenant scoping at the query layer.
2. **25 Oct standard [Stakeholder]:** a database per customer plus a Licence Registry (section 5).
3. **28 Oct understanding report [AI proposal].** Claude reviewed all sources and raised a register of 34 open questions (#1–#34; #35–#37 were added later). Four were judged to block HLD finalisation:
   - who owns and builds the Licence Registry (#1);
   - how the customer is identified at login (#2);
   - the licence-failure policy (#3);
   - whether the 50-user target is per customer or platform-wide (#4).
4. **28 Oct HLD first draft [AI proposals].** The main architectural proposals:
   - a modular-monolith IMS Core;
   - a separate Platform Service with a Control-Plane database;
   - a Login Directory mapping login identifier → customer (credentials stay in the customer database);
   - the Licence Registry built by IMS behind a narrow interface;
   - per-process licence snapshot caching (refresh 60 s, change-feed poll 10 s, maximum staleness 15 min), then **fail closed**;
   - customer databases on a shared HA PostgreSQL cluster, each with its own credential;
   - a transactional outbox, webhooks, workers using PostgreSQL-backed queues, and connector microservices.

   The seven HLD sign-off questions became #1–#6 and #23 (API style).
5. **November HLD reviewer decisions [Stakeholder]**, superseding the AI proposals where they differ:
   - **#1:** there is no shared licensing service. IMS builds it behind the narrow interface, **designed as the future shared ZongoVita platform service**, not IMS-specific code.
   - **#2:** the Login Directory is accepted, with directory caching (login must not depend on the Platform Service being up) and constant-time login.
   - **#3:** fail-closed is **replaced**.
     - On expiry: a **grace period**, 14 days by default and configurable per contract, with in-app banners to the super admin; then **read-only**. **Emergency stock issue** stays available with a mandatory reason, full audit and a notification to the super admin.
     - On a Registry outage: a platform fault must never block a customer. Honour the **last known-good snapshot** and page on-call. Unknown or never-licensed customers are refused.
     - Licence state becomes an explicit state machine (**Active, Grace, Read-only, Suspended, Terminated**) owned by the Platform Service and enforced on every request and job.
   - **#4:** design and load-test for **100 customers × 50 concurrent users = 5,000 concurrent**. Business hours are **24x5 across customer time zones**.
   - **#5:** Product proposes the licensable module list; Engineering keeps module tagging on every route and job. The reviewer's next steps also listed the module list under Engineering proposals; this inconsistency was noted but not resolved.
   - **#6:** a shared HA cluster by default, with a **dedicated instance as a paid tier**. Placement is recorded in the Registry and a customer can move without code change. The objective trigger for moving must be defined.
   - **#23:** REST over JSON with OpenAPI and per-customer API credentials **accepted**.
   - **#27:** **RPO 15 min, RTO 4 h**, zone-level disaster recovery, stated in the HLD.
   - **Other decisions:**
     - **GxP mode** configurable per customer.
     - **MFA** for local logins in Phase 1, mandatory for super admins.
     - **SSO** (OIDC/SAML) in Phase 2.
     - **ZongoLake** out of Phase 1, but the event schema must stay stable and complete enough for a later connector.
   - **Required design changes:**
     - a connection pooler per cluster, transaction mode, with a stated connection budget;
     - a work-pending signal instead of polling every customer, with service levels for lock-timeout release and webhook dispatch;
     - login availability;
     - migrations run only from CI/CD under a non-human identity (the migration role had contradicted "no platform access to business data");
     - GxP: 21 CFR Part 11 e-signatures on approvals, quality verdicts and quarantine release; mandatory segregation of duties on verdicts and release; mandatory reason for change; the GxP flag in the Registry, irreversible once GxP data exists; hooks for all customers;
     - a sizing table;
     - the disaster recovery design;
     - schema-skew limits and a stop-the-rollout rule.
   - **Security changes:**
     - constant-time login;
     - MFA;
     - break-glass super-admin recovery with customer authorisation and no platform data access;
     - just-in-time, customer-approved, time-boxed support access;
     - per-customer encryption keys, at least for the dedicated tier and GxP customers, giving crypto-shredding;
     - webhook timestamp, replay protection and secret rotation, plus token signing-key rotation;
     - noisy-neighbour limits;
     - an explicit event-ordering guarantee;
     - Workers marked as a trust boundary.
   - **Corrections requested:**
     - AD-02 was missing and numbering jumped AD-35 → AD-78;
     - open items #7, #29, #32 and #33 were missing and #23 was out of order;
     - the diagram lacked the migration and webhook paths;
     - the Asset Maintenance API should appear as a dated Phase 1 risk;
     - an accepted-risk statement was needed for no offline mode.
   - **Next steps the reviewer asked for:**
     - a revised HLD;
     - Engineering proposals for the module list, the dedicated-tier trigger and the service levels;
     - a load-test plan for 5,000 users across 100 customers, before the LLD starts.
6. **Claude's response [AI].** Claude raised nine points before revising:
   1. The expiry rule contradicts the 25 Oct standard, which says it applies to every product.
   2. Last-known-good needs a durable store for processes that start during an outage.
   3. With a pooler, the work-pending signal must be a control-plane index, not LISTEN.
   4. Transaction pooling needs the driver's prepared-statement cache disabled.
   5. Per-customer keys are not possible on a shared cluster.
   6. GxP validation conflicts with a single shared release train.
   7. Break-glass and support access need narrow platform-side rights.
   8. Two inconsistencies exist within the feedback itself.
   9. The 15-page limit would be exceeded.

   **[User]** replied: "don't bother about any of these … just agree to the changes suggested by the reviewer, that's the final decision." The reviewer's changes were adopted in full. These points were therefore not raised with the reviewer, and point 1 remains a possible conversation for ZongoVita. Where the design needed something the reviewer did not specify, Claude filled it and flagged the values:
   - a signed snapshot bundle in object storage;
   - a control-plane work-pending index with after-commit hints and a 60 s sweep;
   - GxP customers placed on dedicated instances, because per-customer keys require it.

---

## 7. Confirmed technology stack and technical decisions

| Area | Current decision | Origin |
|---|---|---|
| Front end | Next.js | [Stakeholder] 26 Oct (replaced React from Q23) |
| Back end | Python FastAPI only, for every backend service | [Stakeholder] 26 Oct |
| Database | PostgreSQL | [Stakeholder] 26 Oct (replaced the generic relational DB from Q23) |
| Deployment | ZongoVita cloud; standalone containerised services | [Stakeholder] Q19, Q29; PRD FR-19 |
| Tenancy | One database per customer; Licence Registry; customer from login only | [Stakeholder] 25 Oct standard |
| Licence behaviour | State machine with grace and read-only; last known-good on outage | [Stakeholder] November reviewer |
| Licensing service | Built by IMS as the future shared platform service | [Stakeholder] November reviewer |
| Database placement | Shared HA cluster default; dedicated paid tier; objective trigger | [Stakeholder] November reviewer (trigger values are AI proposals) |
| API | REST over JSON with OpenAPI; per-customer API credentials | [Stakeholder] November reviewer |
| Identity | OAuth2-style tokens (Q24); MFA in Phase 1; SSO in Phase 2 | [Stakeholder] Q24 + November reviewer |
| Integrations | Connector microservices; Asset Maintenance first; accounting/POS optional | [Stakeholder] Q25–Q27 |
| Concurrency | First write wins; stock never negative; over-issue blocked | [Stakeholder] Q7, Q20 |
| Audit | Permanent, lifetime, never edited or deleted | [Stakeholder] Q22 |
| Recovery | RPO 15 min, RTO 4 h, zone-level DR | [Stakeholder] November reviewer |
| Scale | 5,000 concurrent users (100 × 50); 99.5% over 24x5 | [Stakeholder] November reviewer |
| GxP | Per-customer mode; Part 11 e-signatures; segregation of duties; reason for change | [Stakeholder] November reviewer |

The November reviewer explicitly asked to **protect** these design decisions through the LLD and build. They began as AI proposals and are now stakeholder-endorsed:

- tenant routing only from the signed token or API credential (AD-21);
- one database and one credential per customer (AD-16, AD-18);
- Inventory Core as the only stock writer, with an immutable ledger, conditional updates and CHECK constraints (AD-30 to AD-33);
- one transaction per command covering change, audit, ledger and outbox, with idempotency keys (AD-08, AD-34, AD-51);
- no platform data credentials (AD-13);
- the decision log with a status per decision.

---

## 8. HLD and LLD design and review history

The design documents themselves deliberately carry **no version numbers or revision history** (see 15 Nov below). The iterations are recorded here only.

- **28 Oct [User].** "Don't start implementing anything." Wireframes to be attached later; ignore the September HLD diagram. The user gave the stack (Next.js / FastAPI / PostgreSQL) as the source of truth if anything conflicts, and asked Claude to act as a senior chief system architect: a complete end-to-end HLD with reasoning for every decision and Mermaid code for the diagram.
- **28 Oct [AI].** Understanding report (sections 5–6) and the first HLD draft (Claude Docs artifact): 18 sections, an AD-nn decision register, open-items register, traceability, drawn diagrams plus Mermaid source.
- **29 Oct [User → AI].** LLD drafted: code structure, PostgreSQL schemas and ER diagrams, state machines, sequence flows, permission engine, workflow engine, API, events, jobs, frontend, tests and a defaults register (LD-nn decisions).
- **29 Oct, review round 1 [AI reviewing ChatGPT].** The user pasted two ChatGPT reviews, one of the HLD and one of the LLD, with the instruction "don't blindly trust anything … analyze everything". Each claim was checked against Revision B and the schema.
  - **HLD, accepted:**
    - one purchase record per item per inward (Revision B), with a follow-on record for short deliveries;
    - a new **awaiting stock** state for requests short of stock (ChatGPT missed that the approval timeout would expire them);
    - the transaction-boundary wording narrowed to state-changing commands;
    - the ledger is authoritative;
    - drawn diagrams for the Word export;
    - decision-register inconsistencies fixed;
    - asset and batch tracking made independent.
  - **HLD, overstated:** licence caching staleness; a propagation-bounds table was added instead.
  - **HLD, not adopted:** closing the taxonomy depth, because only ZongoVita can.
  - **LLD, accepted:**
    - partitioned-table keys must include the partition column (PostgreSQL would reject otherwise);
    - transfer rows per asset;
    - exactly one super admin enforced at commit;
    - **automatic approval must reserve stock** (the most dangerous finding);
    - append-only verdict history;
    - idempotency key written inside the business transaction;
    - an explicit route-to-permission matrix;
    - a connection budget;
    - webhook egress (SSRF) checks;
    - per-customer migration roles;
    - login-directory recovery.
  - **LLD, rejected as wrong:**
    - "missing identifiers on line tables" (they existed);
    - "deployment target not answered" (Q19 was answered: ZongoVita cloud).
  - **Found by Claude independently:** sequence-ordered feeds can skip late-committing rows, so a commit-safe feed cursor was added.
- **29 Oct, review round 2 [AI reviewing ChatGPT].** All findings were valid, but one proposed fix was rejected:
  - **Accepted:**
    - HLD and LLD aligned on stock balances (locks at item × location; on-hand and quarantine at lot × location);
    - application role stripped of DELETE except on a listed exception set;
    - purchase records hold one batch line per supplier batch, each creating a lot;
    - a guarded awaiting-stock fallback;
    - connection budget corrected (about 180, not ChatGPT's 120);
    - licence-module tags;
    - a single currency per customer;
    - asset-vs-quantity reconciliation;
    - proposed performance targets.
  - **Rejected fix:** copying the business transaction ID into an outbox archive would still lose events, because archive rows become visible in dispatcher commit order. Events stay in one partitioned table instead.
- **15 Nov [AI].** A list of 18 questions for Ravi and Kshethra was drafted, covering the seven sign-off items plus key LLD defaults. Whether it was sent is not recorded. Many of its questions were later answered by the November reviewer.
- **15 Nov [User].** Treat the latest HLD and LLD as the only versions. Remove every reference to versions, revisions or version history. All version references were removed.
- **15 Nov [User].** Condense both documents to 10–15 pages each, with strict scope:
  - the HLD covers architecture only and the LLD implementation only;
  - no meetings, coordination, review history, textbook theory or formalities;
  - keep every important technical detail;
  - no invented requirements.

  Removed: the long decision register (statuses kept inline), the traceability tables, the Mermaid source blocks (drawn diagrams kept) and the LLD defaults register (defaults stated where they apply).
- **November [Stakeholder].** HLD reviewer feedback (section 6, item 5).
- **November [User → AI].** The reviewer's changes were adopted as final and the HLD updated. The user then supplied the team's own HLD `.docx` format: a Google Docs export trimmed by the team, with In Scope as a Heading 3 list, no out-of-scope table, no deployment section, and sections 1–12. The user asked for the same format with no extra formatting. The HLD was rebuilt in that format, about 26 pages:
  - an Out of Scope list added back for the ZongoVita and SSO decisions;
  - the licence state machine and schema-rollout rules in section 5;
  - GxP mode inside Security (section 8);
  - DR and sizing in Data management (section 9);
  - pooling, service levels, dedicated-tier trigger and load-test plan in Non-functional design (section 10);
  - Risks plus Open items (section 11), with #1–#37 sorted and marked open or closed;
  - a Decision log (section 13) with AD-01 to AD-85 and their statuses.

  New decisions: AD-78 licence state machine, AD-79 directory caching and Platform Service availability, AD-80 pooler, AD-81 GxP, AD-82 break-glass, AD-83 support access, AD-84 noisy-neighbour controls, AD-85 event ordering. The old awaiting-stock decision was merged into AD-35 and AD-02 was restored.
- **16 Nov [User → AI].** LLD updated in the team's LLD format to match the revised HLD (about 40 pages; new LD-75 to LD-88):
  - licence-state gate with read-only routes;
  - signed snapshot bundle;
  - MFA (TOTP) and constant-time login;
  - pooler compatibility and connection budget;
  - work-pending index and service levels;
  - pipeline-only migrations with canary stages, at most one version of skew and the stop rule;
  - GxP e-signatures via re-authentication, segregation-of-duties triggers and reason for change;
  - support grants and the break-glass function;
  - emergency issue;
  - event subject version;
  - per-customer rate limits and encryption keys.

---

## 9. Requirements register

### 9.1 Confirmed and current

**Stakeholder decisions:**
- The tenancy rules (with expiry handled by the licence state machine).
- The stack.
- All of Revision B's workflows, except the two-level taxonomy and query-layer tenancy.
- The 25 Oct changes: item codes, four subcategory levels, assets per item code, multi-item vendors, a complete supplier register, custom approvals.
- The 15 Sep answers marked current in section 2.
- The November reviewer's decisions (section 6).

**PRD items still in force:**
- the integration architecture (FR-15 to FR-22, NFR-7, NFR-8, NFR-10);
- audit (NFR-5);
- encryption (NFR-3);
- responsive UI (NFR-4);
- daily backups with point-in-time recovery (NFR-6);
- the out-of-scope list;
- the success criteria.

### 9.2 Proposed (AI) decisions in the current design, awaiting sign-off

These have no stakeholder confirmation yet:

- Most AD-nn and all LD-nn decisions marked "Proposed": modular monolith, Platform Service split, PostgreSQL job queues, lot-per-batch model, formula library, workflow gates, partitioning, environments.
- Values the AI filled in after the reviewer's decisions, flagged as assumptions:
  - sizing per customer;
  - dedicated-tier trigger (250 GB, 15% CPU or I/O, pool saturation, 300 users, 14 days);
  - service levels (lock release ≤ 60 s; first webhook attempt ≤ 10 s at p95);
  - connection budget (max_connections 400; at most 75 customers per shared cluster);
  - how Suspended and Terminated behave;
  - break-glass mechanics (two customer-designated recovery approvers; a single-purpose database function);
  - support grants (4 h default, 24 h maximum);
  - MFA via TOTP;
  - snapshot bundle every 5 minutes;
  - per-customer API limit of 6,000 requests/min;
  - emergency issue using the fulfilment permission;
  - GxP customers on dedicated instances.
- Working defaults for open items, such as five taxonomy levels total and customer-wide item-code uniqueness.
- Proposed response-time targets (LD-74).

### 9.3 Superseded

| Earlier | Replaced by | When / by whom |
|---|---|---|
| React front end; generic relational DB; no backend named (Q23) | Next.js, FastAPI, PostgreSQL | 26 Oct [Stakeholder] |
| Fixed roles Admin/Manager/Staff (FR-11) | Numbered user types on an IAM-style engine | Revision B [Stakeholder via mentor] |
| One warehouse first, multi-location within 6 months (PRD) | Multi-location from the start | Q9 [Stakeholder] |
| Accounting/POS integration required (PRD) | Optional | Q27 [Stakeholder] |
| OAuth2/API keys/SSO/SAML all (NFR-9) | OAuth2 (Q24); MFA in Phase 1; SSO in Phase 2 | 15 Sep, then November [Stakeholder] |
| REST or GraphQL (FR-15; Q18 "Yes") | REST + OpenAPI | November [Stakeholder] |
| Two-level taxonomy (Revision B FB-03) | Four subcategory levels | 25 Oct [Stakeholder] |
| Shared deployment, query-layer tenancy (Revision B) | One database per customer + Licence Registry | 25 Oct [Stakeholder] |
| FB-05 as "optional external identifier" (Revision A) | Expiry tracking where applicable | Revision B [Stakeholder via mentor] |
| Scale: PRD's 50 concurrent users (user's 26 Oct choice) | 5,000 concurrent across 100 customers; 24x5 | November [Stakeholder] |
| Expired licence blocks all sites (25 Oct standard, rule 4) | Grace → read-only with emergency issue | November [Stakeholder] (see section 6) |
| Licence fail-closed after 15 min (AI proposal) | Last known-good snapshot; never block a known customer | November [Stakeholder] |
| Platform Service ran migrations with migration roles (AI proposal) | CI/CD pipeline only, non-human identity | November [Stakeholder] |
| Per-process connection pools without a pooler (AI proposal) | Pooler per cluster, transaction mode | November [Stakeholder] |
| Round-robin worker polling (AI proposal) | Work-pending index with service levels | November [Stakeholder] |
| September HLD and its Mermaid diagram; 13 Oct diagram changes (AI) | Current HLD | 28 Oct [User] |
| Two-month plan ending 2nd week of November (AI plan) | No current timeline; development gated on sign-off | Not formally replaced |

### 9.4 Unresolved

Open items as numbered in the HLD (section 11 there). Current defaults are noted in brackets.

- **#5** licensable module list (Product).
- **#8** custom workflow options: levels, conditions, escalation, delegation.
- **#9** segregation of duties for non-GxP customers.
- **#10** super admin: one person or a user type [one person].
- **#11** taxonomy depth (four levels total, or four beneath a root) and leaf-only assignment.
- **#12** item-code uniqueness scope. Q6 said "unique to location only"; the AI default is customer-wide. This conflict needs a ZongoVita answer.
- **#13** which items are asset-tracked; whether IMS or Asset Maintenance is the master record for assets.
- **#14** what is missing from the supplier quality register.
- **#15** purchase-record granularity and partial deliveries.
- **#16** fate of reworked items.
- **#17** reclassifying a wrong-specification item.
- **#18** vendor, MOQ and usage-window rules.
- **#19** transfer stages; in-transit stock.
- **#20** valuation method, cost vs price, currency.
- **#21** alert channels (Q12 never answered) [in-app].
- **#22** lock timeout; partial fulfilment.
- **#24** Phase 1 integrations; Asset Maintenance API not yet received (dated Phase 1 risk).
- **#26** password, session and key-management detail (MFA and SSO decided).
- **#28** data after permanent termination.
- **#30** behaviour at licence limits.
- **#31** object-storage availability; semantic duplicate matching.
- **#32** attribute governance.
- **#33** Phase 1 feature boundary and timeline (Q28 never answered as a list).
- **#34** scanner hardware.
- **#35** allocation among requests awaiting stock; maximum wait.
- **#36** expired lots at issue.
- **#37** bin-level locations.

**Project-level unknowns:**
- The delivery timeline after the lapsed November date.
- Wireframe sign-off status.
- Whether ZongoVita's multi-tenant standard (which says it applies to every product) is updated for the new grace/read-only expiry behaviour.
- Test data, repository, environments and credentials (promised in Q31–Q32, not yet received).
- Whether the 15 Nov question list was sent.
- Whether the revised HLD has been returned to the reviewer.

---

## 10. The user's expectations for development and for working with the AI

**Development and process:**
- Do not start implementing anything until the design is signed off; development is a separate, later phase.
- Use exactly the confirmed stack. The user's stack statement overrides any conflicting document.
- Treat the HLD and LLD the user provides as the authority. Do not redesign; raise conflicts instead.
- Stakeholder (ZongoVita) decisions are final once given. On 15 Nov the user directed that the November reviewer's changes be adopted as-is, even where the AI had reservations.
- The product is enterprise-grade and multi-tenant, serving many organisations and users, so plan carefully.
- Wireframes are handled separately; do not work on them unless asked.

**Working style with the AI:**
- Act as a senior system architect. Give the reasoning behind each architectural decision.
- **Never blindly trust other AI output** (ChatGPT reviews). Verify every claim against the sources and say plainly what is valid, overstated or wrong.
- Distinguish stakeholder decisions from AI suggestions. Do not invent or assume requirements; label assumptions and defaults explicitly; ask when something is genuinely ambiguous.
- Do not treat outdated decisions as current.
- Concise answers ("don't yapp"), no emojis. Full detail only where it is genuinely needed.
- When teaching: first principles, in the context of this IMS, with real-life analogies. Answer follow-up questions narrowly, then return to the original thread.
- **Documents:** professional and concise. Strict HLD vs LLD scope. No version numbers or revision history inside the documents. When the user supplies a document format, follow it exactly, with no extra formatting.

---

## 11. Sources, and history that could not be accessed

**Used:**
- The PRD PDF.
- The clarification PDF, including its comment annotations.
- The Revision B PDF.
- `multiTenant.png`.
- The exported ChatGPT conversation (`2026-09-09_ZongoVita_Project_context.md`, 9 Sep – 26 Oct, 54 messages, including the 26 Oct meeting transcript).
- The transcript of this conversation's 28–29 Oct sessions.
- The November exchanges in this conversation: the question list, the version-removal and condensation instructions, the reviewer feedback and the format-matched documents.
- The uploaded team-format HLD and LLD `.docx` files.

**Not accessible or not available:**
- The 25 Oct stakeholder comment images. Only a paraphrase survives, so the exact wording of the six changes is unverified.
- The 13 Oct and 26 Oct images. The 26 Oct image is assumed to be the same diagram as `multiTenant.png`, but this is unconfirmed.
- Revision A of the review response.
- All wireframe ZIPs (25 Sep, 15 Oct).
- The clarification `.docx` and the execution-plan `.docx` as files (their content survives only in the ChatGPT export).
- Any recording or transcript of the review meeting; only Revision B's account of it.
- The exact date of the review meeting.
- The full text of the ChatGPT review conversations pasted on 29 Oct. They were attachments; only Claude's verdicts on them survive.
- The name of the November HLD reviewer and the date of that feedback.
- Whether any deliverable since 26 Oct has been formally submitted or signed off.
- The Asset Maintenance API documentation and test data (not yet shared by ZongoVita).
