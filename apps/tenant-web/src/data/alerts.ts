import "server-only";

import { alertsPage } from "@/fixtures/alerts";

import { fromFixture } from "./source";

export interface AlertChannel {
  id: string;
  label: string;
  enabled: boolean;
}

export type AlertStatusKind = "below_min" | "batch_expiring" | "expiry_window" | "above_min";

export interface AlertRow {
  item_code: string;
  name: string;
  location_code: string;
  on_hand: string;
  min_qty: string;
  /** Internal PO time and vendor supply time, in days (FB-18). */
  lead_po_days: number;
  lead_vendor_days: number;
  /** Null when no reorder is suggested. */
  suggested_qty: string | null;
  /** Unit as the suggestion reads ("pcs", "pairs", "drums"). */
  suggested_uom: string;
  status: { kind: AlertStatusKind; label: string };
}

export interface AlertsPage {
  open_count: number;
  channels: AlertChannel[];
  rows: AlertRow[];
  total: number;
  sorted_by: string;
  pages: (number | "…")[];
  page: number;
  /** Worked example of the per-SKU formula for the first suggestion (Q11 · FB-18). */
  formula_example: {
    item_code: string;
    location_short: string;
    expression: string;
    result: string;
    uom: string;
    lead_sources: string;
  };
  /** Dead-stock example with its per-SKU threshold (Q17). */
  dead_stock_example: { item_code: string; idle_days: number; threshold_days: number };
  /** Example webhook body for low.stock.alert (FR-16). */
  webhook_example: string;
}

/** F18 Alerts & Reorder Suggestions. */
export function getAlertsPage(): Promise<AlertsPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/alerts",
      note: "Rows join open alerts with GET /ui/v1/reorder-suggestions (suggested qty, lead PO + vendor days); channel switches come from GET /ui/v1/settings; the formula and dead-stock explainers need GET /ui/v1/formulas and the per-SKU dead-stock threshold, which no endpoint returns yet.",
    },
    alertsPage,
  );
}
