import { AppShell } from "@ims/ui";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { DataSourceBanner } from "@/components/data-source-banner";
import { NotPermitted } from "@/components/not-permitted";
import { getEnterpriseOptions } from "@/data/enterprises";
import { canOpen, menuFor } from "@/session/access";
import { PATH_HEADER } from "@/session/config";
import { requireStaff } from "@/session/server";

/**
 * Frame for every console screen: menu, enterprise selector and user come from the staff session.
 * A screen the person may not open is not rendered; the Platform Service refuses its endpoints
 * in any case.
 */
export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  const staff = await requireStaff();
  const path = (await headers()).get(PATH_HEADER) ?? "/overview";
  const enterprises = staff.role === "system_admin" ? await getEnterpriseOptions() : [];

  return (
    <AppShell
      nav={menuFor(staff.role)}
      footer={`Platform · ${staff.name}`}
      user={{ name: staff.name, role: staff.role_label, initials: staff.initials }}
      scope={{
        ariaLabel: "Enterprise",
        value: "all",
        options: [
          { value: "all", label: "All enterprises" },
          ...enterprises.map((enterprise) => ({ value: enterprise.code, label: `${enterprise.code} · ${enterprise.name}` })),
        ],
      }}
      notificationCount={staff.unread_notifications}
      homeHref="/overview"
      banner={<DataSourceBanner source={staff.source} />}
    >
      {canOpen(staff.role, path) ? children : <NotPermitted />}
    </AppShell>
  );
}
