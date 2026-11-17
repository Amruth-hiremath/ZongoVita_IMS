import { AppShell, type ShellScope } from "@ims/ui";
import type { ReactNode } from "react";

import { FixtureBanner, LicenceBanner } from "@/components/shell-banners";
import { requireSession } from "@/session/server";
import { initialsOf, menuFor, sidebarFooter } from "@/session/workspace";

/** Frame for every signed-in screen: menu, scope and user come from the session. */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await requireSession();
  const { me, workspace } = session;

  const siteOptions = me.sites.map((site) => ({ value: site.id, label: `${site.code} · ${site.name}` }));
  const scope: ShellScope = {
    ariaLabel: "Location",
    // People who work across every site start on "All locations"; others on their own site.
    options: me.sites.length > 1 ? [{ value: "all", label: "All locations" }, ...siteOptions] : siteOptions,
    value: me.home_site_id ?? "all",
  };

  return (
    <AppShell
      nav={menuFor(workspace)}
      footer={sidebarFooter(me)}
      user={{ name: me.principal.display_name, role: me.role_label, initials: initialsOf(me.principal.display_name) }}
      scope={scope}
      notificationCount={me.unread_notifications}
      homeHref="/dashboard"
      banner={
        <>
          {session.source === "fixture" ? <FixtureBanner /> : null}
          <LicenceBanner me={me} />
        </>
      }
    >
      {children}
    </AppShell>
  );
}
