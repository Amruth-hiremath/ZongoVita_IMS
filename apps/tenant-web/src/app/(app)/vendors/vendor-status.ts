import type { Tone } from "@ims/ui";

import type { VendorStatus } from "@/data/vendors";

/** Pill label and tone per vendor state, shared by F37 and F38. */
export const vendorStatusLabel: Record<VendorStatus, string> = {
  onboarding: "Onboarding",
  active: "Active",
  under_review: "Under review",
  retired: "Retired",
};

export const vendorStatusTone: Record<VendorStatus, Tone> = {
  onboarding: "blue",
  active: "green",
  under_review: "red",
  retired: "gray",
};
