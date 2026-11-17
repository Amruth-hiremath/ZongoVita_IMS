import "server-only";

import type { PermissionCode } from "@ims/api-client";

import { userList } from "@/fixtures/users";
import { formatDay } from "@/lib/dates";

import { getPrivilegeMatrix, type MatrixRole } from "./privileges";
import { fromCore } from "./source";

/**
 * How a role is drawn in the user list: the super admin, the seeded approving and store types,
 * the other seeded types, and custom roles.
 */
export type RoleKind = "super_admin" | "approver" | "store_keeper" | "standard" | "custom";

export interface UserRole {
  /** "Type 1", "Type 2 · Auditor", "Purchasing". */
  name: string;
  kind: RoleKind;
}

export interface UserRow {
  id: string;
  display_name: string;
  email: string | null;
  role: UserRole | null;
  /** "All locations", "2 sites", "WH-BLR-01". */
  scope_label: string;
  /** "today", "12 Nov 2026", "never". */
  last_active: string;
  status: "active" | "invited" | "inactive";
}

export interface UserList {
  rows: UserRow[];
  /** Users beyond this page, summarised as the last row of the frame (sample data only). */
  remaining: { count: number; site_codes: string[]; role_label: string; scope_label: string } | null;
}

/** Core's UserOut (services/core/ims_core/modules/access/schemas.py). */
interface CoreAssignment {
  role_name: string;
  role_code: string;
  user_type_no: number | null;
  site_id: string | null;
  super_admin: boolean;
}
interface CoreUser {
  id: string;
  display_name: string;
  email: string | null;
  status: "invited" | "active" | "suspended" | "deactivated";
  is_super_admin: boolean;
  assignments: CoreAssignment[];
  last_active_at: string | null;
}

function roleOf(user: CoreUser): UserRole | null {
  const types = [...new Set(user.assignments.flatMap((a) => (a.user_type_no ? [a.user_type_no] : [])))].sort();
  const custom = [
    ...new Set(user.assignments.filter((a) => a.user_type_no === null && !a.super_admin).map((a) => a.role_name)),
  ].sort();
  const parts = [...types.map((n) => `Type ${n}`), ...custom];
  if (parts.length === 0) return user.is_super_admin ? { name: "Super Admin", kind: "super_admin" } : null;
  const kind: RoleKind = user.is_super_admin
    ? "super_admin"
    : types.length === 0
      ? "custom"
      : types[0] === 2
        ? "approver"
        : types[0] === 3
          ? "store_keeper"
          : "standard";
  return { name: parts.join(" · "), kind };
}

function scopeOf(user: CoreUser): string {
  const ordinary = user.assignments.filter((a) => !a.super_admin);
  if (user.is_super_admin || ordinary.some((a) => a.site_id === null)) return "All locations";
  const sites = new Set(ordinary.map((a) => a.site_id));
  // Site codes come with the organisation module (unit 4); until then the count is shown.
  if (sites.size === 0) return "—";
  return sites.size === 1 ? "1 site" : `${sites.size} sites`;
}

function lastActive(at: string | null, now = new Date()): string {
  if (!at) return "never";
  const day = formatDay(at);
  return day === formatDay(now.toISOString()) ? "today" : day;
}

/** F22 user list. */
export function listUsers(): Promise<UserList> {
  return fromCore<{ items: CoreUser[]; next_cursor: string | null }, UserList>(
    {
      endpoint: "GET /ui/v1/users",
      note: "Rows show role assignments (user types, custom roles, site scope), last activity (latest session refresh) and status. Site codes need the organisation module (unit 4).",
    },
    "/users?limit=200",
    (page) => ({
      rows: page.items.map((user) => ({
        id: user.id,
        display_name: user.display_name,
        email: user.email,
        role: roleOf(user),
        scope_label: scopeOf(user),
        last_active: lastActive(user.last_active_at),
        status: user.status === "active" ? "active" : user.status === "invited" ? "invited" : "inactive",
      })),
      remaining: null,
    }),
    () => userList,
  );
}

export type Granted = "yes" | "partly" | "no";

export interface CapabilitySummaryRow {
  capability: string;
  /** Per seeded user type, Type 1 to Type 4 in order. */
  granted: [Granted, Granted, Granted, Granted];
  /** The permissions the capability stands for (LLD section 7). */
  applies_to: string;
}

/**
 * The capabilities F22 draws, each read as the LLD permissions it names. "Yes" when the type
 * holds all of them, "Partly" when some (decision recorded in Docs/UI_Implementation.md 10).
 */
const CAPABILITIES: { capability: string; codes: PermissionCode[] }[] = [
  { capability: "Generate SKUs (Q6)", codes: ["catalog.numbering.manage"] },
  { capability: "Create / configure items", codes: ["catalog.item.create", "catalog.item.edit", "catalog.attribute.manage"] },
  { capability: "Receive / issue / return stock", codes: ["receiving.grn.create", "issuance.issue.fulfil", "returns.return.receive"] },
  { capability: "Approve requests · locks stock", codes: ["issuance.request.approve"] },
  { capability: "Manage categories", codes: ["catalog.taxonomy.approve"] },
  { capability: "Manage vendors & purchase recs", codes: ["purchasing.vendor.manage", "purchasing.record.manage"] },
  { capability: "Manage users & privileges", codes: ["access.user.manage", "access.role.manage"] },
];

function summarise(roles: MatrixRole[]): CapabilitySummaryRow[] {
  const types = [1, 2, 3, 4].map((n) => roles.find((role) => role.user_type_no === n));
  return CAPABILITIES.map(({ capability, codes }) => ({
    capability,
    granted: types.map((role): Granted => {
      const held = codes.filter((code) => role?.permissions.includes(code)).length;
      return held === codes.length ? "yes" : held > 0 ? "partly" : "no";
    }) as CapabilitySummaryRow["granted"],
    applies_to: codes.join(", "),
  }));
}

/** F22 "Permission matrix by user type": the read-only summary that F36 edits. */
export async function getCapabilitySummary(): Promise<CapabilitySummaryRow[]> {
  return summarise((await getPrivilegeMatrix()).roles);
}
