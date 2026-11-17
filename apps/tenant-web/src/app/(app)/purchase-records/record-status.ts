import type { Tone } from "@ims/ui";

import type { InspectionResult, PurchaseRecordStatus } from "@/data/purchase-records";

/** Pill label and tone per purchase-record state, shared by F40 and F41. */
export const recordStatusLabel: Record<PurchaseRecordStatus, string> = {
  awaiting_inward: "Awaiting inward",
  inwarded: "Inwarded",
  exception: "Exception",
};

export const recordStatusTone: Record<PurchaseRecordStatus, Tone> = {
  awaiting_inward: "amber",
  inwarded: "green",
  exception: "red",
};

export const inspectionLabel: Record<InspectionResult, string> = {
  pass: "Pass",
  partial_fail: "Partial fail",
};
