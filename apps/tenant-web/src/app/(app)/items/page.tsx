import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { listItems } from "@/data/items";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { ItemsList } from "./items-list";

export const metadata: Metadata = { title: "Items & Catalog" };

/** F07 Items & Catalog. */
export default async function ItemsPage() {
  const [{ me }, page] = await Promise.all([requireSession(), listItems()]);
  const canCreate = hasPermission(me, "catalog.item.create");

  return (
    <>
      <PageHeader
        title="Items & Catalog"
        subtitle={`${formatQty(page.total)} items across ${page.location_count} locations · free, locked and quarantined columns with image thumbnails (FB-04 · FB-09)`}
        actions={
          <>
            {canCreate ? (
              <ButtonLink href="/items/new" variant="primary">
                + Add item
              </ButtonLink>
            ) : null}
            {canCreate ? <ActionButton endpoint="POST /ui/v1/items (bulk import)">Import CSV</ActionButton> : null}
            <ActionButton endpoint="POST /ui/v1/exports">Export</ActionButton>
          </>
        }
      />
      <ItemsList page={page} />
    </>
  );
}
