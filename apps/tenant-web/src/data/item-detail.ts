import "server-only";

import { itemDetails } from "@/fixtures/item-detail";

import { fromFixture } from "./source";

export type LocationStockKind = "healthy" | "below_min";
export type LotStatusKind = "fresh" | "expiring" | "expired";

export interface ItemDetail {
  item_code: string;
  name: string;
  category: string;
  uom: string;
  /** Decimal string, customer currency. */
  cost: string;
  lifecycle: string;
  /** ISO 8601 date. */
  created_at: string;
  created_by: string;
  has_image: boolean;
  batch_tracked: boolean;
  expiry_tracked: boolean;
  reorder_rule: "default" | "custom";
  /** Location codes where on hand is below the minimum. */
  below_min_locations: string[];
  attributes: { name: string; value: string }[];
  thresholds: {
    min: string;
    max: string;
    internal_po_lead_days: number;
    vendor_lead_days: number;
    avg_daily_use: string;
    formula: string;
  };
  stock: {
    location_code: string;
    location_name: string;
    on_hand: string;
    free: string;
    locked: string;
    quarantined: string;
    /** Decimal string, customer currency. */
    value: string;
    status: { kind: LocationStockKind; label: string };
  }[];
  lots: {
    lot_no: string;
    /** Display month as drawn ("Jan 2026"). */
    manufactured: string;
    /** ISO 8601 date, or null when the lot has no expiry. */
    expires_on: string | null;
    qty: string;
    location_code: string;
    status: { kind: LotStatusKind; label: string };
  }[];
  /** Expiry-window notice shown under the lots, if any (FB-05). */
  expiry_notice: string | null;
  movements: { title: string; meta: string }[];
}

/** F09 Item detail. Null when no item has this code. */
export async function getItemDetail(itemCode: string): Promise<ItemDetail | null> {
  const item = await fromFixture(
    {
      endpoint: "GET /ui/v1/items",
      note: "Single item by code with attributes, flags and creator. Stock by location from GET /ui/v1/stock, lots from GET /ui/v1/items/{id}/lots, thresholds and lead time from GET /ui/v1/planning, movements from GET /ui/v1/ledger.",
    },
    Object.hasOwn(itemDetails, itemCode) ? (itemDetails[itemCode] ?? null) : null,
  );
  return item;
}
