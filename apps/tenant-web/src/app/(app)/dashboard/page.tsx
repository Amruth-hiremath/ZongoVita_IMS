import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";
import { requireSession } from "@/session/server";

import { AdminDashboard } from "./admin-dashboard";
import { ManagerDashboard } from "./manager-dashboard";
import { StoreDashboard } from "./store-dashboard";

export const metadata: Metadata = { title: "Dashboard" };

/** /dashboard: F04 (admin), F05 (manager) or F48 (store), by the signed-in person's workspace. */
export default async function DashboardPage() {
  const { me, workspace } = await requireSession();

  switch (workspace) {
    case "admin":
      return <AdminDashboard me={me} />;
    case "manager":
      return <ManagerDashboard me={me} />;
    case "store":
      return <StoreDashboard me={me} />;
    case "requester":
      return (
        <NoScreen title="Dashboard">
          The wireframes draw dashboards for User Types 1, 2 and 3 only. There is no frame for a requester (User Type 4).
        </NoScreen>
      );
  }
}
