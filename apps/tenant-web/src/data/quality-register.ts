import "server-only";

import { supplierQualityRegister } from "@/fixtures/quality-register";

import { fromFixture } from "./source";

export type QualityPeriod = "month" | "quarter" | "year";
export type SupplierReviewStatus = "active" | "under_review" | "retired";
export type FeedbackEventStatus = "published" | "acknowledged";
export type CorrectiveActionStatus = "open" | "closed";

export interface SupplierQualityRow {
  vendor_code: string;
  supplier: string;
  city: string;
  pos_received: number;
  /** Poor-quality items attributed to the supplier per period (FB-16). */
  poor: Record<QualityPeriod, number>;
  /** Poor rate for the current period, percentage as a decimal string ("2.1"). */
  poor_rate: string;
  /** Claims raised against the supplier, decimal string; null when none. */
  claims: string | null;
  last_event: { event_id: string; date: string } | null;
  capa_id: string | null;
  review_status: SupplierReviewStatus;
}

export interface FeedbackEvent {
  event_id: string;
  /** ISO 8601 UTC. */
  occurred_at: string;
  supplier: string;
  summary: string;
  status: FeedbackEventStatus;
}

export interface CorrectiveAction {
  capa_id: string;
  summary: string;
  status: CorrectiveActionStatus;
}

export interface SupplierQualityRegister {
  /** Period each control position reports on, as shown beside the control. */
  periods: Record<QualityPeriod, { label: string }>;
  summary: {
    events_published: number;
    vendors_under_review: string[];
    open_capa: { capa_id: string; due_date: string } | null;
    open_capa_count: number;
  };
  rows: SupplierQualityRow[];
  events: FeedbackEvent[];
  corrective_actions: CorrectiveAction[];
  /** The supplier whose review is in progress, with the inputs the frame lists. */
  review: { vendor_code: string; supplier_short: string; poor_rate: string; claims: string } | null;
}

/** F33 Supplier Quality Register. */
export function getSupplierQualityRegister(): Promise<SupplierQualityRegister> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/supplier-quality",
      note: "Per-supplier poor-item counts for month, quarter and year, poor rate, claims, last feedback event, CAPA and review status; feedback events and corrective actions come from GET /ui/v1/quality-cases. Publishing a feedback event has no endpoint in the LLD route list yet.",
    },
    supplierQualityRegister,
  );
}
