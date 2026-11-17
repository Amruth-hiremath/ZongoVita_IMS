import { hasPermission } from "@ims/api-client";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { NoScreen } from "@/components/no-screen";
import { getApprovalWorkspace } from "@/data/approvals";
import { requireSession } from "@/session/server";

import { ApprovalWorkspace } from "./approval-workspace";

export const metadata: Metadata = { title: "Approval Workspace" };

/**
 * Approvals. Manager workspace: F27 Approval Workspace. Admin workspace: the menu entry leads to
 * F23 Approval Workflow Configuration. No frame exists for the other workspaces.
 */
export default async function ApprovalsPage() {
  const { me, workspace } = await requireSession();

  if (workspace === "admin") redirect("/approvals/configuration");
  if (workspace !== "manager") {
    return (
      <NoScreen title="Approvals">
        The wireframes draw the approval workspace for approvers only; there is no approvals screen for this user type.
      </NoScreen>
    );
  }

  const data = await getApprovalWorkspace();
  return <ApprovalWorkspace data={data} canApprove={hasPermission(me, "issuance.request.approve")} />;
}
