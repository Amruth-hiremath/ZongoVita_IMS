import "server-only";

import { adminAuditPage, managerAuditPage, storeAuditPage } from "@/fixtures/audit";

import { fromFixture } from "./source";

/** Where an action came from (FR-15/16, Q26): external systems are traced like people. */
export type AuditSource = "Web" | "Mobile" | "API" | "Connector";

/**
 * What changed, as the Change column draws it: a quantity move ("52 → 48 pcs") or an outcome
 * word. `good` is green ("approved"), `bad` is red ("first-write-wins"), `plain` is gray.
 */
export type AuditChange =
  | { kind: "quantity"; from: string; to: string; uom: string }
  | { kind: "outcome"; tone: "good" | "bad" | "plain"; text: string };

export interface AuditEntry {
  id: string;
  /** ISO 8601 UTC. */
  occurred_at: string;
  /** As the frame prints it, in the site's time zone: "26 Sep 09:42:07". */
  occurred_at_label: string;
  actor_name: string;
  /** Short qualifier after the name: "S", "M", "T2", "connector", "quality". */
  actor_tag: string;
  /** Seeded user type of the actor ("Type 2"), or "System" for connectors and rules. */
  actor_user_type: string;
  action: string;
  /** Functional area, for the Module filter. */
  module: string;
  entity: string;
  change: AuditChange;
  source: AuditSource;
  location_code: string;
}

export interface AuditTrailPage {
  rows: AuditEntry[];
  total: number;
  sorted_by: string;
  pages: (number | "…")[];
  page: number;
  /** Start of the date window, as the range control shows it. */
  from_label: string;
  filters: { users: string[]; user_types: string[]; modules: string[]; locations: string[]; sources: AuditSource[] };
}

/** Action kinds of the store audit (F50): the segmented control and chips filter by these. */
export type StoreActionKind = "issue" | "receipt" | "count" | "transfer" | "approval" | "quality" | "quarantine";

export interface StoreAuditEntry extends AuditEntry {
  action_kind: StoreActionKind;
}

export interface StoreAuditPage {
  site_code: string;
  rows: StoreAuditEntry[];
  /** Months the trail can be viewed by; value is "YYYY-MM". */
  months: { value: string; label: string }[];
  /** Period the rows cover, as the footer states it. */
  period_label: string;
}

const AUDIT_NOTE =
  "Rows need actor name, user type and a short qualifier, the action, module, entity reference, a structured change (quantity before/after with UoM, or an outcome) and the source channel; user, user type, module, location, source and date range become query parameters with cursor pagination.";

/** F24 Audit Trail, tenant-wide (admin workspace). */
export function getAdminAuditTrail(): Promise<AuditTrailPage> {
  return fromFixture({ endpoint: "GET /ui/v1/audit", note: AUDIT_NOTE }, adminAuditPage);
}

/** F24 Audit Trail as drawn for User Type 2 (manager workspace). */
export function getManagerAuditTrail(): Promise<AuditTrailPage> {
  return fromFixture({ endpoint: "GET /ui/v1/audit", note: AUDIT_NOTE }, managerAuditPage);
}

/** F50 Audit Trail for the store's own site (store workspace). */
export function getStoreAuditTrail(): Promise<StoreAuditPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/audit",
      note: `${AUDIT_NOTE} The store view is limited to the user's granted site (FB-23) and also needs an action kind per row (issue, receipt, count, transfer, approval, quality, quarantine) and a month filter.`,
    },
    storeAuditPage,
  );
}
