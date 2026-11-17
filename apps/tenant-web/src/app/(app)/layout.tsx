import { AppShell, type ShellScope } from "@ims/ui";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { NotPermitted } from "@/components/not-permitted";
import { DataSourceBanner, LicenceBanner } from "@/components/shell-banners";
import { canOpen } from "@/session/access";
import { PATH_HEADER } from "@/session/config";
import { requireSession } from "@/session/server";
import { initialsOf, menuFor, sidebarFooter } from "@/session/workspace";

/**
 * Frame for every signed-in screen: menu, scope and user come from the session. A screen whose
 * permission the person does not hold is not rendered (LLD 15, permission-aware UI); Core
 * refuses its endpoints in any case (pipeline step 8).
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await requireSession();
  const { me, workspace } = session;
  const path = (await headers()).get(PATH_HEADER) ?? "/dashboard";

  const siteOptions = me.sites.map((site) => ({ value: site.id, label: `${site.code} · ${site.name}` }));
  const scope: ShellScope = {
    ariaLabel: "Location",
    // People who work across every site start on "All locations"; others on their own site.
    // Until Core lists sites (organisation module), only "All locations" can be offered.
    options:
      me.sites.length === 1 ? siteOptions : [{ value: "all", label: "All locations" }, ...siteOptions],
    value: me.home_site_id ?? "all",
  };

  return (
    <AppShell
      nav={menuFor(workspace, me)}
      footer={sidebarFooter(me)}
      user={{ name: me.principal.display_name, role: me.role_label, initials: initialsOf(me.principal.display_name) }}
      scope={scope}
      notificationCount={me.unread_notifications}
      homeHref="/dashboard"
      banner={
        <>
          <DataSourceBanner source={session.source} />
          <LicenceBanner me={me} />
        </>
      }
    >
      {canOpen(me, workspace, path) ? children : <NotPermitted />}
    </AppShell>
  );
}
