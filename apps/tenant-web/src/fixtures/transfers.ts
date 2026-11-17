/** FIXTURE: sample transfer from wireframes F14 and F15. Temporary; see src/data/source.ts. */
import type { NewTransferDraft, TransferDetail } from "@/data/transfers";

const trf0092: TransferDetail = {
  transfer_no: "TRF-0092",
  from_location_code: "BLR-01",
  to_location_code: "PUN-02",
  requested_by: { name: "Suresh Patil", type_label: "Type 3" },
  approved_by: { name: "Priya Sharma", type_label: "Type 2" },
  dispatched_at_display: "25 Sep 17:30",
  priority: "Normal",
  reason: "Replenishment",
  steps: [
    { label: "Requested", meta: "25 Sep 14:02", state: "done" },
    { label: "Approved", meta: "25 Sep 15:44", state: "done" },
    { label: "Dispatched", meta: "25 Sep 17:30", state: "current" },
    { label: "Received", meta: "in transit · ETA 27 Sep", state: "upcoming" },
  ],
  lines: [
    { item_code: "SPB-6204", name: "Ball Bearing 6204-2RS", sent_qty: "20", received_qty: null, value: "3700" },
    { item_code: "VBLT-A43", name: "V-Belt A-43", sent_qty: "60", received_qty: null, value: "18600" },
  ],
  audit: [
    { title: "Requested · 2 lines", meta: "Suresh Patil · 25 Sep 14:02" },
    { title: "Approved", meta: "Priya Sharma · 25 Sep 15:44" },
    { title: "Challan CHN-0381 printed", meta: "Suresh Patil · 25 Sep 16:50" },
    { title: "Dispatched · truck TN-01-AX-4471", meta: "Suresh Patil · 25 Sep 17:30" },
    { title: "In transit", meta: "system · live tracking off — manual" },
  ],
  stage_actions: [
    { label: "Approve / Reject", actor: "Type 2 · Priya Sharma", state: "done" },
    { label: "Dispatch + challan", actor: "Type 3 · Suresh Patil", state: "done" },
    { label: "Confirm receipt", actor: "Type 3 · Kavita Rao (PUN-02)", state: "current" },
    { label: "Report shortage", actor: "Type 3 · Kavita Rao", state: "if_needed" },
  ],
};

export const transfers: Record<string, TransferDetail> = { [trf0092.transfer_no]: trf0092 };

export const featuredTransferNo = trf0092.transfer_no;

export const newTransferDraft: NewTransferDraft = {
  locations: [
    { id: "018f6f2a-0000-7000-8000-0000000000b1", label: "WH-BLR-01 · Bengaluru" },
    { id: "018f6f2a-0000-7000-8000-0000000000b2", label: "WH-PUN-02 · Pune" },
    { id: "018f6f2a-0000-7000-8000-0000000000b3", label: "ST-MAA-01 · Chennai" },
    { id: "018f6f2a-0000-7000-8000-0000000000b4", label: "WH-HYD-03 · Hyderabad" },
  ],
  from_location_id: "018f6f2a-0000-7000-8000-0000000000b1",
  to_location_id: "018f6f2a-0000-7000-8000-0000000000b2",
  from_location_short: "BLR-01",
  requested_date: "2026-09-26",
  priorities: ["Normal"],
  priority: "Normal",
  reasons: ["Replenishment"],
  reason: "Replenishment",
  routing: "Type 2 · Store → Type 2 · Operations",
  lines: [
    {
      item_code: "SPB-6204",
      name: "Ball Bearing 6204-2RS",
      free_qty: "46",
      qty: "20",
      batch_no: "LOT-SPB-0124",
      value: "3700",
    },
    { item_code: "VBLT-A43", name: "V-Belt A-43", free_qty: "94", qty: "60", batch_no: null, value: "18600" },
  ],
  notes: "Pune plant consumption up after WO-2214;\nreplenish before next week's maintenance window.",
};
