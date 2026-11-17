import "server-only";

import { itemListPage } from "@/fixtures/items";

import { fromFixture } from "./source";

/** How an item's stock stands, as the list shows it in the Status column. */
export type StockStatusKind = "in_stock" | "below_min" | "batch_expiring" | "expiry_window" | "dead";

export interface ItemListRow {
  item_code: string;
  name: string;
  category: string;
  uom: string;
  /** Decimal string in the customer's currency. */
  cost: string;
  on_hand: string;
  locked: string;
  quarantined: string;
  location_count: number;
  has_image: boolean;
  stock_status: { kind: StockStatusKind; label: string };
}

export interface ItemListPage {
  rows: ItemListRow[];
  total: number;
  location_count: number;
  sorted_by: string;
  /** Page tokens as the pager shows them. */
  pages: (number | "…")[];
  page: number;
  filters: { categories: string[]; locations: string[]; statuses: string[] };
}

/** F07 Items & Catalog. */
export function listItems(): Promise<ItemListPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/items",
      note: "List rows need on-hand, locked and quarantined totals, location count and a stock-status summary per item; search, category, location and status become query parameters with cursor pagination.",
    },
    itemListPage,
  );
}
