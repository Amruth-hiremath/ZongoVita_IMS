import "server-only";

import { reorderRules } from "@/fixtures/reorder-rules";

import { fromFixture } from "./source";

export interface FormulaVariable {
  name: string;
  /** Current value with its source, as shown under the name ("3 d · manual"). */
  value_label: string;
}

export interface ReorderRule {
  item_code: string;
  item_name: string;
  category: string;
  /** True when this SKU overrides its category template. */
  is_override: boolean;
  variables: FormulaVariable[];
  formula: string;
  preview: {
    location_code: string;
    /** The formula with today's values substituted. */
    expression: string;
    result: string;
    uom: string;
  };
  lead_time: {
    internal_po_days: number;
    internal_po_source: string;
    vendor_days: number;
    vendor_code: string;
    total_days: number;
  };
  template: { formula: string; inherit_new_items: boolean };
}

/** F19 Reorder Rule for one SKU. Null when the item has no rule. */
export function getReorderRule(itemCode: string): Promise<ReorderRule | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/formulas",
      note: "Per-SKU formula with its variables and their sources, the category template it overrides, the propagation flag, and a live preview from GET /ui/v1/planning (values per location, lead time split into internal PO and vendor supply, FB-18).",
    },
    reorderRules[itemCode] ?? null,
  );
}
