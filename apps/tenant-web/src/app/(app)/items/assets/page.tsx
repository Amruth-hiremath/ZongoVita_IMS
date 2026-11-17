import { hasPermission } from "@ims/api-client";
import {
  Card,
  CardBody,
  CardHeader,
  cn,
  KeyValue,
  PageHeader,
  Pagination,
  Pill,
  SectionLabel,
  StatCard,
  Table,
  TBody,
  TD,
  TH,
  THead,
  type Tone,
  TR,
} from "@ims/ui";
import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ActionButton } from "@/components/action-button";
import { listAssets, type AssetStatus } from "@/data/assets";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { formatMonth } from "@/lib/dates";

export const metadata: Metadata = { title: "IT Asset Mapping" };

const statusLabel: Record<AssetStatus, string> = {
  in_service: "In service",
  in_repair: "In repair",
  spare: "Spare",
  retired: "Retired",
};
const statusTone: Record<AssetStatus, Tone> = { in_service: "green", in_repair: "amber", spare: "gray", retired: "dark" };

const lifecycle = [
  { title: "Mapped", text: "registered against the item code" },
  { title: "In service", text: "issued to a custodian · F11 scan" },
  { title: "In repair", text: "RMA · warranty claim tracks" },
  { title: "Retired", text: "kept for history — never deleted" },
];

/** F60 IT Asset Mapping. */
export default async function AssetsPage() {
  const [{ me }, page] = await Promise.all([requireSession(), listAssets()]);
  const canMap = hasPermission(me, "catalog.asset.manage");
  const canExport = hasPermission(me, "reporting.export.run");
  const { summary, drill_in: item } = page;

  return (
    <>
      <PageHeader
        title="IT Asset Mapping"
        subtitle="Serialised IT assets mapped to catalogue item codes — many assets, one item code (FB-04 · FR-9 serial tracking)"
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export assets</ActionButton> : null}
            {canMap ? (
              <ActionButton variant="primary" endpoint="PATCH /ui/v1/assets/{id}">
                + Map assets
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="grid max-w-[1136px] grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <StatCard
          label="Item codes w/ assets"
          value={formatQty(summary.item_codes.length)}
          hint={summary.item_codes.join(" · ")}
        />
        <StatCard label="Assets on record" value={formatQty(summary.asset_count)} hint="serial-tracked instances" />
        <StatCard
          label="In service"
          value={formatQty(summary.in_service)}
          badge={<Pill tone="green">{summary.in_service_percent}%</Pill>}
        />
        <StatCard
          label="Repair · Spare · Retired"
          value={`${summary.in_repair} · ${summary.spare} · ${summary.retired}`}
          hint="warranty tracked per asset"
        />
      </div>

      <SectionLabel className="mt-6">
        Asset register — each asset maps to one item code; one item code holds many assets
      </SectionLabel>

      <div className="mt-2 grid max-w-[1136px] grid-cols-[minmax(0,1fr)_412px] gap-4 max-lg:grid-cols-1">
        <div className="min-w-0">
          <Table>
            <THead>
              <TR>
                <TH>Asset tag</TH>
                <TH>Serial no</TH>
                <TH>Item code</TH>
                <TH>Item</TH>
                <TH>Status</TH>
                <TH>Custodian · location</TH>
              </TR>
            </THead>
            <TBody zebra>
              {page.rows.map((row) => (
                <TR key={row.asset_tag}>
                  <TD className="h-11">{row.asset_tag}</TD>
                  <TD className="h-11">{row.serial_no}</TD>
                  <TD className="h-11">{row.item_code}</TD>
                  <TD muted className="h-11 whitespace-nowrap">
                    {row.item_name}
                  </TD>
                  <TD className="h-11">
                    <Pill small tone={statusTone[row.status]}>
                      {statusLabel[row.status]}
                    </Pill>
                  </TD>
                  <TD muted className="h-11 whitespace-nowrap">
                    {row.custodian} · {row.location}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-[11.5px] text-gray-500">
              Showing {page.rows.length} of {formatQty(page.total)} assets · {summary.item_codes.length} item codes
            </p>
            <Pagination pages={page.pages} current={page.page} />
          </div>

          {canMap ? (
            <ActionButton
              variant="link"
              endpoint="PATCH /ui/v1/assets/{id}"
              icon={<Plus aria-hidden className="size-4" strokeWidth={1.8} />}
              className="mx-4 mt-3 flex h-auto min-h-12 w-[calc(100%-2rem)] justify-start gap-3 whitespace-normal py-2 text-left rounded-md border-[1.4px] border-dashed border-blue-200 px-6 font-semibold hover:bg-blue-50 hover:no-underline"
            >
              Map asset — scan serial → pick item code → assign custodian
            </ActionButton>
          ) : null}
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardHeader title={`Item drill-in — ${item.item_code}`} />
            <CardBody className="pt-3">
              <dl>
                <KeyValue label="Item code" className="py-2">
                  {item.item_code} · {item.numbering}
                </KeyValue>
                <KeyValue label={`Category path · ${item.category_path.length} levels`} className="py-2">
                  {item.category_path.join(" > ")}
                </KeyValue>
                <KeyValue label="Stock on hand" className="py-2">
                  {formatQty(item.stock_on_hand)} {item.uom} = {item.mapped_assets} mapped assets
                </KeyValue>
                <KeyValue label="In service" className="py-2">
                  {item.in_service} · {item.in_repair} in repair
                  {item.repair_reference ? ` (${item.repair_reference})` : ""}
                </KeyValue>
                <KeyValue label="Warranty" className="py-2">
                  per asset{item.next_warranty_expiry ? ` · next expiry ${formatMonth(item.next_warranty_expiry)}` : ""}
                </KeyValue>
              </dl>
              <p className="mt-3 text-[11px] text-blue-600">
                <Link href={`/items/${item.item_code}`} className="hover:underline">
                  Open item → F09
                </Link>{" "}
                · map assets from here or{" "}
                <Link href="/items/new" className="hover:underline">
                  F08
                </Link>
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Asset lifecycle" />
            <CardBody className="pt-4">
              <ol>
                {lifecycle.map((stage, index) => (
                  <li key={stage.title} className="relative flex gap-3.5 pb-3 last:pb-0">
                    {index < lifecycle.length - 1 ? (
                      <span aria-hidden className="absolute bottom-0 left-[10.5px] top-[22px] w-px bg-gray-300" />
                    ) : null}
                    <span
                      className={cn(
                        "relative flex size-[22px] shrink-0 items-center justify-center rounded-full border-[1.4px] text-[10.5px] font-semibold",
                        index === 0
                          ? "border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep text-white"
                          : "border-gray-300 bg-white text-gray-700",
                      )}
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-[12px] font-semibold text-gray-900">{stage.title}</p>
                      <p className="text-[10.5px] text-gray-500">{stage.text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
