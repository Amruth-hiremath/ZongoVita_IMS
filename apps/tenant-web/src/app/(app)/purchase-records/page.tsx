import { hasPermission } from "@ims/api-client";
import { Card, PageHeader, Pill, StatCard } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { listPurchaseRecords } from "@/data/purchase-records";
import { formatMoney, formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { PurchaseRecordsList } from "./purchase-records-list";

export const metadata: Metadata = { title: "Purchase Records" };

const contextFields = [
  { title: "PO number", text: "PO-2214 · commercial reference" },
  { title: "Item & quantity", text: "item code · PO qty · our SKU link" },
  { title: "Department · people", text: "user dept · purchased by · approved by" },
  { title: "Inward & inspection", text: "date of inward · by whom · when · comments" },
  { title: "Expected usage", text: "planned issue date · linked work order" },
];

/** F40 Purchase Records. */
export default async function PurchaseRecordsPage() {
  const [{ me }, page] = await Promise.all([requireSession(), listPurchaseRecords()]);
  const canCreate = hasPermission(me, "purchasing.record.manage");
  const canExport = hasPermission(me, "reporting.export.run");
  const { summary } = page;

  return (
    <>
      <PageHeader
        title="Purchase Records"
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export</ActionButton> : null}
            {canCreate ? (
              <ActionButton variant="primary" endpoint="POST /ui/v1/purchase-records">
                + New purchase record
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="grid max-w-[1136px] grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <StatCard
          label="POs · Quarter"
          value={formatQty(summary.record_count)}
          hint={`${formatMoney(summary.total_value)} total value`}
        />
        <StatCard
          label="Awaiting inward"
          value={formatQty(summary.awaiting_inward)}
          badge={<Pill tone="amber">due within {summary.due_within_days} d</Pill>}
        />
        <StatCard
          label="Inspection exceptions"
          value={formatQty(summary.inspection_exceptions)}
          badge={<Pill tone="red">supplier returns open</Pill>}
        />
        <StatCard
          label="Avg total lead"
          value={`${summary.avg_internal_lead_days + summary.avg_vendor_lead_days} d`}
          hint={`${summary.avg_internal_lead_days} d internal + ${summary.avg_vendor_lead_days} d vendor`}
        />
      </div>

      <PurchaseRecordsList page={page} />

      <Card className="mt-6 max-w-[1136px] p-4">
        <h2 className="text-[13.5px] font-semibold text-gray-900">Every record carries the full purchase context</h2>
        <ul className="mt-3 grid grid-cols-5 gap-5 max-lg:grid-cols-2 max-sm:grid-cols-1">
          {contextFields.map((field) => (
            <li key={field.title} className="rounded-md border-[1.4px] border-gray-200 bg-surface-alt px-4 py-3">
              <p className="text-[12px] font-semibold text-gray-900">{field.title}</p>
              <p className="mt-1 text-[10.5px] leading-[14px] text-gray-500">{field.text}</p>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
