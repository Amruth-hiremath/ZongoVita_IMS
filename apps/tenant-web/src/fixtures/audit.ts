/** FIXTURE: sample audit entries from wireframes F24 (two versions) and F50. Temporary; see src/data/source.ts. */
import type {
  AuditChange,
  AuditEntry,
  AuditSource,
  AuditTrailPage,
  StoreActionKind,
  StoreAuditEntry,
  StoreAuditPage,
} from "@/data/audit";

const MONTHS: Record<string, string> = { Sep: "09" };

/** "26 Sep 09:42:07" (IST, as drawn) -> ISO 8601 UTC. */
function isoFromLabel(label: string): string {
  const [day, month, time] = label.split(" ");
  return new Date(`2026-${MONTHS[month ?? ""]}-${(day ?? "").padStart(2, "0")}T${time}+05:30`).toISOString();
}

const qty = (from: string, to: string, uom: string): AuditChange => ({ kind: "quantity", from, to, uom });
const good = (text: string): AuditChange => ({ kind: "outcome", tone: "good", text });
const bad = (text: string): AuditChange => ({ kind: "outcome", tone: "bad", text });
const plain = (text: string): AuditChange => ({ kind: "outcome", tone: "plain", text });

function entry(
  id: string,
  at: string,
  actor: [name: string, tag: string, userType: string],
  action: string,
  module: string,
  entity: string,
  change: AuditChange,
  source: AuditSource,
): AuditEntry {
  return {
    id,
    occurred_at: isoFromLabel(at),
    occurred_at_label: at,
    actor_name: actor[0],
    actor_tag: actor[1],
    actor_user_type: actor[2],
    action,
    module,
    entity,
    change,
    source,
    location_code: "WH-BLR-01",
  };
}

const LOCATIONS = ["WH-BLR-01", "WH-PUN-02", "ST-MAA-01", "WH-HYD-03"];
const SOURCES: AuditSource[] = ["Web", "Mobile", "API", "Connector"];

// F24-Audit-Trail-v1 (Arjun Mehta, Type 1).
const RAHUL: [string, string, string] = ["Rahul Verma", "S", "Type 3"];
const PRIYA_M: [string, string, string] = ["Priya Sharma", "M", "Type 2"];

export const adminAuditPage: AuditTrailPage = {
  rows: [
    entry("a1", "26 Sep 09:42:07", RAHUL, "Issue", "Issuance", "ISS-0342 · SPB-6204", qty("52", "48", "pcs"), "Web"),
    entry("a2", "26 Sep 09:41:58", ["Kavita Rao", "S", "Type 3"], "Issue (rejected)", "Issuance", "ISS-0341 · SPB-6204", bad("first-write-wins"), "Web"),
    entry("a3", "26 Sep 09:41:52", ["System", "connector", "System"], "Sync consume", "Integrations", "WO-2214 · SPB-6204", qty("42", "38", "pcs"), "API"),
    entry("a4", "26 Sep 08:15:20", RAHUL, "Receipt", "Receiving", "GRN-2081 · CUT-OIL20", qty("16", "24", "drum"), "Web"),
    entry("a5", "25 Sep 17:30:44", RAHUL, "Transfer dispatch", "Transfers", "TRF-0092 · 2 lines", qty("52", "32", "pcs"), "Web"),
    entry("a6", "25 Sep 15:44:10", PRIYA_M, "Approval", "Approvals", "TRF-0092", good("approved"), "Web"),
    entry("a7", "25 Sep 14:02:31", RAHUL, "Transfer request", "Transfers", "TRF-0092", plain("created"), "Mobile"),
    entry("a8", "25 Sep 11:05:09", PRIYA_M, "Adjustment", "Counts & adjustments", "ADJ-0218 · SPB-6204", qty("46", "43", "pcs"), "Web"),
  ],
  total: 148203,
  sorted_by: "newest first",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  from_label: "26 Sep 2026",
  filters: {
    users: ["Rahul Verma", "Kavita Rao", "Priya Sharma", "System"],
    user_types: ["Type 1", "Type 2", "Type 3", "System"],
    modules: ["Issuance", "Receiving", "Transfers", "Approvals", "Counts & adjustments", "Quality", "Integrations"],
    locations: LOCATIONS,
    sources: SOURCES,
  },
};

