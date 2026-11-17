import { hasPermission, type Me } from "@ims/api-client";
import type { NavItem } from "@ims/ui";

import { canOpen } from "./access";

/**
 * The wireframes draw three sets of screens, labelled Type 1, Type 2 and Type 3. The LLD makes
 * workflow actors privileges, not fixed roles (HLD section 3; LLD 15 "permission-aware UI"),
 * so which set a person sees is derived from effective permissions, not from a role name:
 *
 *   admin      can manage users                    (seeded: Super Admin, User Type 1)
 *   manager    can approve issuance requests       (seeded: User Type 2)
 *   store      can fulfil issues                   (seeded: User Type 3)
 *   requester  none of the above                   (seeded: User Type 4; no wireframes exist)
 */
export type Workspace = "admin" | "manager" | "store" | "requester";

export function resolveWorkspace(me: Me): Workspace {
  if (hasPermission(me, "access.user.manage")) return "admin";
  if (hasPermission(me, "issuance.request.approve")) return "manager";
  if (hasPermission(me, "issuance.issue.fulfil")) return "store";
  return "requester";
}

/** Sidebar menus exactly as drawn: labels, order and icons per workspace. */
const menus: Record<Workspace, NavItem[]> = {
  admin: [
    { label: "Dashboard", href: "/dashboard", icon: "dashboard" },
    { label: "Items & Catalog", href: "/items", icon: "items" },
    { label: "Categories", href: "/categories", icon: "categories" },
    { label: "Vendors & Purchases", href: "/vendors", icon: "vendors", match: ["/purchase-records"] },
    { label: "Quality Register", href: "/quality-register", icon: "quality" },
    { label: "Locations", href: "/locations", icon: "locations" },
    { label: "Users & Types", href: "/users", icon: "users" },
    { label: "Privileges", href: "/privileges", icon: "privileges" },
    { label: "Approvals", href: "/approvals/configuration", icon: "approvals", match: ["/approvals"] },
    { label: "Audit Trail", href: "/audit", icon: "audit" },
    { label: "Settings", href: "/settings", icon: "settings" },
  ],
  manager: [
    { label: "Dashboard", href: "/dashboard", icon: "dashboard" },
    { label: "Items", href: "/items", icon: "items" },
    { label: "Receive", href: "/receive", icon: "receive" },
    { label: "Issuance", href: "/issuance", icon: "issuance" },
    { label: "Approvals", href: "/approvals", icon: "approvals" },
    { label: "Returns", href: "/returns", icon: "returns" },
    { label: "Transfers", href: "/transfers", icon: "transfers" },
    { label: "Stock Counts", href: "/stock-counts", icon: "counts" },
    { label: "Alerts & Reorder", href: "/alerts", icon: "alerts" },
    { label: "Reports", href: "/reports", icon: "reports" },
    { label: "Audit Trail", href: "/audit", icon: "audit" },
  ],
  store: [
    { label: "Dashboard", href: "/dashboard", icon: "dashboard" },
    { label: "Fulfilment Queue", href: "/fulfilment", icon: "fulfilment" },
    { label: "Scan & Issue", href: "/scan-issue", icon: "scan" },
    { label: "Receive", href: "/receive", icon: "receive" },
    { label: "Quarantine", href: "/quarantine", icon: "quarantine" },
    { label: "Returns", href: "/returns", icon: "returns" },
    { label: "Counts", href: "/stock-counts", icon: "counts" },
    { label: "Transfers", href: "/transfers", icon: "transfers" },
    { label: "Audit Trail", href: "/audit", icon: "audit" },
  ],
  requester: [{ label: "Dashboard", href: "/dashboard", icon: "dashboard" }],
};

/**
 * The workspace's menu as drawn, without the entries whose screens the person may not open
 * (src/session/access.ts). The LLD's effective permissions decide; the drawing gives the order,
 * labels and icons.
 */
export function menuFor(workspace: Workspace, me: Me): NavItem[] {
  return menus[workspace].filter((item) => canOpen(me, workspace, item.href));
}

/** "TYPE 1 · ARJUN MEHTA": the small-caps line at the foot of the sidebar. */
export function sidebarFooter(me: Me): string {
  const type = me.user_type_no ? `Type ${me.user_type_no}` : "Custom role";
  return `${type} · ${me.principal.display_name}`;
}

export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
