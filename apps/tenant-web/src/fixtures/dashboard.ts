/** FIXTURE: sample content of wireframes F04, F05 and F48. Temporary; see src/data/source.ts. */
import type {
  ActivityEntry,
  AdminSummary,
  ApprovalQueueRow,
  AttentionRow,
  CountInProgress,
  FulfilmentQueueRow,
  InboundRow,
  IntegrationStatus,
  ManagerSummary,
  QuarantineAgingRow,
  ReorderSuggestionRow,
  StoreSummary,
  SystemHealth,
  WaitingTask,
} from "@/data/dashboard";

// ---------------------------------------------------------------------------------------- F04

export const adminSummary: AdminSummary = {
  locations: { total: 4, live: 1, staged: 3 },
  items: { total: 1284, category_count: 10 },
  active_users: {
    total: 18,
    by_user_type: [
      { user_type_no: 1, count: 2 },
      { user_type_no: 2, count: 4 },
      { user_type_no: 3, count: 12 },
    ],
  },
  pending_approvals: { total: 6, request_count: 2 },
  stock_value: "4286400",
};

export const adminSystemHealth: SystemHealth = {
  state: "healthy",
  rows: [
    { label: "Uptime this month", value: "99.6% — target 99.5% (NFR-1)" },
    { label: "Concurrent users", value: "32 of 50 — no degradation (NFR-2)" },
    { label: "Last backup", value: "Today 02:30 · point-in-time recovery (NFR-6)" },
  ],
};

export const adminIntegration: IntegrationStatus = {
  name: "Asset Maintenance (CMMS)",
  connected: true,
  api_version: "v1.4",
  last_sync: "09:42",
  events_today: 214,
  failures_today: 2,
  failure_handling: "auto-retry",
  free_connector_slots: 4,
  connector_kinds: ["ERP", "POS", "E-commerce"],
};

export const adminApprovalQueue: ApprovalQueueRow[] = [
  {
    ref: "REQ-0417",
    kind: "issuance_request",
    activity: "Issuance request · 2 lines",
    location: "WH-BLR-01",
    raised_by: "Rahul Verma",
    waiting_on: "Type 2",
  },
  {
    ref: "REQ-0416",
    kind: "issuance_request",
    activity: "Issuance request · 1 line",
    location: "WH-PUN-02",
    raised_by: "Kavita Rao",
    waiting_on: "Type 2",
  },
  {
    ref: "TRF-0092",
    kind: "transfer",
    activity: "Stock transfer · 2 lines",
    location: "BLR-01 → PUN-02",
    raised_by: "Suresh Patil",
    waiting_on: "Type 2",
  },
  {
    ref: "CAT-0113",
    kind: "taxonomy_proposal",
    activity: "Category proposal · Fasteners",
    location: "Spares",
    raised_by: "Rahul Verma",
    waiting_on: "Type 2",
  },
];

export const adminRecentAudit: ActivityEntry[] = [
  { title: "Issue · WO-2214 · −4 pcs", meta: "Suresh Patil · 09:42 · via Web" },
  { title: "GRN-2081 posted · +8 drums", meta: "Suresh Patil · 08:15 · via Web" },
  { title: "Lock created · REQ-0417 · 6 pcs", meta: "Priya Sharma · 10:12 · approval" },
  { title: "API key rotated", meta: "Arjun Mehta · 26 Sep · via Console" },
];

// ---------------------------------------------------------------------------------------- F05

export const managerSummary: ManagerSummary = {
  date_label: "Wednesday 26 Sep",
  scope_site_code: "WH-BLR-01",
  stock_value: "4286400",
  item_count: 1284,
  location_count: 4,
  low_stock_alerts: 13,
  critical_alerts: 3,
  requests_to_approve: 2,
  units_locked: "30",
  live_locks: 2,
  dead_stock_value: "320000",
};

export const managerNeedsAttention: AttentionRow[] = [
  {
    item_code: "SPB-6204",
    name: "Ball Bearing 6204-2RS",
    location: "WH-PUN-02",
    on_hand: "38",
    min: "40",
    status: { kind: "below_min", label: "Below min" },
  },
  {
    item_code: "GLV-NIT-L",
    name: "Safety Gloves Nitrile (L)",
    location: "ST-MAA-01",
    on_hand: "96",
    min: "100",
    status: { kind: "below_min", label: "Below min" },
  },
  {
    item_code: "CUT-OIL20",
    name: "Cutting Oil 20 L",
    location: "WH-BLR-01",
    on_hand: "24",
    min: "30",
    status: { kind: "batch_expiring", label: "Batch expiring" },
  },
  {
    item_code: "GRS-EP2-5",
    name: "Grease EP-2 5 kg",
    location: "WH-BLR-01",
    on_hand: "55",
    min: "20",
    status: { kind: "expiry_window", label: "Expiry 30 d" },
  },
  {
    item_code: "WEL-R7018",
    name: "Welding Electrodes E7018",
    location: "WH-BLR-01",
    on_hand: "210",
    min: null,
    status: { kind: "dead", label: "Dead 180 d" },
  },
];

export const managerWaitingOnYou: WaitingTask[] = [
  {
    task_id: "018f6f2a-3000-7000-8000-000000000417",
    ref: "REQ-0417",
    requester: "Rahul Verma",
    kind_label: "Issuance request",
    lines_summary: "2 lines · SPB-6204 ×6 (BLR free 46) · HYD hose 2 m — out of",
    state_label: "Pending",
  },
  {
    task_id: "018f6f2a-3000-7000-8000-000000000416",
    ref: "REQ-0416",
    requester: "Kavita Rao",
    kind_label: "Issuance request",
    lines_summary: "1 line · Grease EP-2 ×3 tubs (PUN free 52)",
    state_label: "Pending",
  },
];

