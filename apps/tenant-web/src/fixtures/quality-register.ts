/** FIXTURE: sample supplier quality register from wireframe F33. Temporary; see src/data/source.ts. */
import type { SupplierQualityRegister } from "@/data/quality-register";

export const supplierQualityRegister: SupplierQualityRegister = {
  // Only the month label is drawn; the quarter and year labels are the calendar periods that
  // contain September 2026 (assumption).
  periods: {
    month: { label: "September 2026" },
    quarter: { label: "Jul–Sep 2026" },
    year: { label: "2026" },
  },
  summary: {
    events_published: 2,
    vendors_under_review: ["SafeGuard"],
    open_capa: { capa_id: "CAPA-0007", due_date: "2026-10-03" },
    open_capa_count: 1,
  },
  rows: [
    {
      vendor_code: "VD-0007",
      supplier: "SafeGuard Equipments India",
      city: "Coimbatore",
      pos_received: 18,
      poor: { month: 2, quarter: 4, year: 9 },
      poor_rate: "2.1",
      claims: "1430",
      last_event: { event_id: "EF-0041", date: "2026-09-26" },
      capa_id: "CAPA-0007",
      review_status: "under_review",
    },
    {
      vendor_code: "VD-0031",
      supplier: "Deccan Industrial Supplies",
      city: "Hyderabad",
      pos_received: 34,
      poor: { month: 1, quarter: 2, year: 5 },
      poor_rate: "0.8",
      claims: "710",
      last_event: { event_id: "EF-0038", date: "2026-09-24" },
      capa_id: "CAPA-0006",
      review_status: "active",
    },
    {
      vendor_code: "VD-0028",
      supplier: "Shakti Bearings Pvt Ltd",
      city: "Pune",
      pos_received: 34,
      poor: { month: 0, quarter: 1, year: 2 },
      poor_rate: "0.2",
      claims: null,
      last_event: null,
      capa_id: null,
      review_status: "active",
    },
    {
      vendor_code: "VD-0014",
      supplier: "Chennai Lubricants LLP",
      city: "Chennai",
      pos_received: 21,
      poor: { month: 0, quarter: 1, year: 1 },
      poor_rate: "0.4",
      claims: null,
      last_event: null,
      capa_id: null,
      review_status: "active",
    },
  ],
  events: [
    {
      event_id: "EF-0041",
      occurred_at: "2026-09-26T05:10:00Z",
      supplier: "SafeGuard Equipments",
      summary: "2 pairs gloves · torn seam on issue",
      status: "published",
    },
    {
      event_id: "EF-0038",
      occurred_at: "2026-09-24T10:42:00Z",
      supplier: "Deccan Industrial",
      summary: "Seal kit hardness out of spec",
      status: "published",
    },
    {
      event_id: "EF-0035",
      occurred_at: "2026-09-18T04:00:00Z",
      supplier: "SafeGuard Equipments",
      summary: "Glove lot failed seam-slip test",
      status: "acknowledged",
    },
  ],
  corrective_actions: [
    {
      capa_id: "CAPA-0007",
      summary: "Root cause: seam-slip on glove lot — remediation plan + re-test batch required",
      status: "open",
    },
    { capa_id: "CAPA-0006", summary: "Hardness certificate resubmitted and verified", status: "closed" },
  ],
  review: { vendor_code: "VD-0007", supplier_short: "SafeGuard", poor_rate: "2.1", claims: "1430" },
};
