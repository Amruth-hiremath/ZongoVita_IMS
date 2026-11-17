/** FIXTURE: sample rows from wireframe F22. Temporary; see src/data/source.ts. */
import type { UserList, UserRole, UserRow } from "@/data/users";

const TYPE_1: UserRole = { name: "Type 1", kind: "super_admin" };
const TYPE_2: UserRole = { name: "Type 2", kind: "approver" };
const TYPE_3_STORE: UserRole = { name: "Type 3 · Store", kind: "store_keeper" };
const TYPE_3: UserRole = { name: "Type 3", kind: "standard" };
const PURCHASING: UserRole = { name: "Purchasing", kind: "custom" };
const FINANCE: UserRole = { name: "Finance", kind: "custom" };

function user(id: string, display_name: string, email: string, role: UserRole, scope_label: string): UserRow {
  return { id, display_name, email, role, scope_label, last_active: "today", status: "active" };
}

export const userList: UserList = {
  rows: [
    user("018f6f2a-1000-7000-8000-00000000a001", "Arjun Mehta", "arjun.mehta@zongovita.in", TYPE_1, "All locations"),
    user("018f6f2a-1000-7000-8000-00000000a002", "Priya Sharma", "priya.sharma@zongovita.in", TYPE_2, "All locations"),
    user("018f6f2a-1000-7000-8000-00000000a003", "Suresh Patil", "suresh.patil@zongovita.in", TYPE_3_STORE, "WH-BLR-01"),
    user("018f6f2a-1000-7000-8000-00000000a004", "Rahul Verma", "rahul.verma@zongovita.in", TYPE_3, "WH-BLR-01"),
    user("018f6f2a-1000-7000-8000-00000000a005", "Ananya Iyer", "ananya.iyer@zongovita.in", TYPE_3, "ST-MAA-01"),
    user("018f6f2a-1000-7000-8000-00000000a006", "Kavita Rao", "kavita.rao@zongovita.in", TYPE_3, "WH-PUN-02"),
    user("018f6f2a-1000-7000-8000-00000000a007", "Vikram Singh", "vikram.singh@zongovita.in", PURCHASING, "— custom —"),
    user("018f6f2a-1000-7000-8000-00000000a008", "Deepa Nair", "deepa.nair@zongovita.in", FINANCE, "— custom —"),
  ],
  remaining: {
    count: 10,
    site_codes: ["BLR-01", "PUN-02", "MAA-01"],
    role_label: "Type 3/4",
    scope_label: "per location",
  },
};
