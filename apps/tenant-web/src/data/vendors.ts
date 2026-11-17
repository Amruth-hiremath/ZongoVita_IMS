import "server-only";

import { onboardingDrafts, vendorDetails, vendorListPage } from "@/fixtures/vendors";

import { fromFixture } from "./source";

/** Vendor lifecycle state as the list and detail show it (F37 "Vendor lifecycle"). */
export type VendorStatus = "onboarding" | "active" | "under_review" | "retired";

export interface VendorListRow {
  vendor_code: string;
  company: string;
  city: string;
  gstin: string;
  /** Items in the vendor's catalogue. */
  item_count: number;
  /** Smallest MOQ across the catalogue, decimal string. */
  moq_from: string;
  lead_days_min: number;
  lead_days_max: number;
  /** Poor-quality items attributed this month (F33). */
  poor_month: number;
  status: VendorStatus;
}

export interface VendorListPage {
  rows: VendorListRow[];
  summary: {
    vendor_count: number;
    active_count: number;
    retired_count: number;
    supplied_item_count: number;
    rate_revisions_pending: number;
    poor_items_month: number;
  };
  total: number;
  sorted_by: string;
  pages: (number | "…")[];
  page: number;
  filters: { supplied_items: string[] };
}

export interface VendorCatalogueLine {
  vendor_item_code: string;
  item_code: string;
  item_name: string;
  moq: string;
  /** Current rate, decimal string in the customer's currency. */
  rate: string;
  lead_time_days: number;
  poor: { month: number; quarter: number; year: number };
}

export type RateRevisionApproval = "approved" | "pending";

export interface RateRevision {
  revision: string;
  /** Calendar date the rate applies from. */
  effective_date: string;
  item_code: string;
  previous_rate: string;
  new_rate: string;
  /** Percentage change, decimal string ("3.9"). */
  change_percent: string;
  approval: RateRevisionApproval;
}

export interface VendorDetail {
  vendor_code: string;
  legal_name: string;
  city: string;
  /** Month the vendor became active ("2024-03"). */
  vendor_since: string;
  purchase_record_count: number;
  units_supplied: string;
  status: VendorStatus;
  current_rate_list: { revision: string; effective_date: string };
  poor_month: number;
  catalogue: VendorCatalogueLine[];
  profile: {
    legal_name: string;
    gstin: string;
    udyam_msme: string;
    city: string;
    state: string;
    payment_terms: string;
    contact_name: string;
    contact_phone: string;
  };
  rate_revisions: RateRevision[];
  /** Lead time per item: vendor-stated supply time plus the internal PO time (FB-19). */
  lead_times: {
    item_code: string;
    vendor_supply_days: number;
    internal_po_days: number;
    total_days: number;
  }[];
}

export type OnboardingStepState = "done" | "current" | "upcoming";

export interface OnboardingDraft {
  vendor_code: string;
  company: string;
  city: string;
  gstin: string;
  udyam_msme: string;
  steps: { label: string; meta: string; state: OnboardingStepState }[];
  catalogue: { vendor_item_code: string; item_code: string; item_name: string; moq: string; rate: string }[];
}

/** F37 Vendors. */
export function listVendors(): Promise<VendorListPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/vendors",
      note: "List rows need catalogue size, smallest MOQ, lead-time range and this month's poor-item count (from GET /ui/v1/supplier-quality) per vendor; the summary needs pending rate revisions. Search, status and supplies-item become query parameters.",
    },
    vendorListPage,
  );
}

/** F38 Vendor detail. Null when the vendor does not exist. */
export function getVendor(vendorCode: string): Promise<VendorDetail | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/vendors/{id}",
      note: "Detail with catalogue and MOQ, rate revisions (GET /ui/v1/vendors/{id}/rates), per-item lead times and poor-item counts per month, quarter and year.",
    },
    vendorDetails[vendorCode] ?? null,
  );
}

/** F39 Vendor Onboarding: a vendor still in the onboarding wizard. Null when there is no such draft. */
export function getOnboardingDraft(vendorCode: string): Promise<OnboardingDraft | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/vendors/{id}",
      note: "A vendor in the onboarding state, with the wizard step reached and the catalogue lines captured so far.",
    },
    onboardingDrafts[vendorCode] ?? null,
  );
}
