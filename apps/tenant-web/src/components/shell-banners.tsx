import type { Me } from "@ims/api-client";

import { formatDay } from "@/lib/dates";

/**
 * Thin strip above the top bar saying where the screens' data comes from. Signed in to Core,
 * the session, the menu, the location selector, Locations, Users and Privileges are live; other
 * screens still show the
 * wireframes' sample data until their Core modules exist (Docs/UI_Implementation.md section 7).
 */
export function DataSourceBanner({ source }: { source: "core" | "fixtures" }) {
  return (
    <div className="flex h-6 items-center justify-center bg-gray-50 px-4 text-center text-[10.5px] tracking-wide text-gray-500">
      {source === "core"
        ? "Signed in to IMS Core · Locations, Users and Privileges are live; other screens show sample data from the wireframes"
        : "Sample data from the wireframes · screens are not connected to IMS Core yet"}
    </div>
  );
}

/**
 * Licence banners (LLD 15): grace shows the end date to the super admin; read-only shows a
 * banner to every user. Suspended and terminated customers cannot sign in at all.
 */
export function LicenceBanner({ me }: { me: Me }) {
  const { state, grace_ends_at: graceEndsAt } = me.licence;
  if (state === "grace" && me.is_super_admin) {
    const until = graceEndsAt ? formatDay(graceEndsAt) : null;
    return (
      <div role="status" className="flex h-8 items-center justify-center border-b border-amber-200 bg-amber-50 text-[12px] text-amber-700">
        Your licence has expired. Full access continues during the grace period{until ? ` until ${until}` : ""}; renew to avoid read-only mode.
      </div>
    );
  }
  if (state === "read_only") {
    return (
      <div role="alert" className="flex h-8 items-center justify-center border-b border-red-200 bg-red-50 text-[12px] text-red-700">
        The licence is in read-only state. Records can be viewed; changes are disabled except emergency stock issue.
      </div>
    );
  }
  return null;
}
