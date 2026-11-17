/** FIXTURE: sample IT assets from wireframe F60. Temporary; see src/data/source.ts. */
import type { AssetRegisterPage, AssetRow, AssetStatus } from "@/data/assets";

function row(
  asset_tag: string,
  serial_no: string,
  item_code: string,
  item_name: string,
  status: AssetStatus,
  custodian: string,
  location: string,
): AssetRow {
  return { asset_tag, serial_no, item_code, item_name, status, custodian, location };
}

export const assetRegisterPage: AssetRegisterPage = {
  rows: [
    row("AST-01042", "DL5540-88231", "LAP-5540", "Latitude 5540 Laptop", "in_service", "Priya Sharma", "WH-BLR-01"),
    row("AST-01043", "DL5540-88407", "LAP-5540", "Latitude 5540 Laptop", "in_service", "Kavita Rao", "WH-PUN-02"),
    row("AST-01044", "DL5540-88512", "LAP-5540", "Latitude 5540 Laptop", "in_repair", "vendor RMA", "RPR-0031"),
    row("AST-01045", "DL5540-88644", "LAP-5540", "Latitude 5540 Laptop", "spare", "Store", "WH-BLR-01"),
    row("AST-01046", "DE24F-55118", "MON-2440", "Dell 24 FHD Monitor", "in_service", "Ananya Iyer", "ST-MAA-01"),
    row("AST-01047", "DE24F-55139", "MON-2440", "Dell 24 FHD Monitor", "in_service", "Rahul Verma", "WH-BLR-01"),
  ],
  summary: {
    item_codes: ["LAP-5540", "MON-2440", "PRT-3014"],
    asset_count: 12,
    in_service: 9,
    in_service_percent: 75,
    in_repair: 1,
    spare: 1,
    retired: 1,
  },
  total: 12,
  pages: [1, 2, "…", 9, 10],
  page: 1,
  drill_in: {
    item_code: "LAP-5540",
    numbering: "manual (Q6)",
    category_path: ["IT", "Computing", "Laptops", "Business"],
    stock_on_hand: "4",
    uom: "pcs",
    mapped_assets: 4,
    in_service: 3,
    in_repair: 1,
    repair_reference: "RPR-0031",
    next_warranty_expiry: "2027-03",
  },
};
