import "server-only";

import { approvalWorkspace } from "@/fixtures/approvals";

import { fromFixture } from "./source";

/** Where an issue request stands, as the approval queue shows it in the State column. */
export type ApprovalStateKind = "pending_approval" | "approved_locked" | "issued_awaiting_ack" | "rejected_lock_released";

export interface ApprovalQueueRow {
  /** Approval task id, used by POST /ui/v1/approval-tasks/{id}/approve and /reject. */
  task_id: string;
  request_ref: string;
  requester: string;
  purpose: string;
  /** "2 lines · 6 pcs + 2 m", as the queue prints it. */
  lines_summary: string;
  state: { kind: ApprovalStateKind; label: string };
}

export interface LiveFree {
  /** Short location code as the frame prints it ("BLR-01"). */
  location_code: string;
  free: string;
}

/** A request line whose stock exists: approving locks it at the request's site. */
export interface ApprovalLineInStock {
  kind: "in_stock";
  item_code: string;
  name: string;
  qty: string;
  uom: string;
  live_free: LiveFree[];
  lock_location_code: string;
  free_after_lock: string;
}

/** A request line with no free stock anywhere: on approval it leaves IMS as an external purchase request (FB-10). */
export interface ApprovalLineOutOfStock {
  kind: "out_of_stock";
  item_code: string;
  name: string;
  qty: string;
  uom: string;
  free_total: string;
  location_count: number;
  external_request_ref: string;
}

export type ApprovalLine = ApprovalLineInStock | ApprovalLineOutOfStock;

export interface LockImpactPreview {
  qty: string;
  uom: string;
  location_code: string;
  free_before: string;
  free_after: string;
  other_pending: string;
}

export interface ApprovalDetail {
  request_ref: string;
  requester: string;
  department: string;
  purpose: string;
  site_label: string;
  /** ISO 8601 date. */
  needed_by: string;
  /** Display string from the frame ("26 Sep 09:58 · 22 m ago"). */
  raised_label: string;
  lines: ApprovalLine[];
  lock_preview: LockImpactPreview;
}

/** The worked example in the "Lock semantics" panel (FB-09). */
export interface LockExample {
  request_ref: string;
  qty: string;
  uom: string;
  item_code: string;
  approver: string;
  approved_at_label: string;
  location_code: string;
  free_before: string;
  free_after: string;
}

export interface ApprovalWorkspaceData {
  queue: ApprovalQueueRow[];
  /** Detail per request ref; only the requests the sample data covers. */
  details: Record<string, ApprovalDetail>;
  /** Display string, e.g. "3 h 20 m". */
  median_wait: string;
  lock_example: LockExample;
}

/** F27 Approval Workspace. */
export function getApprovalWorkspace(): Promise<ApprovalWorkspaceData> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/approval-tasks",
      note: "Tasks scoped to the approver's sites, with the request's lines, live free stock per location for each line, the lock that approval would create (free before/after, other pending requests for the SKU), out-of-stock lines' external purchase-request reference, and the queue's median wait.",
    },
    approvalWorkspace,
  );
}
