import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader, Pill } from "@ims/ui";
import { Image as ImageIcon } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getItemDetail } from "@/data/item-detail";
import { formatMoney } from "@/lib/format";
import { requireSession } from "@/session/server";

import { formatDay, shortLocation } from "./format";
import { ItemTabs } from "./item-tabs";

interface Props {
  params: Promise<{ itemCode: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { itemCode } = await params;
  return { title: decodeURIComponent(itemCode) };
}

/** F09 Item detail. */
export default async function ItemDetailPage({ params }: Props) {
  const { itemCode } = await params;
  const [{ me }, item] = await Promise.all([requireSession(), getItemDetail(decodeURIComponent(itemCode))]);
  if (item === null) notFound();

  const canEdit = hasPermission(me, "catalog.item.edit");

  return (
    <>
      <PageHeader
        leading={
          <span className="flex size-11 shrink-0 items-center justify-center rounded-md border-[1.4px] border-gray-300 bg-gray-50 text-gray-500">
            <ImageIcon aria-hidden className="size-4" strokeWidth={1.6} />
          </span>
        }
        breadcrumbs={[{ label: "Inventory" }, { label: "Items", href: "/items" }, { label: item.item_code }]}
        title={item.name}
        subtitle={`SKU ${item.item_code} · ${item.category} · ${item.uom} · Cost ${formatMoney(item.cost)} · ${item.lifecycle} · Created ${formatDay(item.created_at)} by ${item.created_by}`}
        badges={
          <>
            {item.below_min_locations.map((code) => (
              <Pill key={code} tone="red">
                Below min at {shortLocation(code)}
              </Pill>
            ))}
            {item.batch_tracked ? <Pill tone="blue">Batch tracked</Pill> : null}
            {item.expiry_tracked ? <Pill tone="blue">Expiry tracked</Pill> : null}
            <Pill tone="violet">Reorder rule: {item.reorder_rule}</Pill>
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-3 lg:mt-8">
            {canEdit ? (
              <ActionButton endpoint="PATCH /ui/v1/items/{id}" className="w-[88px]">
                Edit
              </ActionButton>
            ) : null}
            <ButtonLink variant="soft" href="/receive" className="w-[88px]">
              Receive
            </ButtonLink>
            <ButtonLink variant="primary" href="/issuance">
              Issue stock
            </ButtonLink>
          </div>
        }
      />
      <ItemTabs item={item} />
    </>
  );
}
