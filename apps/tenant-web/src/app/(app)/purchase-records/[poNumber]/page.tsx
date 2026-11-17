import { hasPermission } from "@ims/api-client";
import {
  Card,
  CardBody,
  CardHeader,
  Field,
  Input,
  KeyValue,
  NoteBox,
  PageHeader,
  Pill,
  SectionLabel,
  Timeline,
  cn,
} from "@ims/ui";
import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getPurchaseRecord, type PurchaseRecordDetail } from "@/data/purchase-records";
import { formatMoney, formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { formatDay, formatDayYearTime, formatMonth } from "@/lib/dates";
import { inspectionLabel, recordStatusLabel, recordStatusTone } from "../record-status";

type Params = Promise<{ poNumber: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { poNumber } = await params;
  return { title: `Purchase Record — ${poNumber}` };
}

/** F41 Purchase Record detail. */
export default async function PurchaseRecordPage({ params }: { params: Params }) {
  const { poNumber } = await params;
  const [{ me }, record] = await Promise.all([requireSession(), getPurchaseRecord(poNumber)]);
  if (record === null) notFound();

  const canCreate = hasPermission(me, "purchasing.record.manage");
  const canExport = hasPermission(me, "reporting.export.run");
  const { vendor } = record;

  const fields: { label: string; value: string }[] = [
    { label: "PO number", value: record.po_number },
    { label: "Item code", value: record.item_code },
    { label: "User department", value: record.department },
    { label: "Purchased by", value: record.purchased_by },
    { label: "Purchase approved by", value: record.approved_by },
    {
      label: "Date of inward",
      value: record.inward_date
        ? [formatDay(record.inward_date), record.grn_number].filter(Boolean).join(" · ")
        : "—",
    },
    {
      label: "Expected usage / issue date",
      value: [formatDay(record.expected_use_date), record.work_order].filter(Boolean).join(" · "),
    },
    { label: "PO quantity", value: `${formatQty(record.quantity)} ${record.uom} @ ${formatMoney(record.rate)}` },
  ];

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "Purchases", href: "/purchase-records" }, { label: record.po_number }]}
        title={`Purchase Record — ${record.po_number}`}
        badges={
          <>
            <Pill tone={recordStatusTone[record.status]}>{recordStatusLabel[record.status]}</Pill>
            {record.inspection ? (
              <Pill tone={record.inspection === "pass" ? "green" : "red"}>
                Inspection {inspectionLabel[record.inspection].toLowerCase()}
              </Pill>
            ) : null}
            <Link href={`/vendors/${vendor.vendor_code}`}>
              <Pill tone="blue">
                Vendor: {vendor.short_name} · {vendor.vendor_code}
              </Pill>
            </Link>
          </>
        }
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Download</ActionButton> : null}
            {record.grn_number ? (
              <ActionButton variant="soft" endpoint="GET /ui/v1/grns/{id}">
                Open {record.grn_number}
              </ActionButton>
            ) : null}
            {canCreate ? (
              <ActionButton variant="primary" endpoint="POST /ui/v1/purchase-records">
                Raise follow-up PO
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="grid max-w-[1136px] grid-cols-[minmax(0,1fr)_412px] gap-4 max-lg:grid-cols-1">
        <div className="min-w-0">
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 max-sm:grid-cols-1">
            {fields.map((field) => {
              const id = `po-${field.label.toLowerCase().replace(/[^a-z]+/g, "-")}`;
              return (
                <Field key={field.label} label={field.label} htmlFor={id}>
                  <Input id={id} readOnly value={field.value} className="h-[35px]" />
                </Field>
              );
            })}
          </div>

          {record.inspection_details ? <InspectionCard record={record} /> : null}
          <LifecycleCard record={record} />
        </div>

        <div className="flex min-w-0 flex-col gap-6 lg:mt-1">
          <Card>
            <CardHeader title="Vendor — attribution anchor" />
            <CardBody className="pt-6">
              <p className="text-[14px] font-semibold text-gray-900">{vendor.legal_name}</p>
              <p className="mt-0.5 text-[11px] text-gray-500">
                {vendor.vendor_code} · {vendor.city} · active since {formatMonth(vendor.active_since)}
              </p>
              <dl className="mt-1">
                <KeyValue label="Rate at PO">
                  {formatMoney(record.rate)} · rate list {vendor.rate_list_revision}
                </KeyValue>
                <KeyValue label="MOQ">
                  {formatQty(vendor.moq)} {record.uom} · PO qty {formatQty(record.quantity)} ={" "}
                  {formatQty(Number(record.quantity) / Number(vendor.moq))} × MOQ
                </KeyValue>
                <KeyValue label="Supply lead time">{vendor.supply_lead_days} days · vendor-stated</KeyValue>
              </dl>
              <NoteBox tone="red" className="mt-4 px-4 py-3.5">
                <p className="text-[11px] font-semibold text-red-700">Quality events on this PO roll up to this</p>
              </NoteBox>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Stock provenance" />
            <CardBody className="pt-6">
              <p className="text-[12.5px] font-semibold text-gray-900">
                {formatQty(record.provenance.received)} {record.uom} received · {formatQty(record.provenance.issued)}{" "}
                issued · {formatQty(record.provenance.on_hand)} on hand
              </p>
              <Timeline className="mt-3" entries={record.provenance.events} />
            </CardBody>
          </Card>
        </div>
      </div>

      <p className="mt-8 max-w-[1136px] text-[11px] text-gray-500">
        No existing module to integrate with — purchase records are native to IMS, per the mentor clarification (FB-26).
      </p>
    </>
  );
}

