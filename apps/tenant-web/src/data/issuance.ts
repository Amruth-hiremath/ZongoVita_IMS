import "server-only";

import { lockLedger, locksOverview } from "@/fixtures/issuance";

import { fromFixture } from "./source";

/** State of a stock row on the locks view. */
export type StockLockStateKind = "locked_awaiting_pick" | "quarantined_validation_pending" | "lock_released_on_issue";

export interface LockedStockRow {
  item_code: string;
  name: string;
  location_code: string;
  on_hand: string;
  locked: string;
  quarantined: string;
  free: string;
  /** The issue request or return that holds or last held the units. */
  lock_ref: string;
  state: { kind: StockLockStateKind; label: string };
}

export interface LocksOverview {
  active_locks: number;
  awaiting_pick: number;
  released_today: number;
  units_locked: string;
  /** Split by unit of measure, e.g. [{ qty: "6", uom: "pcs" }, { qty: "24", uom: "pairs" }]. */
  units_locked_by_uom: { qty: string; uom: string }[];
  /** Lock auto-release timeout in hours; a customer setting (kernel/tenant_settings.py). */
  lock_timeout_hours: number;
  over_issue_attempts: number;
  rows: LockedStockRow[];
}

export type LockLedgerStateKind = "awaiting_pick" | "released";

export interface LockLedgerRow {
  request_ref: string;
  item_code: string;
  location_code: string;
  qty: string;
  uom: string;
  /** Display string from the frame ("26 Sep 10:12"). */
  locked_at_label: string;
  locked_by: string;
  state: { kind: LockLedgerStateKind; label: string };
}

export interface LockLedger {
  rows: LockLedgerRow[];
  lifecycle: { created_by: string; created_at_label: string };
}

/** F28 Locks & Reservations: KPI tiles and stock by item and location. */
export function getLocksOverview(): Promise<LocksOverview> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/stock",
      note: "Rows need locked and quarantined split out of on hand, free, and the reference holding the lock (issue request or return) with its state; the tiles need counts of active locks, units locked by UoM, over-issue attempts blocked at scan (Q7) and the lock timeout setting (GET /ui/v1/settings).",
    },
    locksOverview,
  );
}

/** F28 Active lock ledger. */
export function getLockLedger(): Promise<LockLedger> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/issue-requests",
      note: "The LLD has no list of locks; this needs approved requests with their lock (item, location, quantity, locked at, by whom, state), including locks released today.",
    },
    lockLedger,
  );
}
