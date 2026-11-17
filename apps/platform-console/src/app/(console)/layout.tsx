import { AppShell, type NavItem } from "@ims/ui";
import type { ReactNode } from "react";

import { getStaffSession } from "@/data/session";

/** Sidebar of the Platform Console as drawn in F51 to F53. */
const menu: NavItem[] = [
  { label: "Overview", href: "/overview", icon: "dashboard" },
  { label: "Enterprises", href: "/enterprises", icon: "vendors" },
  { label: "Licenses", href: "/licenses", icon: "privileges" },
  { label: "Platform Config", href: "/config", icon: "settings" },
  { label: "Audit Trail", href: "/audit", icon: "audit" },
];

export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  const staff = await getStaffSession();
  return (
    <AppShell
      nav={menu}
      footer={`Platform · ${staff.name}`}
      user={{ name: staff.name, role: staff.role, initials: staff.initials }}
      scope={{
        ariaLabel: "Enterprise",
        value: "all",
        options: [
          { value: "all", label: "All enterprises" },
          ...staff.enterprises.map((enterprise) => ({ value: enterprise.code, label: `${enterprise.code} · ${enterprise.name}` })),
        ],
      }}
      notificationCount={staff.unread_notifications}
      homeHref="/overview"
      banner={
        <div className="flex h-6 items-center justify-center bg-gray-50 text-[10.5px] tracking-wide text-gray-500">
          Sample data from the wireframes · screens are not connected to the Platform Service yet
        </div>
      }
    >
      {children}
    </AppShell>
  );
}
