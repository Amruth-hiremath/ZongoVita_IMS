import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";
import { getGrnDraft, getInwardPipeline } from "@/data/receiving";
import { requireSession } from "@/session/server";

import { InwardPipelineView } from "./inward-pipeline";
import { ReceiveStock } from "./receive-stock";

export const metadata: Metadata = { title: "Receive" };

/** Receive: F42 Receiving — Inward Pipeline (manager) or F10 Receive Stock (store). */
export default async function ReceivePage() {
  const { me, workspace } = await requireSession();

  switch (workspace) {
    case "manager":
      return <InwardPipelineView me={me} data={await getInwardPipeline()} />;
    case "store":
      return <ReceiveStock me={me} draft={await getGrnDraft()} />;
    default:
      return (
        <NoScreen title="Receive">
          The wireframes draw receiving for the approving user type (F42) and the store desk (F10) only. There is no
          receiving screen for this user type.
        </NoScreen>
      );
  }
}
