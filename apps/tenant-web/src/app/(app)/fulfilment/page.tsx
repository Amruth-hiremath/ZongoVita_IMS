import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";
import { getFulfilmentQueue } from "@/data/fulfilment";
import { requireSession } from "@/session/server";

import { FulfilmentWorkspace, PrintButton } from "./fulfilment-workspace";

export const metadata: Metadata = { title: "Store Fulfilment Queue" };

/** Fulfilment Queue. Store workspace: F29 Store Fulfilment Queue. No frame exists for the other workspaces. */
export default async function FulfilmentPage() {
  const { workspace } = await requireSession();
  if (workspace !== "store") {
    return (
      <NoScreen title="Fulfilment Queue">
        The wireframes draw the fulfilment queue for store staff only; there is no fulfilment screen for this user type.
      </NoScreen>
    );
  }

  const queue = await getFulfilmentQueue();
  const next = queue.rows.find((row) => row.state.kind === "ready_to_pick");

  return (
    <div className="max-w-[1136px]">
      <PageHeader
        title="Store Fulfilment Queue"
        className="items-center"
        actions={
          <>
            <PrintButton>Print pick lists</PrintButton>
            {next ? (
              <ButtonLink href="/scan-issue" variant="primary">
                Start picking {next.request_ref}
              </ButtonLink>
            ) : null}
          </>
        }
      />
      <FulfilmentWorkspace queue={queue} />
      <p className="mt-9 text-[11px] text-gray-500">
        Issuance by scan mirrors entry by scan — the same barcode discipline on both sides of the shelf (FB-11).
      </p>
    </div>
  );
}
