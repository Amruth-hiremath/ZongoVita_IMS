/** FIXTURE: alerts and reorder suggestions from wireframe F18. Temporary; see src/data/source.ts. */
import type { AlertRow, AlertStatusKind, AlertsPage } from "@/data/alerts";

function row(
  item_code: string,
  name: string,
  location_code: string,
  on_hand: string,
  min_qty: string,
  lead_po_days: number,
  lead_vendor_days: number,
  suggested_qty: string | null,
  suggested_uom: string,
  kind: AlertStatusKind,
  label: string,
): AlertRow {
  return {
    item_code,
    name,
    location_code,
    on_hand,
    min_qty,
    lead_po_days,
    lead_vendor_days,
    suggested_qty,
    suggested_uom,
    status: { kind, label },
  };
}

export const alertsPage: AlertsPage = {
  open_count: 13,
  channels: [
    { id: "dashboard", label: "Dashboard", enabled: true },
    { id: "email_digest", label: "Email digest 08:00 IST", enabled: true },
    { id: "sms", label: "SMS — undecided (Q12)", enabled: false },
    { id: "webhook", label: "Webhook: low.stock.alert (FR-16)", enabled: true },
  ],
  rows: [
    row("SPB-6204", "Ball Bearing 6204-2RS", "WH-PUN-02", "38", "40", 3, 9, "74", "pcs", "below_min", "Below min"),
    row("GLV-NIT-L", "Safety Gloves Nitrile (L)", "ST-MAA-01", "96", "100", 2, 5, "140", "pairs", "below_min", "Below min"),
    row("CUT-OIL20", "Cutting Oil 20 L", "WH-BLR-01", "24", "30", 6, 14, "18", "drums", "batch_expiring", "Batch expiring"),
    row("GRS-EP2-5", "Grease EP-2 5 kg", "WH-BLR-01", "55", "20", 2, 4, null, "tubs", "expiry_window", "Expiry 30 d"),
    row("HYD-SK40", "Hydraulic Seal Kit 40 mm", "WH-PUN-02", "16", "15", 1, 5, null, "kits", "above_min", "Above min"),
  ],
  total: 13,
  sorted_by: "severity",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  formula_example: {
    item_code: "SPB-6204",
    location_short: "PUN-02",
    expression: "( 6 avg/day × [ 3 d PO + 9 d vendor ] ) + 40 safety − 38 on hand",
    result: "74",
    uom: "pcs",
    lead_sources: "Lead sources — PO time: manual per SKU · vendor: VD-0028 Shakti (F38).",
  },
  dead_stock_example: { item_code: "WEL-R7018", idle_days: 180, threshold_days: 120 },
  webhook_example:
    'POST /webhooks { "event": "low.stock.alert", "sku": "SPB-6204", "location": "WH-PUN-02",\n"onHand": 38, "min": 40, "suggestedQty": 74 }',
};
