import "server-only";

import { purchaseRecordDetails, purchaseRecordListPage } from "@/fixtures/purchase-records";

import { fromFixture } from "./source";

export type PurchaseRecordStatus = "awaiting_inward" | "inwarded" | "exception";
export type InspectionResult = "pass" | "partial_fail";

export interface PurchaseRecordRow {
  po_number: string;
  item_code: string;
  quantity: string;
  uom: string;
  department: string;
  purchased_by: string;
  approved_by: string;
  /** Calendar date of inward; null while awaiting inward. */
  inward_date: string | null;
  /** Expected inward date while awaiting inward. */
  inward_due_date: string | null;
  /** Null until the inward is inspected. */
  inspection: InspectionResult | null;
  expected_use_date: string;
  status: PurchaseRecordStatus;
}

export interface PurchaseRecordListPage {
  rows: PurchaseRecordRow[];
  summary: {
    period_label: string;
    record_count: number;
    /** Decimal string in the customer's currency. */
    total_value: string;
    awaiting_inward: number;
    due_within_days: number;
    inspection_exceptions: number;
    avg_internal_lead_days: number;
    avg_vendor_lead_days: number;
  };
  total: number;
  sorted_by: string;
  pages: (number | "…")[];
  page: number;
  filters: { vendors: string[]; departments: string[] };
}

export type LifecycleStepState = "done" | "current" | "upcoming";

export interface PurchaseRecordDetail {
  po_number: string;
  status: PurchaseRecordStatus;
  inspection: InspectionResult | null;
  item_code: string;
  department: string;
  purchased_by: string;
  approved_by: string;
  inward_date: string | null;
  grn_number: string | null;
  expected_use_date: string;
  work_order: string | null;
  quantity: string;
  uom: string;
  rate: string;
  vendor: {
    vendor_code: string;
    legal_name: string;
    short_name: string;
    city: string;
    /** Month the vendor became active ("2024-03"). */
    active_since: string;
    rate_list_revision: string;
    moq: string;
    supply_lead_days: number;
  };
  inspection_details: {
    inspected_by: string;
    desk: string;
    /** ISO 8601 UTC. */
    inspected_at: string;
    verdict: string;
    comments: string[];
  } | null;
  lifecycle: { label: string; meta: string; state: LifecycleStepState }[];
  provenance: {
    received: string;
    issued: string;
    on_hand: string;
    /** Movements traced to this record, newest stock event first as drawn. */
    events: { title: string; meta: string }[];
  };
}

/** F40 Purchase Records. */
export function listPurchaseRecords(): Promise<PurchaseRecordListPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/purchase-records",
      note: "Rows need inward date or due date, inspection result and expected-use date; the summary needs quarter count and value, awaiting-inward and exception counts and average internal and vendor lead time. Search, status, vendor and department become query parameters.",
    },
    purchaseRecordListPage,
  );
}

/** F41 Purchase Record detail. Null when the record does not exist. */
export function getPurchaseRecord(poNumber: string): Promise<PurchaseRecordDetail | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/purchase-records/{id}",
      note: "Detail with the vendor's rate, MOQ and lead time at the time of the PO, the GRN inspection (by, when, verdict, comments), the record lifecycle and stock provenance (ledger movements traced to this record, GET /ui/v1/ledger).",
    },
    purchaseRecordDetails[poNumber] ?? null,
  );
}
