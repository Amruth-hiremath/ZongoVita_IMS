import { hasPermission, type PermissionCode } from "@ims/api-client";
import type { Metadata } from "next";

import { NotPermitted } from "@/components/not-permitted";
import { getPrivilegeMatrix } from "@/data/privileges";
import { canOpen } from "@/session/access";
import { requireSession } from "@/session/server";

import { PrivilegeEditor } from "./privilege-editor";

export const metadata: Metadata = { title: "Privilege Matrix" };

/** F36 Privilege Matrix. */
export default async function PrivilegesPage() {
  // Session and permission first: the layout's guard renders in parallel with this page.
  const { me, workspace } = await requireSession();
  if (!canOpen(me, workspace, "/privileges")) return <NotPermitted />;
  const matrix = await getPrivilegeMatrix();
  // No self-escalation (LLD 7): a role can be assigned anywhere, so a permission can only be
  // added by someone who holds it at every site.
  const heldEverywhere = me.permissions.filter((p) => p.site_ids === null).map((p) => p.code as PermissionCode);
  return (
    <PrivilegeEditor matrix={matrix} canEdit={hasPermission(me, "access.role.manage")} heldEverywhere={heldEverywhere} />
  );
}
