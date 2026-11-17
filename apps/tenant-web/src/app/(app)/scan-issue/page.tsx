import { PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getIssueDraft } from "@/data/issues";
import { requireSession } from "@/session/server";

import { IssueForm } from "./issue-form";

export const metadata: Metadata = { title: "Issue Stock" };

/** Scan & Issue. Store workspace: F11 Issue Stock. No frame exists for the other workspaces. */
export default async function ScanIssuePage() {
  const { workspace } = await requireSession();
  if (workspace !== "store") {
    return (
      <NoScreen title="Scan & Issue">
        The wireframes draw the issue screen for store staff only; there is no scan-and-issue screen for this user type.
      </NoScreen>
    );
  }

  const draft = await getIssueDraft();

  return (
    <div className="max-w-[1136px]">
      <PageHeader
        title={`Issue Stock — ${draft.issue_no}`}
        actions={
          <>
            <ActionButton endpoint={`PUT /ui/v1/fulfilment-queue/${draft.queue_id} (save draft; not in the LLD route table)`}>
              Save draft
            </ActionButton>
            <ActionButton variant="primary" endpoint={`POST /ui/v1/fulfilment-queue/${draft.queue_id}/complete`}>
              Post issue
            </ActionButton>
          </>
        }
      />
      <IssueForm draft={draft} />
    </div>
  );
}
