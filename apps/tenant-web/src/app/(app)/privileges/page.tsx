import { hasPermission } from "@ims/api-client";
import type { Metadata } from "next";

import { getPrivilegeMatrix } from "@/data/privileges";
import { requireSession } from "@/session/server";

import { PrivilegeEditor } from "./privilege-editor";

export const metadata: Metadata = { title: "Privilege Matrix" };

/** F36 Privilege Matrix. */
export default async function PrivilegesPage() {
  const [{ me }, matrix] = await Promise.all([requireSession(), getPrivilegeMatrix()]);
  return <PrivilegeEditor matrix={matrix} canEdit={hasPermission(me, "access.role.manage")} />;
}
