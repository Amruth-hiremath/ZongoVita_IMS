import { hasPermission, type Me } from "@ims/api-client";
import { PageHeader } from "@ims/ui";

import { ActionButton } from "@/components/action-button";
import type { GrnDraft } from "@/data/receiving";

import { formatDay as formatDate } from "@/lib/dates";
import { GrnForm } from "./grn-form";

/** F10 Receive Stock (store desk). */
export function ReceiveStock({ me, draft }: { me: Me; draft: GrnDraft }) {
  const canCreate = hasPermission(me, "receiving.grn.create");
  const canPost = hasPermission(me, "receiving.grn.post");

  return (
    <>
      <PageHeader
        title={`Receive Stock — ${draft.grn_number}`}
        subtitle="Goods receipt note · posting makes stock available immediately"
        actions={
          <>
            {canCreate ? <ActionButton endpoint="POST /ui/v1/grns">Save draft</ActionButton> : null}
            {canPost ? (
              <ActionButton variant="primary" endpoint="POST /ui/v1/grns/{id}/post">
                Post receipt
              </ActionButton>
            ) : null}
          </>
        }
      />
      <GrnForm draft={draft} receiptDate={formatDate(draft.receipt_date)} />
    </>
  );
}
