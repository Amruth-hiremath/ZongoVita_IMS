import { hasPermission } from "@ims/api-client";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NoScreen } from "@/components/no-screen";
import { getFeaturedTransfer, getNewTransferDraft } from "@/data/transfers";
import { requireSession } from "@/session/server";

import { TransferLifecycle } from "./transfer-lifecycle";
import { TransferRequest } from "./transfer-request";

export const metadata: Metadata = { title: "Transfers" };

/** Transfers: F15 Transfer lifecycle for the manager, F14 Transfer — New Request for the store. */
export default async function TransfersPage() {
  const { me, workspace } = await requireSession();

  switch (workspace) {
    case "manager": {
      const transfer = await getFeaturedTransfer();
      if (transfer === null) notFound();
      return <TransferLifecycle me={me} transfer={transfer} />;
    }
    case "store": {
      const draft = await getNewTransferDraft();
      return <TransferRequest draft={draft} canCreate={hasPermission(me, "transfers.transfer.create")} />;
    }
    default:
      return (
        <NoScreen title="Transfers">
          The wireframes draw transfers for the manager (F15 Transfer lifecycle) and the store (F14 Transfer — New
          Request) only.
        </NoScreen>
      );
  }
}
