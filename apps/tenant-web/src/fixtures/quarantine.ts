/** FIXTURE: sample data from wireframe F32. Temporary; see src/data/source.ts. */
import type { QuarantineQueue } from "@/data/quarantine";

export const quarantineQueue: QuarantineQueue = {
  kpis: [
    { label: "In quarantine", value: "9 units", hint: "3 lines · 2 sites" },
    { label: "Awaiting validation", value: "3", badge: { label: "1 overdue", tone: "amber" } },
    { label: "Avg hold time", value: "1.8 d", hint: "validation window ≤ 3 d" },
    { label: "Released today", value: "4", badge: { label: "restocked", tone: "green" } },
  ],
  rows: [
    {
      quarantine_ref: "QTN-0031",
      item_name: "Hydraulic Seal Kit 40 mm",
      qty_display: "1 kit",
      reason: "Poor quality",
      since: "26 Sep 11:20",
      vendor_po: "Deccan · PO-2190",
      state: { kind: "due_today", label: "Due today" },
    },
    {
      quarantine_ref: "QTN-0029",
      item_name: "Safety Gloves Nitrile (L)",
      qty_display: "6 pairs",
      reason: "Damaged",
      since: "21 Sep 14:02",
      vendor_po: "SafeGuard · PO-2213",
      state: { kind: "overdue", label: "Overdue 1 d" },
    },
    {
      quarantine_ref: "QTN-0027",
      item_name: "V-Belt A-43",
      qty_display: "2 pcs",
      reason: "Wrong item",
      since: "19 Sep 09:48",
      vendor_po: "Shakti · PO-2188",
      state: { kind: "spec_check", label: "Spec check" },
    },
  ],
  checklists: [
    {
      quarantine_ref: "QTN-0031",
      title: "Validation checklist — QTN-0031 · HYD-SK40 ×1",
      checks: [
        {
          id: "identity",
          label: "Identity — barcode & SKU",
          detail: "scans clean against the returned line",
          checked: false,
        },
        { id: "specification", label: "Specification match", detail: "40 mm · EPDM · matches item master", checked: false },
        {
          id: "condition",
          label: "Physical condition",
          detail: "seal lip hardness out of spec — measured",
          checked: false,
        },
        {
          id: "evidence",
          label: "Reason evidence",
          detail: "requester photo + issuance record attached",
          checked: false,
        },
        { id: "vendor", label: "Vendor attribution", detail: "Deccan Industrial Supplies · via PO-2190", checked: false },
      ],
      footnote:
        "Validation can overturn the stated reason — mismatches and wrong details attached at issuance are corrected at this gate before anything restocks.",
    },
  ],
  selected_ref: "QTN-0031",
  verdict_paths: [
    {
      tone: "green",
      label: "PASS — validated OK",
      body: "Restock: returns to original inventory, availability and reorder resume immediately",
    },
    {
      tone: "red",
      label: "FAIL — poor quality / damage",
      body: "Quality-hold: separate lifecycle — can never return to stock. Disposition: scrap, rework or supplier return (configurable)",
    },
  ],
  paths_footnote:
    "FAIL lines flow to the supplier quality register (F33) with vendor attribution — and raise an external feedback event.",
};
