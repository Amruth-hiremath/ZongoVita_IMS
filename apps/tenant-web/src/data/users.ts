import "server-only";

import { capabilitySummary, userList } from "@/fixtures/users";

import { fromFixture } from "./source";

/**
 * How a role is drawn in the user list: the super-admin type, the seeded approving and store
 * types, the other seeded types, and custom roles cloned from a type (F36 "Purchasing").
 */
export type RoleKind = "super_admin" | "approver" | "store_keeper" | "standard" | "custom";

export interface UserRole {
  role_id: string;
  /** "Type 1", "Type 3 · Store", "Purchasing". */
  name: string;
  kind: RoleKind;
  /** Seeded user type 1 to 4; null for a custom role. */
  user_type_no: 1 | 2 | 3 | 4 | null;
}

export interface UserRow {
  id: string;
  display_name: string;
  email: string;
  role: UserRole;
  /** Location codes the role assignment covers; null means every location. */
  site_codes: string[] | null;
  /** True when the role assignment carries a custom scope rather than a site list. */
  custom_scope: boolean;
  /** Display string as drawn ("today"); a real timestamp once Core records sessions. */
  last_active: string;
  status: "active" | "inactive";
}

export interface UserList {
  rows: UserRow[];
  /** Users beyond this page, summarised as the last row of the frame. */
  remaining: { count: number; site_codes: string[]; role_label: string; scope_label: string } | null;
}

/** F22 user list. */
export function listUsers(): Promise<UserList> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/users",
      note: "Rows need the user's role assignment (role name, user type, site scope), last activity and status; the tail of the list is summarised by count and sites.",
    },
    userList,
  );
}

export interface CapabilitySummaryRow {
  capability: string;
  /** Granted per seeded user type, Type 1 to Type 4 in order. */
  granted: [boolean, boolean, boolean, boolean];
  applies_to: string;
}

/** F22 "Permission matrix by user type": the read-only summary that F36 edits. */
export function getCapabilitySummary(): Promise<CapabilitySummaryRow[]> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/privilege-matrix",
      note: "The summary groups permissions into capabilities with a short scope note; the grouping is not in the LLD permission catalogue.",
    },
    capabilitySummary,
  );
}
