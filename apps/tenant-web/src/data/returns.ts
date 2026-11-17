import "server-only";

import { managerReturns, storeReturns } from "@/fixtures/returns";

import { fromFixture } from "./source";

/** Tint of a pill, note box or bullet as drawn. */
export type ReturnsTone = "green" | "amber" | "red" | "blue" | "violet";

export interface Kpi {
  label: string;
  value: string;
  hint?: string;
  badge?: { label: string; tone: ReturnsTone };
}

export type ReturnState =
  | "verdict_due"
  | "spec_check"
  | "overdue"
  | "claim_open"
  | "closed"
  | "routed"
  | "validating";

export interface ReturnRow {
  return_ref: string;
  /** Items and quantities as one line ("Seal kit ×1 · V-belt ×2"). */
  items_summary: string;
  /** Quantity as drawn: "1 + 2" for a mixed return, "6 pairs" with a unit. */
  qty_display: string;
  reason: string;
  returned_by: string;
  /** Lifecycle stage (manager view) or the store's last action (store view). */
  stage: string;
  state: { kind: ReturnState; label: string };
}

export interface Fact {
  label: string;
  value: string;
}

/** A tinted explanation box: a step of the verdict flow or a reason-code route. */
export interface ToneNote {
  tone: ReturnsTone;
  title: string;
  body: string;
  meta: string;
}

export interface Bullet {
  tone: "red" | "blue";
  text: string;
}

// ---------------------------------------------------------------------------- F43 (manager)

export interface VerdictPanel {
  return_ref: string;
  quarantine_ref: string;
  title: string;
  facts: Fact[];
  store_validation: string;
  disposition_label: string;
  disposition_options: string[];
  disposition_default: string;
}

export interface ManagerReturns {
  kpis: Kpi[];
  rows: ReturnRow[];
  notice: string;
  /** Verdict panels the screen can show, keyed by return_ref. */
  verdicts: VerdictPanel[];
  selected_ref: string;
  semantics: { title: string; steps: ToneNote[]; footnote: string };
  attribution: { title: string; intro: string; bullets: Bullet[] };
}

/** F43 Returns — Lifecycle & Dispositions. */
export function getManagerReturns(): Promise<ManagerReturns> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/returns",
      note: "Needs returns in flight with stage and state, the KPI counts, the quarantine record of a return awaiting verdict (store validation, hold since, vendor and PO), disposition options from GET /ui/v1/settings, and per-vendor FAIL roll-up from GET /ui/v1/supplier-quality.",
    },
    managerReturns,
  );
}

// ------------------------------------------------------------------------------ F49 (store)

export interface ValidationPanel {
  return_ref: string;
  title: string;
  facts: Fact[];
  store_check: string;
  recommendation_options: string[];
  recommendation_default: string;
}

export interface StoreReturns {
  kpis: Kpi[];
  rows: ReturnRow[];
  validations: ValidationPanel[];
  selected_ref: string;
  routing: { title: string; routes: ToneNote[] };
  never_back: { title: string; intro: string; bullets: Bullet[] };
}

/** F49 Returns — Store Processing. */
export function getStoreReturns(): Promise<StoreReturns> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/returns",
      note: "Store queue: returns at this site with the store's last action, the return being validated (ordered vs supplied), routing by reason code (GET /ui/v1/reason-codes) and per-vendor poor-quality rates from GET /ui/v1/supplier-quality.",
    },
    storeReturns,
  );
}
