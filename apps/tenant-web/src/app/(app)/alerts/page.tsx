import { hasPermission } from "@ims/api-client";
import {
  Card,
  CardBody,
  CardHeader,
  NoteBox,
  PageHeader,
  Pagination,
  Pill,
  SectionLabel,
  Table,
  TBody,
  TD,
  TH,
  THead,
  Toggle,
  type Tone,
  TR,
} from "@ims/ui";
import type { Metadata } from "next";
import Link from "next/link";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getAlertsPage, type AlertStatusKind } from "@/data/alerts";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";


export const metadata: Metadata = { title: "Alerts & Reorder Suggestions" };

const statusTone: Record<AlertStatusKind, Tone> = {
  below_min: "red",
  batch_expiring: "amber",
  expiry_window: "amber",
  above_min: "green",
};

/** F18 Alerts & Reorder Suggestions (manager). */
export default async function AlertsPage() {
  const { me, workspace } = await requireSession();
  if (workspace !== "manager") {
    return (
      <NoScreen title="Alerts & Reorder Suggestions">
        The wireframes draw alerts and reorder suggestions for the manager (F18) only.
      </NoScreen>
    );
  }

  const page = await getAlertsPage();
  const canExport = hasPermission(me, "reporting.export.run");
  const example = page.formula_example;
  const dead = page.dead_stock_example;

  return (
    <>
      <PageHeader
        title="Alerts & Reorder Suggestions"
        subtitle={`${page.open_count} open alerts · low-stock and expiry together · suggestions recalculate daily after every movement`}
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export CSV</ActionButton> : null}
            <ActionButton variant="primary" endpoint="POST /ui/v1/reorder-suggestions (push to procurement API)">
              Push to procurement API
            </ActionButton>
          </>
        }
      />

      <Card>
        <CardHeader title="Alert channels" />
        <CardBody className="flex flex-wrap items-center gap-x-14 gap-y-4 pt-8">
          {page.channels.map((channel) => (
            <Toggle key={channel.id} label={channel.label} defaultChecked={channel.enabled} />
          ))}
        </CardBody>
      </Card>

      <SectionLabel className="mt-2">Open alerts &amp; suggestions</SectionLabel>
      <div className="mt-2 max-w-[1106px]">
        <Table>
          <THead>
            <TR>
              <TH>SKU</TH>
              <TH>Item</TH>
              <TH>Location</TH>
              <TH align="right">On hand</TH>
              <TH align="right">Min</TH>
              <TH align="center">Lead PO+ven</TH>
              <TH align="right">Suggested qty</TH>
              <TH>Status</TH>
              <TH>
                <span className="sr-only">Reorder rule</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {page.rows.map((row) => (
              <TR key={`${row.item_code}-${row.location_code}`}>
                <TD>{row.item_code}</TD>
                <TD>{row.name}</TD>
                <TD>{row.location_code}</TD>
                <TD align="right" numeric>
                  {formatQty(row.on_hand)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(row.min_qty)}
                </TD>
                <TD align="center" numeric muted>
                  {row.lead_po_days}+{row.lead_vendor_days}
                </TD>
                <TD align="right" numeric>
                  {row.suggested_qty === null ? "—" : `${formatQty(row.suggested_qty)} ${row.suggested_uom}`}
                </TD>
                <TD>
                  <Pill small tone={statusTone[row.status.kind]}>
                    {row.status.label}
                  </Pill>
                </TD>
                <TD align="right" muted>
                  <Link href={`/alerts/reorder-rules/${row.item_code}`} className="whitespace-nowrap hover:text-gray-700">
                    Suggest → F19
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing {page.rows.length} of {formatQty(page.total)} alerts · sorted by {page.sorted_by}
        </p>
        <Pagination pages={page.pages} current={page.page} />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <NoteBox tone="gray" className="px-4 py-4">
          <SectionLabel>Suggested qty — per-SKU custom formula (Q11 · FB-18)</SectionLabel>
          <p className="mt-2 text-[13px] font-semibold text-gray-900">
            {example.item_code} @ {example.location_short}: {example.expression}
          </p>
          <p className="mt-1.5 text-[12px] text-gray-700">
            = {formatQty(example.result)} {example.uom}. {example.lead_sources}
          </p>
        </NoteBox>
        <Card>
          <CardBody>
            <SectionLabel>Dead stock rule (Q17)</SectionLabel>
            <p className="mt-2 text-[12.5px] text-gray-700">
              <span className="font-semibold text-gray-900">
                {dead.item_code} · no movement {dead.idle_days} days —
              </span>
              <br />
              its own threshold is {dead.threshold_days} days.
            </p>
            <p className="mt-2 text-[11px] text-gray-500">X is defined per SKU by the user (Q17).</p>
          </CardBody>
        </Card>
      </div>

      <NoteBox tone="gray" className="mt-4 px-4 py-4">
        <SectionLabel>What an alert looks like to an external system — webhook payload (FR-16)</SectionLabel>
        <p className="mt-2 whitespace-pre-line break-words text-[12px] leading-5 text-gray-700">{page.webhook_example}</p>
      </NoteBox>
    </>
  );
}
