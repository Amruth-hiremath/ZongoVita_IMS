import "server-only";

import { quarantineQueue } from "@/fixtures/quarantine";

import { fromFixture } from "./source";

export interface Kpi {
  label: string;
  value: string;
  hint?: string;
  badge?: { label: string; tone: "green" | "amber" | "red" | "blue" };
}

export type QuarantineState = "due_today" | "overdue" | "spec_check";

export interface QuarantineRow {
  quarantine_ref: string;
  item_name: string;
  /** Quantity with its unit, as drawn ("6 pairs"). */
  qty_display: string;
  reason: string;
  /** Display string as drawn ("26 Sep 11:20"). */
  since: string;
  vendor_po: string;
  state: { kind: QuarantineState; label: string };
}

export interface ValidationCheck {
  id: "identity" | "specification" | "condition" | "evidence" | "vendor";
  label: string;
  /** What the store observed for this check. */
  detail: string;
  checked: boolean;
}

export interface ValidationChecklist {
  quarantine_ref: string;
  title: string;
  checks: ValidationCheck[];
  footnote: string;
}

export interface VerdictPath {
  tone: "green" | "red";
  label: string;
  body: string;
}

export interface QuarantineQueue {
  kpis: Kpi[];
  rows: QuarantineRow[];
  /** Checklists the screen can show, keyed by quarantine_ref. */
  checklists: ValidationChecklist[];
  selected_ref: string;
  verdict_paths: VerdictPath[];
  paths_footnote: string;
}

/** F32 Quarantine Validation Queue. */
export function getQuarantineQueue(): Promise<QuarantineQueue> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/quarantine-queue",
      note: "Needs the held lines with reason, hold start, vendor and PO attribution, the KPI counts (units held, awaiting validation, average hold time against the validation window, released today) and each line's validation checklist as last saved through /ui/v1/returns/{id}/validation.",
    },
    quarantineQueue,
  );
}
