"use client";

import {
  Callout,
  Card,
  Field,
  Input,
  NoteBox,
  Pill,
  SectionLabel,
  Select,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from "@ims/ui";
import { Plus, Scan, X } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { IssueDraft, IssueLine } from "@/data/issues";
import { formatDay as formatDate } from "@/lib/dates";
import { formatMoney, formatQty } from "@/lib/format";


/**
 * F11 Issue Stock form. Header fields, line quantities and remarks are editable and lines can be
 * removed; adding a line needs the scan lookup, and posting is the fulfilment-queue complete call.
 * The over-issue check (Q7) is enforced by Core on post; its outcomes are drawn in F12.
 */
export function IssueForm({ draft }: { draft: IssueDraft }) {
  const [lines, setLines] = useState<IssueLine[]>(draft.lines);
  const lock = draft.lock;

  const update = (code: string, patch: Partial<IssueLine>) =>
    setLines((current) => current.map((line) => (line.item_code === code ? { ...line, ...patch } : line)));

  return (
    <>
      <Callout tone="info" dismissible className="-mt-1.5 min-h-[42px]">
        Issuing against {lock.request_ref} — {formatQty(lock.qty)} {lock.uom} {lock.item_code} locked{" "}
        {lock.locked_at_label} · {lock.locked_by} (F28). Free stock shown per line.
      </Callout>

      <div className="mt-3.5 flex flex-wrap gap-5">
        <Field label="Issue no · auto" htmlFor="issue-no" className="w-[150px]">
          <Input id="issue-no" readOnly defaultValue={draft.issue_no} />
        </Field>
        <Field label="Date" htmlFor="issue-date" className="w-[130px]">
          <Input id="issue-date" defaultValue={formatDate(draft.issue_date)} />
        </Field>
        <Field label="Issue from" htmlFor="issue-from" className="w-[200px]">
          <Select id="issue-from" defaultValue={draft.issue_from.value}>
            {draft.issue_from.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Issue to" htmlFor="issue-to" className="w-[240px]">
          <Select id="issue-to" defaultValue={draft.issue_to.value}>
            {draft.issue_to.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Request · lock ref" htmlFor="issue-request" className="w-[200px]">
          <Select id="issue-request" defaultValue={draft.request.value}>
            {draft.request.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <p className="mt-2 text-[11px] text-gray-500">
        Issue-to options: user, production line, retail sale, or a linked Asset Maintenance work order (integration).
      </p>

      <div className="max-w-[976px]">
        <div className="mt-0.5 flex items-center gap-14">
          <SectionLabel>Line items</SectionLabel>
          <ActionButton
            variant="link"
            endpoint="GET /ui/v1/scan/{code}"
            icon={<Scan aria-hidden className="size-3.5" strokeWidth={1.6} />}
            className="text-[11px] font-normal"
          >
            Scan barcode to add a line
          </ActionButton>
        </div>

        <div className="mt-1.5">
          <Table>
            <THead>
              <TR>
                <TH>SKU · scan</TH>
                <TH>Item</TH>
                <TH align="right">Free</TH>
                <TH align="right">Locked</TH>
                <TH>Issue qty</TH>
                <TH align="center">Batch</TH>
                <TH>Remarks</TH>
                <TH>
                  <span className="sr-only">Remove</span>
                </TH>
              </TR>
            </THead>
            <TBody zebra>
              {lines.map((line) => (
                <TR key={line.item_code} className="h-[52px]">
                  <TD className="whitespace-nowrap">{line.item_code}</TD>
                  <TD className="whitespace-nowrap">{line.name}</TD>
                  <TD align="right" numeric>
                    {formatQty(line.free)}
                  </TD>
                  <TD align="right" numeric>
                    {formatQty(line.locked)}
                  </TD>
                  <TD>
                    <Input
                      compact
                      inputMode="decimal"
                      aria-label={`Issue qty for ${line.item_code}`}
                      className="tabular w-16"
                      value={line.issue_qty}
                      onChange={(event) => update(line.item_code, { issue_qty: event.target.value })}
                    />
                  </TD>
                  <TD align="center" className="whitespace-nowrap">
                    {line.batch ?? "—"}
                  </TD>
                  <TD>
                    <Input
                      compact
                      aria-label={`Remarks for ${line.item_code}`}
                      className="w-[144px]"
                      value={line.remarks}
                      onChange={(event) => update(line.item_code, { remarks: event.target.value })}
                    />
                  </TD>
                  <TD align="center">
                    <button
                      type="button"
                      aria-label={`Remove ${line.item_code}`}
                      className="text-gray-500 hover:text-gray-900"
                      onClick={() => setLines((current) => current.filter((l) => l.item_code !== line.item_code))}
                    >
                      <X className="size-3" strokeWidth={1.8} />
                    </button>
                  </TD>
                </TR>
              ))}
              {lines.length === 0 ? (
                <TR>
                  <TD colSpan={8} muted align="center">
                    No lines. Scan or search to add one.
                  </TD>
                </TR>
              ) : null}
            </TBody>
          </Table>
        </div>

        <ActionButton
          variant="link"
          endpoint="GET /ui/v1/scan/{code}"
          icon={<Plus aria-hidden className="size-4" strokeWidth={1.8} />}
          className="mt-1 h-11 w-full justify-start gap-3 rounded-md border-[1.4px] border-dashed border-blue-200 px-5 text-[12.5px] font-semibold hover:no-underline"
        >
          Add line — scan or search (FR-8)
        </ActionButton>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <div className="min-w-0 pt-3">
          <Callout tone="warning" dismissible className="min-h-11">
            Blocked if issue qty &gt; free stock at this location — see state frame F12 (Q7).
          </Callout>
        </div>
        {draft.work_order ? (
          <NoteBox tone="violet" className="min-h-[120px] px-4 py-4">
            <p className="text-[10px] font-semibold text-gray-500">Linked work order</p>
            <p className="mt-1.5 text-[13.5px] font-semibold text-gray-900">
              {draft.work_order.ref} · {draft.work_order.asset}
            </p>
            <p className="mt-1 text-[11.5px] text-gray-500">{draft.work_order.description}</p>
            <Pill tone="violet" className="mt-2 bg-white">
              {draft.work_order.source}
            </Pill>
          </NoteBox>
        ) : null}
      </div>

      <Card className="mt-10 flex flex-wrap items-end justify-between gap-4 bg-gray-50 px-4 py-3.5">
        <div className="min-w-0">
          <p className="text-[11.5px] text-gray-500">This issue will deduct</p>
          <p className="mt-1 text-[13px] font-semibold text-gray-900">
            {draft.deducts.map((part) => `${formatQty(part.qty)} ${part.uom} ${part.label}`).join(" · ")} — lock{" "}
            {lock.request_ref} releases on post
          </p>
        </div>
        <div className="text-right">
          <p className="text-[15px] font-bold text-gray-900">Value {formatMoney(draft.value)}</p>
          <p className="text-[10.5px] text-gray-500">posted to audit + webhook</p>
        </div>
      </Card>
      <p className="mt-4 text-[11px] text-gray-500">
        On post: lock released → stock deducted → {draft.requester} gets the receipt-acknowledgement prompt.
      </p>
    </>
  );
}