// F24-Audit-Trail (Priya Sharma, User Type 2).
const SURESH: [string, string, string] = ["Suresh Patil", "T3", "Type 3"];
const PRIYA_T2: [string, string, string] = ["Priya Sharma", "T2", "Type 2"];
const KAVITA: [string, string, string] = ["Kavita Rao", "T3", "Type 3"];
const QUALITY: [string, string, string] = ["System", "quality", "System"];

export const managerAuditPage: AuditTrailPage = {
  rows: [
    entry("m1", "26 Sep 10:12:04", PRIYA_T2, "Approval", "Approvals", "REQ-0417 · 6 pcs", good("approved · locked"), "Web"),
    entry("m2", "26 Sep 09:42:07", SURESH, "Issue", "Issuance", "ISS-0342 · SPB-6204", qty("52", "48", "pcs"), "Web"),
    entry("m3", "26 Sep 09:41:58", KAVITA, "Issue (rejected)", "Issuance", "ISS-0341 · SPB-6204", bad("first-write-wins"), "Web"),
    entry("m4", "26 Sep 08:15:20", SURESH, "Receipt", "Receiving", "GRN-2081 · CUT-OIL20", qty("16", "24", "drum"), "Web"),
    entry("m5", "26 Sep 08:02:11", QUALITY, "Quality event", "Quality", "EF-0041 · SafeGuard", plain("published"), "Web"),
    entry("m6", "25 Sep 17:30:44", SURESH, "Transfer dispatch", "Transfers", "TRF-0092 · 2 lines", qty("52", "32", "pcs"), "Web"),
    entry("m7", "25 Sep 15:44:10", PRIYA_T2, "Approval", "Approvals", "TRF-0092", good("approved"), "Web"),
    entry("m8", "25 Sep 14:02:31", SURESH, "Transfer request", "Transfers", "TRF-0092", plain("created"), "Mobile"),
  ],
  total: 148203,
  sorted_by: "newest first",
  pages: [1, 2, "…", 9, 10],
  page: 1,
  from_label: "26 Sep 2026",
  filters: {
    users: ["Priya Sharma", "Suresh Patil", "Kavita Rao", "System"],
    user_types: ["Type 2", "Type 3", "System"],
    modules: ["Issuance", "Receiving", "Transfers", "Approvals", "Quality"],
    locations: LOCATIONS,
    sources: SOURCES,
  },
};

// F50-Store-Audit-Type-3 (Suresh Patil, User Type 3 · Store, WH-BLR-01 only).
function storeEntry(kind: StoreActionKind, base: AuditEntry): StoreAuditEntry {
  return { ...base, action_kind: kind };
}

export const storeAuditPage: StoreAuditPage = {
  site_code: "WH-BLR-01",
  rows: [
    storeEntry("quarantine", entry("s1", "26 Sep 11:20:33", SURESH, "Quarantine", "Returns", "RET-0421 · 2 lines", plain("routed · 2 lines"), "Web")),
    storeEntry("approval", entry("s2", "26 Sep 10:12:04", PRIYA_T2, "Approval", "Approvals", "REQ-0417 · 6 pcs", good("approved · locked"), "Web")),
    storeEntry("issue", entry("s3", "26 Sep 09:42:07", SURESH, "Issue", "Issuance", "ISS-0342 · SPB-6204", qty("52", "48", "pcs"), "Web")),
    storeEntry("issue", entry("s4", "26 Sep 09:41:58", KAVITA, "Rejected", "Issuance", "ISS-0341 · SPB-6204", bad("first-write-wins"), "Web")),
    storeEntry("receipt", entry("s5", "26 Sep 08:15:20", SURESH, "Receipt", "Receiving", "GRN-2081 · CUT-OIL20", qty("16", "24", "drum"), "Web")),
    storeEntry("quality", entry("s6", "26 Sep 08:02:11", QUALITY, "Quality", "Quality", "EF-0041 · SafeGuard", plain("published"), "Web")),
    storeEntry("transfer", entry("s7", "25 Sep 17:30:44", SURESH, "Transfer", "Transfers", "TRF-0092 · 2 lines", qty("52", "32", "pcs"), "Web")),
    storeEntry("issue", entry("s8", "25 Sep 15:20:10", SURESH, "Issue", "Issuance", "REQ-0408 · SPB-6204", plain("to Rahul Verma"), "Web")),
  ],
  months: [
    { value: "2026-09", label: "Sep 2026" },
    { value: "2026-08", label: "Aug 2026" },
    { value: "2026-07", label: "Jul 2026" },
  ],
  period_label: "yesterday + today",
};
