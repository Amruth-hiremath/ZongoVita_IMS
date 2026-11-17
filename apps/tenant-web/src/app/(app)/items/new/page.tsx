import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getItemFormData } from "@/data/item-form";
import { requireSession } from "@/session/server";

import { ItemForm } from "./item-form";

export const metadata: Metadata = { title: "Add / Configure Item" };

/** F08 Add / Configure Item. */
export default async function NewItemPage() {
  const { me } = await requireSession();
  if (!hasPermission(me, "catalog.item.create")) notFound();
  const data = await getItemFormData();

  return (
    <>
      <PageHeader
        title="Add / Configure Item"
        subtitle="Governed category · image upload · expiry tracking where applicable · vendor-linked purchase details (FB-04 · FB-05 · FB-26)"
        actions={
          <>
            <ButtonLink href="/items" className="w-[88px]">
              Cancel
            </ButtonLink>
            <ActionButton variant="primary" endpoint="POST /ui/v1/items" className="w-[94px]">
              Save item
            </ActionButton>
          </>
        }
      />
      <ItemForm data={data} />
    </>
  );
}
