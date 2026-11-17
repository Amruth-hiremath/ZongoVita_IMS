"use client";

import {
  Button,
  ButtonLink,
  Callout,
  Card,
  CardHeader,
  KeyValue,
  Tabs,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Timeline,
  Pill,
  type Tone,
} from "@ims/ui";
import { useState } from "react";

import type { ItemDetail, LocationStockKind, LotStatusKind } from "@/data/item-detail";
import { formatQty } from "@/lib/format";

import { formatDay } from "./format";

type TabId = "overview" | "batches" | "movements" | "reorder" | "linked";

const stockTone: Record<LocationStockKind, Tone> = { healthy: "green", below_min: "red" };
const lotTone: Record<LotStatusKind, Tone> = { fresh: "green", expiring: "amber", expired: "red" };

function AttributesCard({ item }: { item: ItemDetail }) {
  return (
    <Card className="px-4 pb-2.5 pt-3.5">
      <h2 className="text-[13.5px] font-semibold text-gray-900">Attributes</h2>
      <dl>
        {item.attributes.map((attribute) => (
          <KeyValue key={attribute.name} label={attribute.name} className="py-[5px]">
            {attribute.value}
          </KeyValue>
        ))}
        <KeyValue label="Added by" className="py-[5px]">
          {item.created_by}
        </KeyValue>
      </dl>
    </Card>
  );
}

function ThresholdsCard({ item }: { item: ItemDetail }) {
  const t = item.thresholds;
  return (
    <Card className="px-4 pb-2.5 pt-3.5">
      <h2 className="text-[13.5px] font-semibold text-gray-900">Thresholds &amp; reorder</h2>
      <dl className="mt-3">
        <KeyValue label="Min / Max" className="py-[5px]">
          {formatQty(t.min)} / {formatQty(t.max)} {item.uom}
        </KeyValue>
        <KeyValue label="Lead time" className="py-[5px]">
          {t.internal_po_lead_days + t.vendor_lead_days} d = {t.internal_po_lead_days} PO + {t.vendor_lead_days} vendor
        </KeyValue>
        <KeyValue label="Avg daily use" className="py-[5px]">
          {formatQty(t.avg_daily_use)} {item.uom}
        </KeyValue>
        <KeyValue label="Formula" className="py-[5px]">
          {t.formula}
        </KeyValue>
      </dl>
    </Card>
  );
}

function MovementsCard({ item, onAll }: { item: ItemDetail; onAll?: () => void }) {
  return (
    <Card>
      <CardHeader
        title="Recent movements"
        action={
          onAll ? (
            <Button variant="link" onClick={onAll}>
              All →
            </Button>
          ) : null
        }
      />
      <div className="px-4 pb-6 pt-6">
        <Timeline entries={item.movements} />
      </div>
    </Card>
  );
}

function StockCard({ item }: { item: ItemDetail }) {
  return (
    <Card className="overflow-hidden pb-7">
      <CardHeader title="Stock by location (FR-4 · FB-09)" className="pt-3.5" />
      <Table className="mt-6">
        <THead>
          <TR>
            <TH>Location</TH>
            <TH align="right">On hand</TH>
            <TH align="right">Free</TH>
            <TH align="right">Locked</TH>
            <TH align="right">Quar.</TH>
            <TH align="right">Value (₹)</TH>
            <TH>Status</TH>
          </TR>
        </THead>
        <TBody zebra>
          {item.stock.map((row) => (
            <TR key={row.location_code} className="[&>td]:h-10">
              <TD strong>
                {row.location_code} · {row.location_name}
              </TD>
              <TD align="right" numeric className="text-gray-700">
                {formatQty(row.on_hand)}
              </TD>
              <TD align="right" numeric strong>
                {formatQty(row.free)}
              </TD>
              <TD align="right" numeric muted>
                {formatQty(row.locked)}
              </TD>
              <TD align="right" numeric muted>
                {formatQty(row.quarantined)}
              </TD>
              <TD align="right" numeric className="text-gray-700">
                {formatQty(row.value)}
              </TD>
              <TD>
                <Pill tone={stockTone[row.status.kind]} small>
                  {row.status.label}
                </Pill>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </Card>
  );
}

function BatchesCard({ item, onManage }: { item: ItemDetail; onManage?: () => void }) {
  return (
    <Card className="overflow-hidden pb-4">
      <CardHeader
        title="Batches & expiry (FR-9 · FB-05)"
        className="pt-3.5"
        action={
          onManage ? (
            <Button variant="link" onClick={onManage}>
              Manage batches →
            </Button>
          ) : null
        }
      />
      <Table className="mt-6">
        <THead>
          <TR>
            <TH>Batch / lot</TH>
            <TH>Manufactured</TH>
            <TH>Expiry</TH>
            <TH align="right">Qty</TH>
            <TH>Location</TH>
            <TH>Status</TH>
          </TR>
        </THead>
        <TBody zebra>
          {item.lots.map((lot) => (
            <TR key={lot.lot_no} className="[&>td]:h-10">
              <TD className="text-gray-700">{lot.lot_no}</TD>
              <TD muted>{lot.manufactured}</TD>
              <TD>{lot.expires_on === null ? "—" : formatDay(lot.expires_on)}</TD>
              <TD align="right" numeric>
                {formatQty(lot.qty)}
              </TD>
              <TD muted>{lot.location_code}</TD>
              <TD>
                <Pill tone={lotTone[lot.status.kind]} small>
                  {lot.status.label}
                </Pill>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
      {item.expiry_notice ? (
        <div className="px-4 pt-10">
          <Callout tone="warning" dismissible className="min-h-11">
            {item.expiry_notice}
          </Callout>
        </div>
      ) : null}
    </Card>
  );
}

/** Tabs and panels of F09. Only Overview is drawn; the other tabs reuse the drawn panels. */
export function ItemTabs({ item }: { item: ItemDetail }) {
  const [tab, setTab] = useState<TabId>("overview");

  const overview = (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[420px_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-6">
        <AttributesCard item={item} />
        <ThresholdsCard item={item} />
        <MovementsCard item={item} onAll={() => setTab("movements")} />
      </div>
      <div className="flex min-w-0 flex-col gap-6">
        <StockCard item={item} />
        <BatchesCard item={item} onManage={() => setTab("batches")} />
      </div>
    </div>
  );

  return (
    <Tabs
      value={tab}
      onChange={(id) => setTab(id as TabId)}
      className="gap-6 overflow-x-auto [&>button]:shrink-0 sm:[&>button]:w-24 sm:[&>button]:text-left"
      panelClassName="mt-7"
      items={[
        { id: "overview", label: "Overview", content: overview },
        { id: "batches", label: "Batches", content: <BatchesCard item={item} /> },
        {
          id: "movements",
          label: "Movements",
          content: (
            <div className="max-w-[640px]">
              <MovementsCard item={item} />
            </div>
          ),
        },
        {
          id: "reorder",
          label: "Reorder rule",
          content: (
            <div className="flex max-w-[640px] flex-col gap-4">
              <ThresholdsCard item={item} />
              <div>
                <ButtonLink variant="link" href={`/alerts/reorder-rules/${item.item_code}`}>
                  Open reorder rule (F19) →
                </ButtonLink>
              </div>
            </div>
          ),
        },
        {
          id: "linked",
          label: "Linked systems",
          content: (
            <Card className="max-w-[640px] p-5">
              <p className="text-[13px] font-semibold text-gray-900">No wireframe for this tab</p>
              <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">
                F09 draws the Overview tab only. What Linked systems shows for an item is not specified in the frames.
              </p>
            </Card>
          ),
        },
      ]}
    />
  );
}
