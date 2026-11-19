import type { StaffRole } from "@ims/api-client";
import type { NavItem } from "@ims/ui";

/**
 * Which console screens a staff member may open: the menu and the layout's guard both read this.
 *
 * HLD section 3: the ZongoVita system admin manages customers, licences and licence state,
 * provisioning and migrations from the Platform Console; the support engineer has no standing
 * access and works only through customer-approved support grants (AD-83), whose console flow
 * arrives with the support-access unit. The Platform Service refuses every administration
 * endpoint to anyone but a system admin in any case; this only keeps the screens consistent.
 */
interface Screen extends NavItem {
  roles: readonly StaffRole[];
}

const SYSTEM_ADMIN_ONLY: readonly StaffRole[] = ["system_admin"];

/** Sidebar of the Platform Console as drawn in F51 to F53. */
const SCREENS: Screen[] = [
  { label: "Overview", href: "/overview", icon: "dashboard", roles: SYSTEM_ADMIN_ONLY },
  { label: "Enterprises", href: "/enterprises", icon: "vendors", roles: SYSTEM_ADMIN_ONLY },
  { label: "Licenses", href: "/licenses", icon: "privileges", roles: SYSTEM_ADMIN_ONLY },
  { label: "Platform Config", href: "/config", icon: "settings", roles: SYSTEM_ADMIN_ONLY },
  { label: "Audit Trail", href: "/audit", icon: "audit", roles: SYSTEM_ADMIN_ONLY },
];

export function menuFor(role: StaffRole): NavItem[] {
  return SCREENS.filter((screen) => screen.roles.includes(role)).map(({ label, href, icon }) => ({ label, href, icon }));
}

export function canOpen(role: StaffRole, path: string): boolean {
  const screen = SCREENS.find((entry) => path === entry.href || path.startsWith(`${entry.href}/`));
  return screen !== undefined && screen.roles.includes(role);
}
