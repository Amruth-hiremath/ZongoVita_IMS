/** FIXTURE: sample rows from wireframe F07. Temporary; see src/data/source.ts. */
import type { ItemListPage, ItemListRow, StockStatusKind } from "@/data/items";

function row(
  item_code: string,
  name: string,
  category: string,
  uom: string,
  cost: string,
  on_hand: string,
  locked: string,
  quarantined: string,
  location_count: number,
  kind: StockStatusKind,
  label: string,
): ItemListRow {
  return {
    item_code,
    name,
    category,
    uom,
    cost,
    on_hand,
    locked,
    quarantined,
    location_count,
    has_image: true,
    stock_status: { kind, label },
  };
}

export const itemListPage: ItemListPage = {
  rows: [
    row("SPB-6204", "Ball Bearing 6204-2RS", "Spares", "pcs", "185", "116", "6", "0", 3, "below_min", "Below min"),
    row("HYD-SK40", "Hydraulic Seal Kit 40 mm", "Spares", "kit", "1240", "34", "0", "0", 2, "in_stock", "In stock"),
    row("VBLT-A43", "V-Belt A-43", "Spares", "pcs", "310", "148", "0", "2", 3, "in_stock", "In stock"),
    row("MS-SH2", "MS Sheet 2 mm", "Raw Material", "kg", "58", "2400", "0", "0", 1, "in_stock", "In stock"),
    row("CUT-OIL20", "Cutting Oil 20 L", "Consumables", "drum", "2350", "41", "0", "0", 2, "batch_expiring", "Batch expiring"),
    row("GLV-NIT-L", "Safety Gloves Nitrile (L)", "Consumables", "pair", "145", "96", "24", "0", 3, "below_min", "Below min"),
    row("GRS-EP2-5", "Grease EP-2 5 kg", "Consumables", "tub", "640", "55", "0", "0", 2, "expiry_window", "Expiry 30 d"),
    row("MCB-32A", "Circuit Breaker 32 A", "Electrical", "pcs", "475", "72", "0", "0", 1, "in_stock", "In stock"),
    row("WEL-R7018", "Welding Electrodes E7018", "Consumables", "kg", "92", "210", "0", "0", 1, "dead", "Dead 180 d"),
    row("BRG-PL3T", "Bearing Puller 3 T", "Tools", "unit", "4200", "12", "0", "0", 2, "in_stock", "In stock"),
  ],
  total: 1284,
  location_count: 4,
  sorted_by: "SKU",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  filters: {
    categories: ["Spares", "Raw Material", "Consumables", "Electrical", "Tools"],
    locations: ["WH-BLR-01", "WH-PUN-02", "ST-MAA-01", "WH-HYD-03"],
    statuses: ["Active", "Inactive", "Draft"],
  },
};
