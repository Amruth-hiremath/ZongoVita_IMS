import { hasPermission } from "@ims/api-client";
import type { Metadata } from "next";

import { getNewTransferDraft } from "@/data/transfers";
import { requireSession } from "@/session/server";

import { TransferRequest } from "../transfer-request";

export const metadata: Metadata = { title: "Transfer — New Request" };

/** F14 Transfer — New Request. */
export default async function NewTransferPage() {
  const [{ me }, draft] = await Promise.all([requireSession(), getNewTransferDraft()]);
  return <TransferRequest draft={draft} canCreate={hasPermission(me, "transfers.transfer.create")} />;
}
