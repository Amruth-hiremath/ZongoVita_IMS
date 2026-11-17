"use client";

import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Field,
  Input,
  KeyValue,
  SectionLabel,
  Select,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Tabs,
} from "@ims/ui";
import { Plus, ScanLine, X } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { GrnDraft, GrnLine } from "@/data/receiving";
import { formatMoney, formatQty } from "@/lib/format";

type EditableField = "qty" | "lot_number" | "expiry";

/**
 * The GRN entry of F10. Line inputs and header selects are local until "Save draft" or
 * "Post receipt" sends them (POST /ui/v1/grns, POST /ui/v1/grns/{id}/post). Line totals and
 * the GRN total are Core's figures for the draft as loaded; the app does no money arithmetic.
 */
export function GrnForm({ draft, receiptDate }: { draft: GrnDraft; receiptDate: string }) {
  const [lines, setLines] = useState<GrnLine[]>(draft.lines);

  const update = (lineId: string, field: EditableField, value: string) =>
    setLines((current) => current.map((line) => (line.line_id === lineId ? { ...line, [field]: value } : line)));

  const remove = (lineId: string) => setLines((current) => current.filter((line) => line.line_id !== lineId));

  const manual = (
    <>
      <div className="flex flex-wrap items-end gap-6 max-sm:gap-4">
        <Field label="GRN no · auto" htmlFor="grn-number" className="w-[160px]">
          <Input id="grn-number" value={draft.grn_number} readOnly />
        </Field>
        <Field label="Date" htmlFor="grn-date" className="w-[140px]">
          <Input id="grn-date" defaultValue={receiptDate} />
        </Field>
        <Field label="Receive into" htmlFor="grn-site" className="w-[220px]">
          <Select id="grn-site" defaultValue={draft.site.code}>
            {draft.site_options.map((site) => (
              <option key={site.code} value={site.code}>
                {site.code} · {site.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Supplier · vendor master" htmlFor="grn-vendor" className="w-[200px]">
          <Select id="grn-vendor" defaultValue={draft.vendor.code}>
            {draft.vendor_options.map((vendor) => (
              <option key={vendor.code} value={vendor.code}>
                {vendor.short_name} · {vendor.code}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Purchase record · PO" htmlFor="grn-po" className="w-[200px]">
          <Select id="grn-po" defaultValue={draft.purchase_record.po_number}>
            {draft.purchase_record_options.map((record) => (
              <option key={record.po_number} value={record.po_number}>
                {record.po_number} · {record.reference}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="mt-7 flex items-center gap-14">
        <SectionLabel>Line items</SectionLabel>
        <ActionButton
          variant="link"
          endpoint="GET /ui/v1/scan/{code}"
          icon={<ScanLine aria-hidden className="size-3.5" strokeWidth={1.6} />}
          className="text-[11px]"
        >
          Scan barcode to add a line
        </ActionButton>
      </div>

      <div className="mt-2 max-w-[1066px]">
        <Table>
          <THead>
            <TR>
              <TH>SKU · scan</TH>
              <TH>Item</TH>
              <TH align="center">Qty</TH>
              <TH align="center">UoM</TH>
              <TH align="center">Batch / lot</TH>
              <TH align="center">Expiry</TH>
              <TH align="right">Cost (₹)</TH>
              <TH align="right">Line total (₹)</TH>
              <TH>
                <span className="sr-only">Remove</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {lines.map((line) => (
              <TR key={line.line_id} className="h-14">
                <TD>{line.item_code}</TD>
                <TD>{line.item_name}</TD>
                <TD align="center">
                  <Input
                    compact
                    inputMode="decimal"
                    aria-label={`Quantity received, ${line.item_code}`}
                    className="w-[52px]"
                    value={line.qty}
                    onChange={(event) => update(line.line_id, "qty", event.target.value)}
                  />
                </TD>
                <TD align="center">{line.uom}</TD>
                <TD align="center">
                  <Input
                    compact
                    aria-label={`Batch or lot, ${line.item_code}`}
                    placeholder="—"
                    className="w-[112px] placeholder:text-gray-900"
                    value={line.lot_number}
                    onChange={(event) => update(line.line_id, "lot_number", event.target.value)}
                  />
                </TD>
                <TD align="center">
                  <Input
                    compact
                    aria-label={`Expiry, ${line.item_code}`}
                    placeholder="—"
                    className="w-[92px] placeholder:text-gray-900"
                    value={line.expiry}
                    onChange={(event) => update(line.line_id, "expiry", event.target.value)}
                  />
                </TD>
                <TD align="right" numeric>
                  {formatQty(line.unit_cost)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(line.line_total)}
                </TD>
                <TD align="center">
                  <button
                    type="button"
                    aria-label={`Remove ${line.item_code}`}
                    className="text-gray-500 hover:text-gray-900"
                    onClick={() => remove(line.line_id)}
                  >
                    <X aria-hidden className="size-3" strokeWidth={1.8} />
                  </button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
        <ActionButton
          variant="link"
          endpoint="GET /ui/v1/scan/{code} · GET /ui/v1/items"
          icon={<Plus aria-hidden className="size-4" strokeWidth={1.8} />}
          className="mt-0 h-11 w-full justify-start gap-3 rounded-md border-[1.4px] border-dashed border-blue-200 px-5 font-semibold hover:no-underline"
        >
          Add line — scan barcode or search SKU (FR-8)
        </ActionButton>
      </div>

      <div className="mt-4 grid grid-cols-[minmax(0,1fr)_412px] gap-6 max-lg:grid-cols-1">
        <div className="min-w-0 pt-4">
          <Callout tone="info" dismissible>
            {draft.notice}
          </Callout>
          <p className="mt-4 flex items-baseline gap-10 px-0.5">
            <span className="text-[11px] text-gray-500">Total — {lines.length} lines</span>
            <span className="tabular text-[15px] font-bold text-gray-900">{formatMoney(draft.total_value)}</span>
          </p>
        </div>
        <Card>
          <CardHeader title={draft.linked_record.title} />
          <CardBody className="pt-2">
            <dl>
              {draft.linked_record.facts.map((fact) => (
                <KeyValue key={fact.label} label={fact.label} className="text-[12px]">
                  {fact.value}
                </KeyValue>
              ))}
            </dl>
          </CardBody>
        </Card>
      </div>

      <p className="mt-6 text-[11px] text-gray-500">{draft.footnote}</p>
    </>
  );

  return (
    <Tabs
      variant="segmented"
      panelClassName="mt-3.5"
      items={[
        { id: "manual", label: "Manual entry", content: manual },
        { id: "suggestion", label: "From suggestion", content: <NoMode /> },
        { id: "api", label: "External system (API)", content: <NoMode /> },
      ]}
    />
  );
}

function NoMode() {
  return (
    <Card className="max-w-[640px] p-5">
      <p className="text-[13px] font-semibold text-gray-900">No wireframe for this entry mode</p>
      <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">
        F10 draws manual entry only. Receiving from a suggestion or from an external system has no screen yet.
      </p>
    </Card>
  );
}
