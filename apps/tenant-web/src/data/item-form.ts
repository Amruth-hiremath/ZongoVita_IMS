import "server-only";

import {
  itemFormAttributes,
  itemFormDraft,
  itemFormLifecycle,
  itemFormNumbering,
  itemFormPlanningDefaults,
  itemFormTaxonomy,
  itemFormUoms,
  itemFormVendors,
} from "@/fixtures/item-form";

import { fromFixture } from "./source";

export interface NumberingScheme {
  /** Prefix of the category's running number, e.g. "SPB-". */
  prefix: string;
  /** The code the next item will receive, e.g. "SPB-6210". */
  next_code: string;
}

/** One level of the four-level category path with the options at that level. */
export interface TaxonomyLevel {
  level: 1 | 2 | 3 | 4;
  label: string;
  options: { id: string; name: string }[];
}

export type AttributeType = "text" | "number" | "dropdown" | "date";

export interface AttributeDefinition {
  id: string;
  name: string;
  type: AttributeType;
  required: boolean;
}

export interface VendorOption {
  vendor_code: string;
  name: string;
}

export interface ItemDraft {
  name: string;
  uom: string;
  /** Decimal string; cost equals price (Q4). */
  cost: string;
  category_path: string[];
  barcode: string;
  lifecycle: string;
  batch_tracked: boolean;
  serial_tracked: boolean;
  expiry_tracked: boolean;
  shelf_life_months: string;
  min_stock: string;
  max_stock: string;
  vendor_code: string;
  vendor_item_code: string;
  /** Decimal string from the vendor's rate list. */
  rate: string;
  rate_list: string;
  moq: string;
  vendor_lead_days: string;
}

export interface ItemFormData {
  numbering: NumberingScheme;
  uoms: string[];
  taxonomy: TaxonomyLevel[];
  lifecycle: string[];
  attributes: AttributeDefinition[];
  vendors: VendorOption[];
  /** Internal PO lead time in days, a customer setting (FB-18). */
  internal_po_lead_days: number;
  /** Values the frame is drawn with. */
  draft: ItemDraft;
}

/** F08 Add / Configure Item: reference data for the form. */
export async function getItemFormData(): Promise<ItemFormData> {
  const [numbering, uoms, taxonomy, lifecycle, attributes, vendors, planning, draft] = await Promise.all([
    fromFixture(
      { endpoint: "GET /ui/v1/numbering-schemes", note: "Prefix and next running number for the selected category (Q6)." },
      itemFormNumbering,
    ),
    fromFixture({ endpoint: "GET /ui/v1/uoms" }, itemFormUoms),
    fromFixture(
      { endpoint: "GET /ui/v1/taxonomy", note: "Four-level path; options at each level depend on the parent chosen." },
      itemFormTaxonomy,
    ),
    fromFixture(
      { endpoint: "GET /ui/v1/items", note: "Item lifecycle states are not enumerated in the UI API; the form needs the allowed set." },
      itemFormLifecycle,
    ),
    fromFixture(
      { endpoint: "GET /ui/v1/attribute-definitions", note: "Custom attributes required for the selected category (Q5)." },
      itemFormAttributes,
    ),
    fromFixture({ endpoint: "GET /ui/v1/vendors", note: "Approved vendors (F37) for the preferred-vendor list." }, itemFormVendors),
    fromFixture(
      { endpoint: "GET /ui/v1/settings", note: "Internal PO lead time, the manual part of total lead time (FB-18)." },
      itemFormPlanningDefaults,
    ),
    fromFixture({ endpoint: "GET /ui/v1/items", note: "Sample values as drawn; a new item starts empty." }, itemFormDraft),
  ]);
  return {
    numbering,
    uoms,
    taxonomy,
    lifecycle,
    attributes,
    vendors,
    internal_po_lead_days: planning.internal_po_lead_days,
    draft,
  };
}
