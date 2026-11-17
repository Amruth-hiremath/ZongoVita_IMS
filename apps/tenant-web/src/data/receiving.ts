import "server-only";

import { grnDraft, inwardPipeline } from "@/fixtures/receiving";

import { fromFixture } from "./source";

/** Tone of a small pill under a KPI value, as drawn. */
export type BadgeTone = "green" | "amber" | "red" | "blue" | "violet";

export interface Kpi {
  label: string;
  value: string;
  hint?: string;
  badge?: { label: string; tone: BadgeTone };
}

// ---------------------------------------------------------------------------- F42 (manager)

export type PipelineStatus = "awaiting_grn" | "in_transit" | "exception";

export interface PipelineRow {
  po_number: string;
  vendor_name: string;
  /** Item and ordered quantity as one line ("Seal kit 40 mm ×6"). */
  items_summary: string;
  /** Display string as drawn: "due 05 Oct" before inward, the inward date after. */
  inward_due: string;
  /** ISO 8601 date the material is needed. */
  expected_use_date: string;
  /** Null until the GRN has been inspected. */
  inspection: string | null;
  status: { kind: PipelineStatus; label: string };
}

export type GrnState = "posted" | "held";

export interface RecentGrn {
  grn_number: string;
  /** Display string as drawn ("26 Sep"). */
  posted: string;
  received_by: string;
  /** "4 lines", "100 pairs", "8 drums". */
  lines_summary: string;
  /** Decimal string in the customer's currency. */
  value: string;
  po_number: string;
  inspection: string;
  state: { kind: GrnState; label: string };
}

export interface InspectionReview {
  po_number: string;
  facts: { label: string; value: string }[];
  findings: string;
  store_note: string;
  /** Labels of the two decisions offered. */
  accept_label: string;
  raise_label: string;
  raise_hint: string;
}

export interface InwardPipeline {
  kpis: Kpi[];
  pipeline: PipelineRow[];
  pipeline_notice: string;
  recent_grns: RecentGrn[];
  /** Reviews the screen can show, keyed by PO number. */
  reviews: InspectionReview[];
  /** PO whose review opens first. */
  review_po: string;
  closing_rules: string[];
  footnote: string;
}

/** F42 Receiving — Inward Pipeline. */
export function getInwardPipeline(): Promise<InwardPipeline> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/purchase-records",
      note: "Needs purchase records awaiting inward with inspection outcome, plus a GRN list (no GET /ui/v1/grns in the LLD route table), the KPI counts and the inspection review of an exception PO (findings and the store's note).",
    },
    inwardPipeline,
  );
}

// ------------------------------------------------------------------------------ F10 (store)

export interface GrnLine {
  line_id: string;
  item_code: string;
  item_name: string;
  qty: string;
  uom: string;
  /** Empty when the item is not lot-tracked or no lot was entered yet. */
  lot_number: string;
  /** Display string as entered ("10 Nov 26"); empty when none. */
  expiry: string;
  /** Unit cost, decimal string. */
  unit_cost: string;
  line_total: string;
}

export interface GrnDraft {
  grn_number: string;
  /** ISO 8601 date. */
  receipt_date: string;
  site: { code: string; name: string };
  site_options: { code: string; name: string }[];
  vendor: { code: string; short_name: string };
  vendor_options: { code: string; short_name: string }[];
  purchase_record: { po_number: string; reference: string };
  purchase_record_options: { po_number: string; reference: string }[];
  lines: GrnLine[];
  total_value: string;
  notice: string;
  linked_record: { title: string; facts: { label: string; value: string }[] };
  footnote: string;
}

/** F10 Receive Stock — the GRN being entered. */
export function getGrnDraft(): Promise<GrnDraft> {
  return fromFixture(
    {
      endpoint: "POST /ui/v1/grns",
      note: "Reading a draft GRN has no route in the LLD table (GET /ui/v1/grns/{id} is assumed); site, vendor and PO options come from GET /ui/v1/sites, /vendors and /purchase-records; the linked purchase record panel needs purchaser, approver and expected use.",
    },
    grnDraft,
  );
}
