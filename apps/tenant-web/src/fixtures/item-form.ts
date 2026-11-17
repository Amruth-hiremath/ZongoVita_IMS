/** FIXTURE: reference data and sample values of wireframe F08. Temporary; see src/data/source.ts. */
import type { AttributeDefinition, ItemDraft, NumberingScheme, TaxonomyLevel, VendorOption } from "@/data/item-form";

export const itemFormNumbering: NumberingScheme = { prefix: "SPB-", next_code: "SPB-6210" };

/** Units drawn on F07 and F08. */
export const itemFormUoms: string[] = ["pcs", "kit", "kg", "drum", "pair", "tub"];

/** Only the path drawn on F08 exists in the sample. */
export const itemFormTaxonomy: TaxonomyLevel[] = [
  { level: 1, label: "Category", options: [{ id: "tx-spares", name: "Spares" }] },
  { level: 2, label: "Subcategory", options: [{ id: "tx-bearings-bushings", name: "Bearings & Bushings" }] },
  { level: 3, label: "Group", options: [{ id: "tx-ball-bearings", name: "Ball Bearings" }] },
  { level: 4, label: "Type", options: [{ id: "tx-deep-groove", name: "Deep Groove" }] },
];

export const itemFormLifecycle: string[] = ["Active", "Inactive"];

export const itemFormAttributes: AttributeDefinition[] = [
  { id: "attr-brand", name: "Brand", type: "text", required: true },
  { id: "attr-grade", name: "Grade", type: "text", required: true },
  { id: "attr-size", name: "Size", type: "text", required: true },
  { id: "attr-hazard", name: "Hazard class", type: "dropdown", required: true },
];

export const itemFormVendors: VendorOption[] = [{ vendor_code: "VD-0028", name: "Shakti Bearings Pvt Ltd" }];

export const itemFormPlanningDefaults = { internal_po_lead_days: 3 };

export const itemFormDraft: ItemDraft = {
  name: "Ball Bearing 6205-2RS",
  uom: "pcs",
  cost: "210",
  category_path: ["tx-spares", "tx-bearings-bushings", "tx-ball-bearings", "tx-deep-groove"],
  barcode: "",
  lifecycle: "Active",
  batch_tracked: true,
  serial_tracked: false,
  expiry_tracked: true,
  shelf_life_months: "24",
  min_stock: "40",
  max_stock: "200",
  vendor_code: "VD-0028",
  vendor_item_code: "SB-6204",
  rate: "185",
  rate_list: "R3",
  moq: "20",
  vendor_lead_days: "9",
};
