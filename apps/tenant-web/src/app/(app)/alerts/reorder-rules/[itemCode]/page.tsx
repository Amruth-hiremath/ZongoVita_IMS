import { hasPermission } from "@ims/api-client";
import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  KeyValue,
  NoteBox,
  PageHeader,
  Pill,
  SectionLabel,
  Select,
} from "@ims/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getReorderRule } from "@/data/reorder-rules";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

export async function generateMetadata({ params }: { params: Promise<{ itemCode: string }> }): Promise<Metadata> {
  const { itemCode } = await params;
  return { title: `Reorder Rule — ${decodeURIComponent(itemCode)}` };
}

/** F19 Reorder Rule for one SKU (manager). */
export default async function ReorderRulePage({ params }: { params: Promise<{ itemCode: string }> }) {
  const { itemCode } = await params;
  const [{ me }, rule] = await Promise.all([requireSession(), getReorderRule(decodeURIComponent(itemCode))]);
  if (rule === null) notFound();

  const canManage = hasPermission(me, "replenishment.formula.manage");
  const lead = rule.lead_time;

  return (
    <>
      <PageHeader
        title={`Reorder Rule — ${rule.item_code}`}
        subtitle="Custom formula per SKU · lead time decomposed into internal PO time + vendor supply (Q11 · FB-18)"
        actions={
          canManage ? (
            <>
              <ActionButton endpoint={`PATCH /ui/v1/planning (reset ${rule.item_code} to category template)`}>
                Reset to template
              </ActionButton>
              <ActionButton variant="primary" endpoint="PUT /ui/v1/formulas/{id} (per-SKU rule)">
                Edit rule
              </ActionButton>
            </>
          ) : null
        }
      />

      <NoteBox tone="gray" className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
        <label htmlFor="rule-sku" className="text-[11.5px] font-semibold text-gray-600">
          SKU
        </label>
        <div className="w-[222px]">
          <Select id="rule-sku" compact defaultValue={rule.item_code}>
            <option value={rule.item_code}>
              {rule.item_code} · {rule.item_name}
            </option>
          </Select>
        </div>
        {rule.is_override ? (
          <Pill small tone="violet" className="ml-4 max-sm:ml-0">
            Per-SKU override
          </Pill>
        ) : null}
        <span className="text-[11.5px] text-gray-500">
          Template applied from category &apos;{rule.category}&apos;{rule.is_override ? " · overridden for this SKU" : ""}
        </span>
      </NoteBox>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card>
          <CardHeader title="Formula — suggested reorder qty" />
          <CardBody className="pt-7">
            <SectionLabel className="text-gray-500">Variables</SectionLabel>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {rule.variables.map((variable) => (
                <div
                  key={variable.name}
                  className="rounded-md border-[1.4px] border-gray-200 bg-gray-50 px-3 py-1.5"
                >
                  <p className="text-[11.5px] font-semibold text-blue-600">{variable.name}</p>
                  <p className="text-[10.5px] text-gray-500">{variable.value_label}</p>
                </div>
              ))}
            </div>
            <SectionLabel className="mt-3 text-gray-500">Formula</SectionLabel>
            <p className="mt-2 rounded-md border-[1.4px] border-blue-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-900">
              {rule.formula}
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={`Live preview — ${rule.preview.location_code}`} />
          <CardBody className="pt-2">
            <p className="text-[15px] text-gray-700">{rule.preview.expression}</p>
            <p className="mt-1 flex items-baseline gap-4">
              <span className="tabular text-[44px] font-bold leading-[52px] text-gray-900">
                {formatQty(rule.preview.result)}
              </span>
              <span className="text-[13px] text-gray-500">{rule.preview.uom}</span>
            </p>
            <Pill tone="blue" className="mt-2">
              Suggestion appears in F18
            </Pill>
            <NoteBox tone="gray" className="mt-3 text-[11.5px] leading-4 text-gray-700">
              <SectionLabel className="text-[9.5px]">Lead time — sourced (FB-18)</SectionLabel>
              <p className="mt-1">
                {lead.internal_po_days} d internal PO — {lead.internal_po_source}, this rule
              </p>
              <p>
                {lead.vendor_days} d vendor supply — {lead.vendor_code} · F38
              </p>
              <p className="font-semibold text-gray-900">= {lead.total_days} d total lead time</p>
            </NoteBox>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Category template & propagation" />
          <CardBody className="pt-5">
            <p className="flex flex-wrap gap-x-8 gap-y-1 text-[12.5px] text-gray-700">
              <span className="font-semibold text-gray-900">{rule.category} template:</span>
              <span>{rule.template.formula}</span>
            </p>
            <Checkbox
              className="mt-5 text-[13px]"
              label={`New items in '${rule.category}' inherit this template`}
              defaultChecked={rule.template.inherit_new_items}
            />
            <p className="mt-4 text-[11px] leading-5 text-gray-500">
              Propagation applies to future items only — existing SKUs keep their saved rules
              <br />
              until an admin bulk-applies the template explicitly.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Lead time — decomposed (FB-18)" className="pt-7" />
          <CardBody className="pt-3">
            <dl>
              <KeyValue label="Internal PO time" className="py-2">
                {lead.internal_po_days} days — {lead.internal_po_source}
              </KeyValue>
              <KeyValue label="Vendor supply" className="py-2">
                {lead.vendor_days} days — {lead.vendor_code} (F38)
              </KeyValue>
              <KeyValue label="Total lead" className="py-2">
                {lead.total_days} days — feeds formula
              </KeyValue>
            </dl>
          </CardBody>
        </Card>
      </div>

      <Callout dismissible className="mt-6">
        Rules are pure configuration — no code deploys. The engine evaluates them nightly and after every movement
        (FR-6/7 · Q11).
      </Callout>
    </>
  );
}
