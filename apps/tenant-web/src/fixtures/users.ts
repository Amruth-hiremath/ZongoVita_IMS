/** FIXTURE: sample rows from wireframe F22. Temporary; see src/data/source.ts. */
import type { CapabilitySummaryRow, UserList, UserRole, UserRow } from "@/data/users";

const TYPE_1: UserRole = { role_id: "role-type-1", name: "Type 1", kind: "super_admin", user_type_no: 1 };
const TYPE_2: UserRole = { role_id: "role-type-2", name: "Type 2", kind: "approver", user_type_no: 2 };
const TYPE_3_STORE: UserRole = { role_id: "role-type-3-store", name: "Type 3 · Store", kind: "store_keeper", user_type_no: 3 };
const TYPE_3: UserRole = { role_id: "role-type-3", name: "Type 3", kind: "standard", user_type_no: 3 };
const PURCHASING: UserRole = { role_id: "role-purchasing", name: "Purchasing", kind: "custom", user_type_no: null };
const FINANCE: UserRole = { role_id: "role-finance", name: "Finance", kind: "custom", user_type_no: null };

function user(
  id: string,
  display_name: string,
  email: string,
  role: UserRole,
  site_codes: string[] | null,
  custom_scope = false,
): UserRow {
  return { id, display_name, email, role, site_codes, custom_scope, last_active: "today", status: "active" };
}

export const userList: UserList = {
  rows: [
    user("018f6f2a-1000-7000-8000-00000000a001", "Arjun Mehta", "arjun.mehta@zongovita.in", TYPE_1, null),
    user("018f6f2a-1000-7000-8000-00000000a002", "Priya Sharma", "priya.sharma@zongovita.in", TYPE_2, null),
    user("018f6f2a-1000-7000-8000-00000000a003", "Suresh Patil", "suresh.patil@zongovita.in", TYPE_3_STORE, ["WH-BLR-01"]),
    user("018f6f2a-1000-7000-8000-00000000a004", "Rahul Verma", "rahul.verma@zongovita.in", TYPE_3, ["WH-BLR-01"]),
    user("018f6f2a-1000-7000-8000-00000000a005", "Ananya Iyer", "ananya.iyer@zongovita.in", TYPE_3, ["ST-MAA-01"]),
    user("018f6f2a-1000-7000-8000-00000000a006", "Kavita Rao", "kavita.rao@zongovita.in", TYPE_3, ["WH-PUN-02"]),
    user("018f6f2a-1000-7000-8000-00000000a007", "Vikram Singh", "vikram.singh@zongovita.in", PURCHASING, null, true),
    user("018f6f2a-1000-7000-8000-00000000a008", "Deepa Nair", "deepa.nair@zongovita.in", FINANCE, null, true),
  ],
  remaining: {
    count: 10,
    site_codes: ["BLR-01", "PUN-02", "MAA-01"],
    role_label: "Type 3/4",
    scope_label: "per location",
  },
};

export const capabilitySummary: CapabilitySummaryRow[] = [
  { capability: "Generate SKUs (Q6)", granted: [true, false, false, false], applies_to: "Type 1 only per Q6." },
  { capability: "Create / configure items", granted: [true, true, false, false], applies_to: "Attributes configurable (Q5)." },
  { capability: "Receive / issue / return stock", granted: [true, true, true, false], applies_to: "Type 3: own location." },
  { capability: "Approve requests · locks stock", granted: [true, true, false, false], applies_to: "First approval locks (FB-09)." },
  { capability: "Manage categories", granted: [true, false, false, false], applies_to: "Proposals + dedupe (F25)." },
  { capability: "Manage vendors & purchase recs", granted: [true, false, false, false], applies_to: "Vendor master (F37 · F40)." },
  { capability: "Manage users & privileges", granted: [true, false, false, false], applies_to: "IAM-style engine (F36)." },
];
