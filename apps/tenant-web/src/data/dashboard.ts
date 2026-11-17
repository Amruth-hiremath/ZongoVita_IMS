import "server-only";

import {
  adminApprovalQueue,
  adminIntegration,
  adminRecentAudit,
  adminSummary,
  adminSystemHealth,
  managerNeedsAttention,
  managerRecentMovements,
  managerReorderSuggestions,
  managerSummary,
  managerWaitingOnYou,
  storeCountInProgress,
  storeFulfilmentQueue,
  storeInbound,
  storeQuarantineAging,
  storeSummary,
  storeTodayActions,
} from "@/fixtures/dashboard";

import { fromFixture } from "./source";

/** One entry in a recent-activity list: what happened, then who, when and where. */
export interface ActivityEntry {
  title: string;
  /** Display line as the feed shows it ("Suresh Patil · 09:42 · via Web"). */
  meta: string;
}

// ------------------------------------------------------------------------- F04 (admin, Type 1)

export interface AdminSummary {
  locations: { total: number; live: number; staged: number };
  items: { total: number; category_count: number };
  active_users: { total: number; by_user_type: { user_type_no: 1 | 2 | 3 | 4; count: number }[] };
  pending_approvals: { total: number; request_count: number };
  /** Decimal string, customer currency, across all locations. */
  stock_value: string;
}

export interface SystemHealthRow {
  label: string;
  /** Display value with its NFR reference, as drawn. */
  value: string;
}

export interface SystemHealth {
  state: "healthy" | "degraded";
  rows: SystemHealthRow[];
}

export interface IntegrationStatus {
  name: string;
  connected: boolean;
  api_version: string;
  /** Display time of the last sync, e.g. "09:42". */
  last_sync: string;
  events_today: number;
  failures_today: number;
  failure_handling: string;
  free_connector_slots: number;
  connector_kinds: string[];
}

export type ApprovalTaskKind = "issuance_request" | "transfer" | "taxonomy_proposal";

export interface ApprovalQueueRow {
  ref: string;
  kind: ApprovalTaskKind;
  activity: string;
  location: string;
  raised_by: string;
  waiting_on: string;
}

export interface AdminDashboard {
  summary: AdminSummary;
  health: SystemHealth;
  integration: IntegrationStatus;
  approvals: ApprovalQueueRow[];
  audit: ActivityEntry[];
}

/** F04 Dashboard — Type 1. */
export async function getAdminDashboard(): Promise<AdminDashboard> {
  const [summary, health, integration, approvals, audit] = await Promise.all([
    fromFixture(
      {
        endpoint: "GET /ui/v1/reports",
        note: "No dashboard summary resource in the UI API. Needs: site count with live/staged split (GET /ui/v1/sites), item and category counts, active users by user type, pending approval tasks and requests, stock value across all locations.",
      },
      adminSummary,
    ),
    fromFixture(
      {
        endpoint: "GET /ui/v1/reports",
        note: "System health (uptime this month vs NFR-1, concurrent users vs NFR-2, last backup / PITR per NFR-6) has no UI API resource; it comes from platform monitoring.",
      },
      adminSystemHealth,
    ),
    fromFixture(
      {
        endpoint: "GET /ui/v1/connectors",
        note: "Connector state, API version, last sync and today's event and failure counts (GET /ui/v1/sync-logs); free connector slots from the licence.",
      },
      adminIntegration,
    ),
    fromFixture({ endpoint: "GET /ui/v1/approval-tasks", note: "Open tasks across all sites with the user type the task waits on." }, adminApprovalQueue),
    fromFixture({ endpoint: "GET /ui/v1/audit", note: "Latest four entries, newest first." }, adminRecentAudit),
  ]);
  return { summary, health, integration, approvals, audit };
}

// ----------------------------------------------------------------------- F05 (manager, Type 2)

export interface ManagerSummary {
  /** Display date line, e.g. "Wednesday 26 Sep". */
  date_label: string;
  scope_site_code: string;
  stock_value: string;
  item_count: number;
  location_count: number;
  low_stock_alerts: number;
  critical_alerts: number;
  requests_to_approve: number;
  units_locked: string;
  live_locks: number;
  dead_stock_value: string;
}

export type AttentionKind = "below_min" | "batch_expiring" | "expiry_window" | "dead";

export interface AttentionRow {
  item_code: string;
  name: string;
  location: string;
  on_hand: string;
  /** Null when the item has no minimum at this location. */
  min: string | null;
  status: { kind: AttentionKind; label: string };
}

export interface WaitingTask {
  task_id: string;
  ref: string;
  requester: string;
  kind_label: string;
  lines_summary: string;
  state_label: string;
}

