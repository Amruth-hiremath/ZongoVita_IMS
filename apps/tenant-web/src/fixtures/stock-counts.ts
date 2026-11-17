/** FIXTURE: count session CC-0057 from wireframes F16 and F17. Temporary; see src/data/source.ts. */
import type { CountSession, CountSheetLine, VarianceReview } from "@/data/stock-counts";

function line(item_code: string, name: string, bin: string, uom: string, counted_qty: string): CountSheetLine {
  return {
    item_code,
    name,
    bin,
    uom,
    system_qty: null,
    counted_qty,
    status: { kind: "pending", label: "Pending" },
  };
}

const cc0057: CountSession = {
  count_no: "CC-0057",
  count_types: ["Cycle count"],
  count_type: "Cycle count",
  locations: [
    { id: "018f6f2a-0000-7000-8000-0000000000b1", label: "WH-BLR-01 · Bengaluru" },
  ],
  location_id: "018f6f2a-0000-7000-8000-0000000000b1",
  scope: "Aisle B · Spares",
  blind: true,
  counted_lines: 37,
  total_lines: 41,
  lines: [
    line("SPB-6204", "Ball Bearing 6204-2RS", "B-04", "pcs", "43"),
    line("VBLT-A43", "V-Belt A-43", "B-07", "pcs", "150"),
    line("HYD-SK40", "Hydraulic Seal Kit 40 mm", "B-02", "kit", "18"),
    line("MCB-32A", "Circuit Breaker 32 A", "B-11", "pcs", "72"),
    line("BRG-PL3T", "Bearing Puller 3 T", "B-12", "unit", "12"),
    line("GRS-EP2-5", "Grease EP-2 5 kg", "B-09", "tub", "55"),
  ],
  filter_label: "uncounted first",
  pages: [1, 2, "…", 9, 10],
  page: 1,
};

export const countSessions: Record<string, CountSession> = { [cc0057.count_no]: cc0057 };

export const featuredCountNo = cc0057.count_no;

const cc0057Variance: VarianceReview = {
  count_no: "CC-0057",
  sku_count: 41,
  net_impact: "-1065",
  lines: [
    {
      item_code: "SPB-6204",
      name: "Ball Bearing 6204-2RS",
      bin: "B-04",
      system_qty: "46",
      counted_qty: "43",
      variance: "-3",
      impact: "-555",
      reason: "Pick miss",
      decision: { kind: "approval_required", label: "Approve?" },
    },
    {
      item_code: "VBLT-A43",
      name: "V-Belt A-43",
      bin: "B-07",
      system_qty: "148",
      counted_qty: "150",
      variance: "2",
      impact: "620",
      reason: "Found in bin B-08",
      decision: { kind: "approval_required", label: "Approve?" },
    },
    {
      item_code: "HYD-SK40",
      name: "Hydraulic Seal Kit 40 mm",
      bin: "B-02",
      system_qty: "18",
      counted_qty: "18",
      variance: "0",
      impact: "0",
      reason: null,
      decision: { kind: "match", label: "Match" },
    },
  ],
  adjustments: [
    {
      item_code: "SPB-6204",
      location_code: "WH-BLR-01",
      from_qty: "46",
      to_qty: "43",
      uom: "pcs",
      movement_note: "movement record: count adjustment, ref CC-0057",
    },
    {
      item_code: "VBLT-A43",
      location_code: "WH-BLR-01",
      from_qty: "148",
      to_qty: "150",
      uom: "pcs",
      movement_note: "movement record: count adjustment, ref CC-0057",
    },
  ],
  policy: {
    rules: [
      { id: "variance_pct", label: "Variance beyond ±2% needs approval", enabled: true },
      { id: "value_impact", label: "Value impact over ₹500 needs approval", enabled: true },
      { id: "photo_evidence", label: "Photo evidence required (future)", enabled: false },
    ],
    approvers: ["Type 2"],
  },
};

export const varianceReviews: Record<string, VarianceReview> = { [cc0057Variance.count_no]: cc0057Variance };
