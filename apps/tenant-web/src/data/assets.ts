import "server-only";

import { assetRegisterPage } from "@/fixtures/assets";

import { fromFixture } from "./source";

export type AssetStatus = "in_service" | "in_repair" | "spare" | "retired";

export interface AssetRow {
  asset_tag: string;
  serial_no: string;
  item_code: string;
  item_name: string;
  status: AssetStatus;
  /** Person or party holding the asset ("Priya Sharma", "vendor RMA", "Store"). */
  custodian: string;
  /** Location code, or the repair reference while in repair. */
  location: string;
}

export interface AssetItemDrillIn {
  item_code: string;
  /** How the item code was numbered, as the item master records it. */
  numbering: string;
  category_path: string[];
  stock_on_hand: string;
  uom: string;
  mapped_assets: number;
  in_service: number;
  in_repair: number;
  repair_reference: string | null;
  /** Month of the next warranty expiry across the item's assets ("2027-03"). */
  next_warranty_expiry: string | null;
}

export interface AssetRegisterPage {
  rows: AssetRow[];
  summary: {
    item_codes: string[];
    asset_count: number;
    in_service: number;
    in_service_percent: number;
    in_repair: number;
    spare: number;
    retired: number;
  };
  total: number;
  pages: (number | "…")[];
  page: number;
  drill_in: AssetItemDrillIn;
}

/** F60 IT Asset Mapping. */
export function listAssets(): Promise<AssetRegisterPage> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/assets",
      note: "Rows need serial, item code and name, status and custodian with location; the summary needs counts by status and the item codes holding assets; the drill-in needs the item's numbering, category path, stock on hand, asset counts and next warranty expiry.",
    },
    assetRegisterPage,
  );
}