export interface ReorderSuggestionRow {
  item_code: string;
  name: string;
  location: string;
  on_hand: string;
  min: string;
  lead_po_days: number;
  lead_vendor_days: number;
  suggested_qty: string;
  uom: string;
}

export interface ManagerDashboard {
  summary: ManagerSummary;
  attention: AttentionRow[];
  waiting: WaitingTask[];
  reorder: ReorderSuggestionRow[];
  movements: ActivityEntry[];
}

/** F05 Inventory Overview. */
export async function getManagerDashboard(): Promise<ManagerDashboard> {
  const [summary, attention, waiting, reorder, movements] = await Promise.all([
    fromFixture(
      {
        endpoint: "GET /ui/v1/stock",
        note: "No dashboard summary resource. Needs stock value, item and location counts, low-stock alert count with critical count (GET /ui/v1/alerts), requests to approve, locked units and live locks, dead-stock value.",
      },
      managerSummary,
    ),
    fromFixture({ endpoint: "GET /ui/v1/alerts", note: "Open stock alerts with on hand and minimum per item and location." }, managerNeedsAttention),
    fromFixture({ endpoint: "GET /ui/v1/approval-tasks", note: "Tasks assigned to the caller, with a one-line summary of the requested lines and free stock." }, managerWaitingOnYou),
    fromFixture({ endpoint: "GET /ui/v1/reorder-suggestions", note: "Top four by urgency; lead time split into internal PO days and vendor days." }, managerReorderSuggestions),
    fromFixture({ endpoint: "GET /ui/v1/ledger", note: "Latest movements and lock events in scope, newest first." }, managerRecentMovements),
  ]);
  return { summary, attention, waiting, reorder, movements };
}

// -------------------------------------------------------------------------- F48 (store, Type 3)

export interface StoreSummary {
  date_label: string;
  site_code: string;
  queue_count: number;
  /** Display SLA of the earliest queued request, e.g. "17:00 today". */
  queue_sla: string;
  inbound_due: { po_number: string; due: string }[];
  quarantine_open_lines: number;
  quarantine_overdue: number;
  counts_in_progress: number;
  count_blind: boolean;
  /** The request "Start picking" opens. */
  next_pick_ref: string;
}

export type QueueState = "ready_to_pick" | "picking";

export interface FulfilmentQueueRow {
  ref: string;
  requester: string;
  site: string;
  lines: string;
  locked_ago: string;
  sla: string;
  state: { kind: QueueState; label: string };
}

export type InboundState = "in_transit" | "awaiting_grn" | "posted";

export interface InboundRow {
  ref: string;
  vendor_or_posted: string;
  items_value: string;
  when: string;
  state: { kind: InboundState; label: string };
}

export type QuarantineAgingKind = "overdue" | "due_today" | "spec_check";

export interface QuarantineAgingRow {
  ref: string;
  summary: string;
  status: { kind: QuarantineAgingKind; label: string };
}

export interface CountInProgress {
  count_no: string;
  summary: string;
}

export interface StoreDashboard {
  summary: StoreSummary;
  queue: FulfilmentQueueRow[];
  inbound: InboundRow[];
  actions: ActivityEntry[];
  quarantine: QuarantineAgingRow[];
  count: CountInProgress | null;
}

/** F48 Store dashboard ("Namaste, Suresh"). */
export async function getStoreDashboard(): Promise<StoreDashboard> {
  const [summary, queue, inbound, actions, quarantine, count] = await Promise.all([
    fromFixture(
      {
        endpoint: "GET /ui/v1/fulfilment-queue",
        note: "No dashboard summary resource. Needs queue size with earliest SLA, POs due (GET /ui/v1/purchase-records), open and overdue quarantine lines, counts in progress and whether they are blind.",
      },
      storeSummary,
    ),
    fromFixture({ endpoint: "GET /ui/v1/fulfilment-queue", note: "Approved and locked requests at the caller's site." }, storeFulfilmentQueue),
    fromFixture(
      { endpoint: "GET /ui/v1/purchase-records", note: "Expected POs for the site plus today's posted GRNs in one list." },
      storeInbound,
    ),
    fromFixture({ endpoint: "GET /ui/v1/audit", note: "Today's entries by the caller and on the caller's requests, newest first." }, storeTodayActions),
    fromFixture({ endpoint: "GET /ui/v1/quarantine-queue", note: "Open validations with their ageing state." }, storeQuarantineAging),
    fromFixture({ endpoint: "GET /ui/v1/count-sessions", note: "The caller's count session in progress, if any." }, storeCountInProgress),
  ]);
  return { summary, queue, inbound, actions, quarantine, count };
}
