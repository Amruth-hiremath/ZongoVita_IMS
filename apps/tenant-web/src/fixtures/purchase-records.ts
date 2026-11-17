/** FIXTURE: sample purchase records from wireframes F40 and F41. Temporary; see src/data/source.ts. */
import type {
  InspectionResult,
  PurchaseRecordDetail,
  PurchaseRecordListPage,
  PurchaseRecordRow,
  PurchaseRecordStatus,
} from "@/data/purchase-records";

function row(
  po_number: string,
  item_code: string,
  quantity: string,
  uom: string,
  department: string,
  approved_by: string,
  inward: { date: string } | { due: string },
  inspection: InspectionResult | null,
  expected_use_date: string,
  status: PurchaseRecordStatus,
): PurchaseRecordRow {
  return {
    po_number,
    item_code,
    quantity,
    uom,
    department,
    purchased_by: "Vikram Singh",
    approved_by,
    inward_date: "date" in inward ? inward.date : null,
    inward_due_date: "due" in inward ? inward.due : null,
    inspection,
    expected_use_date,
    status,
  };
}

export const purchaseRecordListPage: PurchaseRecordListPage = {
  rows: [
    row("PO-2214", "SPB-6204", "40", "pcs", "Maintenance", "Deepa Nair", { date: "2026-09-26" }, "pass", "2026-09-28", "inwarded"),
    row("PO-2216", "HYD-SK40", "6", "kits", "Maintenance", "Priya Sharma", { due: "2026-10-05" }, null, "2026-10-06", "awaiting_inward"),
    row("PO-2213", "GLV-NIT-L", "100", "pairs", "Safety", "Deepa Nair", { date: "2026-09-18" }, "partial_fail", "2026-09-25", "exception"),
    row("PO-2197", "CUT-OIL20", "8", "drums", "Production", "Priya Sharma", { date: "2026-09-12" }, "pass", "2026-09-20", "inwarded"),
    row("PO-2188", "VBLT-A43", "120", "pcs", "Maintenance", "Deepa Nair", { date: "2026-09-02" }, "partial_fail", "2026-09-10", "exception"),
  ],
  summary: {
    period_label: "quarter",
    record_count: 34,
    total_value: "842300",
    awaiting_inward: 2,
    due_within_days: 10,
    inspection_exceptions: 2,
    avg_internal_lead_days: 3,
    avg_vendor_lead_days: 9,
  },
  total: 34,
  sorted_by: "inward date",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  filters: {
    vendors: ["Shakti Bearings Pvt Ltd", "Deccan Industrial Supplies", "Chennai Lubricants LLP", "SafeGuard Equipments India"],
    departments: ["Maintenance", "Safety", "Production"],
  },
};

export const purchaseRecordDetails: Record<string, PurchaseRecordDetail> = {
  "PO-2214": {
    po_number: "PO-2214",
    status: "inwarded",
    inspection: "pass",
    item_code: "SPB-6204",
    department: "Maintenance",
    purchased_by: "Vikram Singh",
    approved_by: "Deepa Nair",
    inward_date: "2026-09-26",
    grn_number: "GRN-2081",
    expected_use_date: "2026-09-28",
    work_order: "WO-2221",
    quantity: "40",
    uom: "pcs",
    rate: "185",
    vendor: {
      vendor_code: "VD-0028",
      legal_name: "Shakti Bearings Pvt Ltd",
      short_name: "Shakti Bearings",
      city: "Pune",
      active_since: "2024-03",
      rate_list_revision: "R3",
      moq: "20",
      supply_lead_days: 9,
    },
    inspection_details: {
      inspected_by: "Rahul Verma",
      desk: "store desk",
      inspected_at: "2026-09-26T04:35:00Z",
      verdict: "Pass",
      comments: [
        "Cartons intact on arrival · 2 pcs sampled for run-out — pass.",
        "Batch LOT-SPB-0124 verified against the vendor COC.",
        "No exceptions — units released to available stock.",
      ],
    },
    lifecycle: [
      { label: "PO raised", meta: "22 Sep · Vikram Singh", state: "done" },
      { label: "Approved", meta: "23 Sep · Deepa Nair", state: "done" },
      { label: "Inward", meta: "26 Sep · GRN-2081", state: "done" },
      { label: "Inspection", meta: "26 Sep · pass", state: "current" },
      { label: "Expected use", meta: "28 Sep · WO-2221", state: "upcoming" },
    ],
    provenance: {
      received: "40",
      issued: "6",
      on_hand: "34",
      events: [
        { title: "GRN-2081 · +40 pcs to BLR-01", meta: "26 Sep · linked to this record" },
        { title: "ISS-0339 · −4 pcs · spindle repair", meta: "12 Sep · traceable to this PO" },
        { title: "LOT-SPB-0124 · 34 pcs remain", meta: "every unit queryable to its PO" },
      ],
    },
  },
};