export const managerReorderSuggestions: ReorderSuggestionRow[] = [
  {
    item_code: "SPB-6204",
    name: "Ball Bearing 6204-2RS",
    location: "WH-PUN-02",
    on_hand: "38",
    min: "40",
    lead_po_days: 3,
    lead_vendor_days: 9,
    suggested_qty: "74",
    uom: "pcs",
  },
  {
    item_code: "GLV-NIT-L",
    name: "Safety Gloves Nitrile (L)",
    location: "ST-MAA-01",
    on_hand: "96",
    min: "100",
    lead_po_days: 2,
    lead_vendor_days: 5,
    suggested_qty: "140",
    uom: "pairs",
  },
  {
    item_code: "CUT-OIL20",
    name: "Cutting Oil 20 L",
    location: "WH-BLR-01",
    on_hand: "24",
    min: "30",
    lead_po_days: 6,
    lead_vendor_days: 14,
    suggested_qty: "18",
    uom: "drums",
  },
  {
    item_code: "VBLT-A43",
    name: "V-Belt A-43",
    location: "WH-BLR-01",
    on_hand: "148",
    min: "120",
    lead_po_days: 4,
    lead_vendor_days: 6,
    suggested_qty: "60",
    uom: "pcs",
  },
];

export const managerRecentMovements: ActivityEntry[] = [
  { title: "Issue · WO-2214 · −4 pcs", meta: "Suresh Patil · 09:42 · SPB-6204" },
  { title: "GRN-2081 receipt · +8 drums", meta: "Suresh Patil · 08:15 · CUT-OIL20" },
  { title: "Lock created · REQ-0417", meta: "Priya Sharma · 10:12 · 6 pcs" },
  { title: "Ack pending · REQ-0408", meta: "Rahul Verma · 25 Sep 15:20" },
];

// ---------------------------------------------------------------------------------------- F48

export const storeSummary: StoreSummary = {
  date_label: "Wednesday 26 Sep",
  site_code: "WH-BLR-01",
  queue_count: 3,
  queue_sla: "17:00 today",
  inbound_due: [
    { po_number: "PO-2219", due: "29 Sep" },
    { po_number: "PO-2216", due: "05 Oct" },
  ],
  quarantine_open_lines: 3,
  quarantine_overdue: 1,
  counts_in_progress: 1,
  count_blind: true,
  next_pick_ref: "REQ-0417",
};

export const storeFulfilmentQueue: FulfilmentQueueRow[] = [
  {
    ref: "REQ-0417",
    requester: "Rahul Verma",
    site: "WH-BLR-01",
    lines: "1 line · 6 pcs",
    locked_ago: "10:12 today",
    sla: "Today 17:00",
    state: { kind: "ready_to_pick", label: "Ready to pick" },
  },
  {
    ref: "REQ-0413",
    requester: "Ananya Iyer",
    site: "ST-MAA-01",
    lines: "1 line · 24 pairs",
    locked_ago: "24 Sep 16:20",
    sla: "Today 17:00",
    state: { kind: "ready_to_pick", label: "Ready to pick" },
  },
  {
    ref: "REQ-0416",
    requester: "Kavita Rao",
    site: "WH-PUN-02",
    lines: "1 line · 3 tubs",
    locked_ago: "11:35 today",
    sla: "Sun 12:00",
    state: { kind: "picking", label: "Picking" },
  },
];

export const storeInbound: InboundRow[] = [
  {
    ref: "PO-2219",
    vendor_or_posted: "Chennai Lubricants",
    items_value: "CUT-OIL20 ×12 drums",
    when: "due 29 Sep",
    state: { kind: "in_transit", label: "In transit" },
  },
  {
    ref: "PO-2216",
    vendor_or_posted: "Deccan Industrial",
    items_value: "HYD-SK40 ×6 kits",
    when: "due 05 Oct",
    state: { kind: "awaiting_grn", label: "Awaiting GRN" },
  },
  {
    ref: "GRN-2081",
    vendor_or_posted: "posted · today 08:15",
    items_value: "4 lines · ₹59,300 · PO-2214",
    when: "inspection pass",
    state: { kind: "posted", label: "Posted" },
  },
];

export const storeTodayActions: ActivityEntry[] = [
  { title: "GRN-2081 posted — 4 lines · ₹59,300", meta: "08:15 · PO-2214 · inspection pass" },
  { title: "ISS-0342 scan-issued — SPB-6204 ×4", meta: "09:42 · 52 → 48 pcs · lock released" },
  { title: "REQ-0417 approved — 6 pcs locked", meta: "10:12 · Priya Sharma · Type 2 (F27)" },
  { title: "RET-0421 routed — 2 lines", meta: "11:20 · → QTN-0031 · QTN-0027 (F32)" },
];

export const storeQuarantineAging: QuarantineAgingRow[] = [
  { ref: "QTN-0029", summary: "Gloves ×6", status: { kind: "overdue", label: "Overdue 1 d · FAIL rec." } },
  { ref: "QTN-0031", summary: "Seal kit ×1", status: { kind: "due_today", label: "Due today" } },
  { ref: "QTN-0027", summary: "V-Belt ×2", status: { kind: "spec_check", label: "Spec check" } },
];

export const storeCountInProgress: CountInProgress = {
  count_no: "CC-0057",
  summary: "Aisle B · Spares · 41 SKUs · blind · variance goes to Type 2 (F17)",
};