function InspectionCard({ record }: { record: PurchaseRecordDetail }) {
  const details = record.inspection_details;
  if (details === null) return null;
  return (
    <Card className="mt-8">
      <CardHeader title="Inspection details" />
      <CardBody className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6 pt-4 max-sm:grid-cols-1">
        <dl className="self-start">
          <KeyValue label="By whom">
            {details.inspected_by} · {details.desk}
          </KeyValue>
          <KeyValue label="When">{formatDayYearTime(details.inspected_at)}</KeyValue>
          <KeyValue label="Verdict">{details.verdict}</KeyValue>
        </dl>
        <div className="border-l border-gray-300 pl-6 pt-2 max-sm:border-l-0 max-sm:pl-0">
          <SectionLabel>Comments</SectionLabel>
          <ul className="mt-1.5 space-y-2">
            {details.comments.map((comment) => (
              <li key={comment} className="flex gap-2.5 text-[11px] leading-[14px] text-gray-700">
                <span aria-hidden className="mt-1 size-1.5 shrink-0 rounded-full bg-blue-600" />
                {comment}
              </li>
            ))}
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}

/**
 * "Record lifecycle": left-aligned steps with dark markers (check when done, filled when
 * current, hollow when upcoming). The kit's Stepper centres its labels and uses the blue
 * current marker, so this strip is drawn here with the same tokens.
 */
function LifecycleCard({ record }: { record: PurchaseRecordDetail }) {
  return (
    <Card className="mt-5">
      <CardHeader title="Record lifecycle" />
      <CardBody className="pt-8">
        <ol className="grid grid-cols-5 gap-y-4 max-sm:grid-cols-2">
          {record.lifecycle.map((step, index) => (
            <li key={step.label} className="min-w-0">
              <div className="flex items-center">
                <span
                  className={cn(
                    "flex size-[19px] shrink-0 items-center justify-center rounded-full border-[1.4px]",
                    step.state === "upcoming" ? "border-gray-300 bg-white" : "border-gray-900 bg-gray-900 text-white",
                  )}
                >
                  {step.state === "done" ? <Check aria-hidden className="size-3" strokeWidth={2.4} /> : null}
                </span>
                {index < record.lifecycle.length - 1 ? (
                  <span aria-hidden className="mx-1 h-px flex-1 bg-gray-300 max-sm:hidden" />
                ) : null}
              </div>
              <p className="mt-2 text-[12px] font-semibold text-gray-900">{step.label}</p>
              <p className="text-[10.5px] text-gray-500">{step.meta}</p>
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}
