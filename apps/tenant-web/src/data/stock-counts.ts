import "server-only";

import { countSessions, featuredCountNo, varianceReviews } from "@/fixtures/stock-counts";

import { fromFixture } from "./source";

export interface CountSheetLine {
  item_code: string;
  name: string;
  bin: string;
  uom: string;
  /** Withheld (null) while the session is a blind count. */
  system_qty: string | null;
  /** Physical quantity entered so far; null when not yet counted. */
  counted_qty: string | null;
  status: { kind: "pending" | "counted"; label: string };
}

export interface CountSession {
  count_no: string;
  count_types: string[];
  count_type: string;
  locations: { id: string; label: string }[];
  location_id: string;
  /** "Aisle B · Spares". */
  scope: string;
  blind: boolean;
  counted_lines: number;
  total_lines: number;
  lines: CountSheetLine[];
  /** Order the sheet is shown in ("uncounted first"). */
  filter_label: string;
  pages: (number | "…")[];
  page: number;
}

/** F16 Stock Count sheet. Null when the count session does not exist. */
export function getCountSession(countNo: string): Promise<CountSession | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/count-sessions/{id}/lines",
      note: "Needs the session header (type, location, scope, blind flag, counted / total) with the lines; system quantity must be withheld for blind counts; cursor pagination with an uncounted-first order.",
    },
    countSessions[countNo] ?? null,
  );
}

/**
 * The session the store's Counts entry opens on. The wireframes draw no list of count sessions,
 * only the open sheet for CC-0057.
 */
export function getActiveCountSession(): Promise<CountSession | null> {
  return getCountSession(featuredCountNo);
}

export interface VarianceLine {
  item_code: string;
  name: string;
  bin: string;
  system_qty: string;
  counted_qty: string;
  /** Signed decimal string, counted minus system. */
  variance: string;
  /** Signed decimal string in the customer's currency. */
  impact: string;
  reason: string | null;
  decision: { kind: "approval_required" | "match"; label: string };
}

export interface AdjustmentPreview {
  item_code: string;
  location_code: string;
  from_qty: string;
  to_qty: string;
  uom: string;
  /** "movement record: count adjustment, ref CC-0057". */
  movement_note: string;
}

export interface VariancePolicyRule {
  id: string;
  label: string;
  enabled: boolean;
}

export interface VarianceReview {
  count_no: string;
  sku_count: number;
  /** Signed decimal string in the customer's currency. */
  net_impact: string;
  lines: VarianceLine[];
  adjustments: AdjustmentPreview[];
  policy: { rules: VariancePolicyRule[]; approvers: string[] };
}

/** F17 Variance Review. Null when the count session does not exist. */
export function getVarianceReview(countNo: string): Promise<VarianceReview | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/count-sessions/{id}/lines",
      note: "Variance view of a submitted session: system and counted quantity, variance and value impact per line, the reason entered, the adjustment each approval would post, and the adjustment approval policy from GET /ui/v1/approval-policies (Q3).",
    },
    varianceReviews[countNo] ?? null,
  );
}

/** The submitted count the manager's Stock Counts entry opens on (no list frame exists). */
export function getPendingVarianceReview(): Promise<VarianceReview | null> {
  return getVarianceReview(featuredCountNo);
}
