/** FIXTURE: sample vendors from wireframes F37, F38 and F39. Temporary; see src/data/source.ts. */
import type { OnboardingDraft, VendorDetail, VendorListPage, VendorListRow, VendorStatus } from "@/data/vendors";

function row(
  vendor_code: string,
  company: string,
  city: string,
  gstin: string,
  item_count: number,
  moq_from: string,
  lead_days_min: number,
  lead_days_max: number,
  poor_month: number,
  status: VendorStatus,
): VendorListRow {
  return { vendor_code, company, city, gstin, item_count, moq_from, lead_days_min, lead_days_max, poor_month, status };
}

export const vendorListPage: VendorListPage = {
  rows: [
    row("VD-0028", "Shakti Bearings Pvt Ltd", "Pune", "27AABCS9142F1Z5", 14, "20", 9, 12, 0, "active"),
    row("VD-0031", "Deccan Industrial Supplies", "Hyderabad", "36AACCD8271K1Z2", 9, "10", 6, 10, 1, "active"),
    row("VD-0014", "Chennai Lubricants LLP", "Chennai", "33AAGCC2210P1Z9", 6, "4", 4, 7, 0, "active"),
    row("VD-0007", "SafeGuard Equipments India", "Coimbatore", "33AAECS6711Q1Z8", 11, "50", 12, 15, 2, "under_review"),
    row("VD-0022", "Metro Tool House", "Mumbai", "27AAFCM9023H1ZR", 22, "5", 7, 9, 0, "retired"),
  ],
  summary: {
    vendor_count: 5,
    active_count: 4,
    retired_count: 1,
    supplied_item_count: 62,
    rate_revisions_pending: 1,
    poor_items_month: 3,
  },
  total: 5,
  sorted_by: "company",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  filters: { supplied_items: ["SPB-6204", "SPB-6205", "SPB-6200", "VBLT-A43"] },
};

export const vendorDetails: Record<string, VendorDetail> = {
  "VD-0028": {
    vendor_code: "VD-0028",
    legal_name: "Shakti Bearings Pvt Ltd",
    city: "Pune",
    vendor_since: "2024-03",
    purchase_record_count: 34,
    units_supplied: "2840",
    status: "active",
    current_rate_list: { revision: "R3", effective_date: "2026-04-01" },
    poor_month: 0,
    catalogue: [
      {
        vendor_item_code: "SB-6204",
        item_code: "SPB-6204",
        item_name: "Ball Bearing 6204-2RS",
        moq: "20",
        rate: "185",
        lead_time_days: 9,
        poor: { month: 0, quarter: 1, year: 2 },
      },
      {
        vendor_item_code: "SB-6205",
        item_code: "SPB-6205",
        item_name: "Ball Bearing 6205-2RS",
        moq: "20",
        rate: "210",
        lead_time_days: 9,
        poor: { month: 0, quarter: 0, year: 0 },
      },
      {
        vendor_item_code: "SB-6200",
        item_code: "SPB-6200",
        item_name: "Ball Bearing 6200-2RS",
        moq: "30",
        rate: "128",
        lead_time_days: 9,
        poor: { month: 0, quarter: 0, year: 1 },
      },
      {
        vendor_item_code: "VB-A43",
        item_code: "VBLT-A43",
        item_name: "V-Belt A-43",
        moq: "50",
        rate: "310",
        lead_time_days: 12,
        poor: { month: 0, quarter: 0, year: 0 },
      },
    ],
    profile: {
      legal_name: "Shakti Bearings Pvt Ltd",
      gstin: "27AABCS9142F1Z5",
      udyam_msme: "UDYAM-PN-03-0041826",
      city: "Pune",
      state: "Maharashtra",
      payment_terms: "Net 30 · 2% 10 days",
      contact_name: "R. Shakti",
      contact_phone: "+91 98220 41187",
    },
    rate_revisions: [
      {
        revision: "R3",
        effective_date: "2026-04-01",
        item_code: "SPB-6204",
        previous_rate: "178",
        new_rate: "185",
        change_percent: "3.9",
        approval: "approved",
      },
      {
        revision: "R3",
        effective_date: "2026-04-01",
        item_code: "VBLT-A43",
        previous_rate: "305",
        new_rate: "310",
        change_percent: "1.6",
        approval: "approved",
      },
      {
        revision: "R4",
        effective_date: "2026-10-01",
        item_code: "SPB-6205",
        previous_rate: "210",
        new_rate: "216",
        change_percent: "2.9",
        approval: "pending",
      },
    ],
    lead_times: [{ item_code: "SPB-6204", vendor_supply_days: 9, internal_po_days: 3, total_days: 12 }],
  },
};

export const onboardingDrafts: Record<string, OnboardingDraft> = {
  "VD-0043": {
    vendor_code: "VD-0043",
    company: "Prakash Engineering Works",
    city: "Rajkot",
    gstin: "24AAFCP9821M1Z7",
    udyam_msme: "24-0092138",
    steps: [
      { label: "Company & registration", meta: "done · Prakash Engineering", state: "done" },
      { label: "Catalogue & MOQ", meta: "2 items added", state: "current" },
      { label: "Rate list", meta: "next", state: "upcoming" },
      { label: "Lead times", meta: "next", state: "upcoming" },
      { label: "Review & activate", meta: "activates vendor", state: "upcoming" },
    ],
    catalogue: [
      { vendor_item_code: "PE-BRG-6204", item_code: "SPB-6204", item_name: "Ball Bearing 6204-2RS", moq: "20", rate: "182" },
      { vendor_item_code: "PE-BRG-6205", item_code: "SPB-6205", item_name: "Ball Bearing 6205-2RS", moq: "20", rate: "207" },
      { vendor_item_code: "PE-BRG-6200", item_code: "SPB-6200", item_name: "Ball Bearing 6200-2RS", moq: "30", rate: "121" },
      { vendor_item_code: "PE-VB-A43", item_code: "VBLT-A43", item_name: "V-Belt A-43", moq: "50", rate: "305" },
    ],
  },
};
