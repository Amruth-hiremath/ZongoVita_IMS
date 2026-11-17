import "server-only";

import { reportsPage } from "@/fixtures/reports";

import { fromFixture } from "./source";

/** Pill tone of a report's state, as drawn (green good, amber soon, red problem, dark terminal, blue ready). */
export type ReportStateTone = "green" | "amber" | "red" | "dark" | "blue";

export interface ReportState {
  tone: ReportStateTone;
  label: string;
}

export interface ReportCatalogRow {
  report_id: string;
  name: string;
  covers: string;
  /** As drawn: "today 07:40", "26 Sep". */
  last_run_label: string;
  schedule: string;
  state: ReportState;
}

export interface ReportOutputRow {
  output_id: string;
  report: string;
  generated_label: string;
  generated_by: string;
  format: string;
  sent_to: string;
  state: ReportState;
}

export interface SupplierRollupRow {
  vendor: string;
  /** Poor (FAIL) verdicts this month. */
  poor_count: number;
  /** Poor rate in percent, decimal string. */
  poor_rate: string;
  /** True when the rate breaches the threshold (drawn red). */
  breach: boolean;
  last_event: string | null;
}

export interface ReportsPage {
  kpis: {
    runs: { month_label: string; total: number; scheduled: number; ad_hoc: number };
    approval_turnaround: { hours: string; decisions: number; target_hours: string };
    expiry: { batches: number; inside_30_days: number };
    supplier_claims: { amount: string; case_ref: string };
  };
  catalog: ReportCatalogRow[];
  /** Quality alert shown above Recent outputs, if any. */
  alert: string | null;
  outputs: ReportOutputRow[];
  preview: {
    title: string;
    period: string;
    scope: string;
    fail_lines: string;
    month_label: string;
    suppliers: SupplierRollupRow[];
  };
  scheduled_deliveries: string[];
}

/** F44 Reports — Catalog & Deliveries (manager workspace). */
export function getReportsPage(): Promise<ReportsPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/reports",
      note: "Needs the report catalogue scoped to the caller's user type and site (FB-23) with last run, schedule and a state summary per report; recent outputs with format, recipients and delivery state; scheduled deliveries; the month's run counts and KPI tiles; and the vendor quality roll-up preview (also served by GET /ui/v1/supplier-quality).",
    },
    reportsPage,
  );
}
