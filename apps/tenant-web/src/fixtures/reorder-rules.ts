/** FIXTURE: reorder rule for SPB-6204 from wireframe F19. Temporary; see src/data/source.ts. */
import type { ReorderRule } from "@/data/reorder-rules";

const FORMULA = "( AvgDailyUse × ( LeadPO + LeadVendor ) ) + SafetyStock − OnHand";

const spb6204: ReorderRule = {
  item_code: "SPB-6204",
  item_name: "Ball Bearing 6204-2RS",
  category: "Spares",
  is_override: true,
  variables: [
    { name: "AvgDailyUse", value_label: "6 pcs" },
    { name: "LeadPO", value_label: "3 d · manual" },
    { name: "LeadVendor", value_label: "9 d · VD-0028" },
    { name: "SafetyStock", value_label: "40 pcs" },
    { name: "OnHand", value_label: "38 pcs" },
    { name: "InTransit", value_label: "20 pcs" },
  ],
  formula: FORMULA,
  preview: {
    location_code: "WH-PUN-02",
    expression: "( 6 × ( 3 + 9 ) ) + 40 − 38",
    result: "74",
    uom: "pcs",
  },
  lead_time: {
    internal_po_days: 3,
    internal_po_source: "manual",
    vendor_days: 9,
    vendor_code: "VD-0028",
    total_days: 12,
  },
  template: { formula: FORMULA, inherit_new_items: true },
};

export const reorderRules: Record<string, ReorderRule> = { [spb6204.item_code]: spb6204 };
