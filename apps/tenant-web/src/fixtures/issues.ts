/** FIXTURE: sample data from wireframes F11 and F12. Temporary; see src/data/source.ts. */
import type { IssueDraft, IssueGuardRails } from "@/data/issues";

export const issueDraft: IssueDraft = {
  queue_id: "018f6f2a-0000-7000-8000-00000000f417",
  issue_no: "ISS-0342",
  issue_date: "2026-09-26",
  issue_from: {
    value: "WH-BLR-01",
    options: [{ value: "WH-BLR-01", label: "WH-BLR-01 · Bengaluru" }],
  },
  issue_to: {
    value: "wo-2214",
    options: [{ value: "wo-2214", label: "Maintenance · WO-2214" }],
  },
  request: {
    value: "REQ-0417",
    options: [{ value: "REQ-0417", label: "REQ-0417 · Rahul Verma" }],
  },
  lock: {
    request_ref: "REQ-0417",
    qty: "6",
    uom: "pcs",
    item_code: "SPB-6204",
    locked_at_label: "26 Sep 10:12",
    locked_by: "first approval",
  },
  requester: "Rahul Verma",
  lines: [
    {
      item_code: "SPB-6204",
      name: "Ball Bearing 6204-2RS",
      free: "12",
      locked: "6",
      issue_qty: "40",
      batch: "LOT-SPB-0124",
      remarks: "REQ-0417 · spindle",
    },
    {
      item_code: "GRS-EP2-5",
      name: "Grease EP-2 5 kg",
      free: "31",
      locked: "0",
      issue_qty: "2",
      batch: "LOT-GE-0426",
      remarks: "",
    },
    {
      item_code: "GLV-NIT-L",
      name: "Safety Gloves Nitrile (L)",
      free: "36",
      locked: "0",
      issue_qty: "6",
      batch: null,
      remarks: "",
    },
  ],
  work_order: {
    ref: "WO-2214",
    asset: "CNC Milling M-02",
    description: "Spindle bearing replacement",
    source: "From Asset Maintenance",
  },
  deducts: [
    { qty: "6", uom: "pcs", label: "SPB-6204" },
    { qty: "2", uom: "tubs", label: "Grease" },
    { qty: "6", uom: "pairs", label: "Gloves" },
  ],
  value: "3260",
};

export const issueGuardRails: IssueGuardRails = {
  blocked: {
    item_code: "SPB-6204",
    name: "Ball Bearing 6204-2RS",
    location_code: "WH-BLR-01",
    uom: "pcs",
    free: "12",
    requested: "40",
    locked: "6",
    lock_ref: "REQ-0417",
    on_hand: "34",
  },
  concurrent: { other_qty: "4", uom: "pcs", at_label: "09:41:58", snapshot_free: "12" },
  success: { issue_no: "ISS-0342" },
};
