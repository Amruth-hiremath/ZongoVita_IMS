"use client";

import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Field,
  Input,
  NoteBox,
  PageHeader,
  SectionLabel,
  Select,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Textarea,
} from "@ims/ui";
import { ArrowRight, Plus, X } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { DraftTransferLine, NewTransferDraft } from "@/data/transfers";
import { formatQty } from "@/lib/format";

interface EditableLine extends DraftTransferLine {
  key: string;
  /** Added on this page and not yet resolved to an item. */
  added: boolean;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09-26" -> "26 Sep 2026", as the frame writes dates. */
function formatDay(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

/**
 * F14 Transfer — New Request. Lines can be added, edited and removed on the page; saving and
 * submitting need the transfers endpoints. Free stock and value come from Core per line.
 */
export function TransferRequest({ draft, canCreate }: { draft: NewTransferDraft; canCreate: boolean }) {
  const [lines, setLines] = useState<EditableLine[]>(() =>
    draft.lines.map((line) => ({ ...line, key: line.item_code, added: false })),
  );
  const [nextKey, setNextKey] = useState(1);

  const update = (key: string, patch: Partial<EditableLine>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));

  const addLine = () => {
    setLines((current) => [
      ...current,
      { key: `new-${nextKey}`, added: true, item_code: "", name: "", free_qty: "", qty: "", batch_no: null, value: "" },
    ]);
    setNextKey((key) => key + 1);
  };

  return (
    <>
      <PageHeader
        className="mb-5 items-center"
        title="Transfer — New Request"
        actions={
          canCreate ? (
            <>
              <ActionButton endpoint="POST /ui/v1/transfers">Save draft</ActionButton>
              <ActionButton variant="primary" endpoint="POST /ui/v1/transfers/{id}/submit">
                Send for approval
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="flex flex-wrap items-end gap-x-5 gap-y-4">
        <Field label="From location" htmlFor="transfer-from" className="w-[230px] max-sm:w-full">
          <Select id="transfer-from" defaultValue={draft.from_location_id}>
            {draft.locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.label}
              </option>
            ))}
          </Select>
        </Field>
        <ArrowRight aria-hidden className="mb-3 size-4 text-blue-600 max-sm:hidden" strokeWidth={2} />
        <Field label="To location" htmlFor="transfer-to" className="w-[230px] max-sm:w-full">
          <Select id="transfer-to" defaultValue={draft.to_location_id}>
            {draft.locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Requested date" htmlFor="transfer-date" className="w-[140px]">
          <Input id="transfer-date" defaultValue={formatDay(draft.requested_date)} />
        </Field>
        <Field label="Priority" htmlFor="transfer-priority" className="w-[140px]">
          <Select id="transfer-priority" defaultValue={draft.priority}>
            {draft.priorities.map((priority) => (
              <option key={priority}>{priority}</option>
            ))}
          </Select>
        </Field>
        <Field label="Reason" htmlFor="transfer-reason" className="w-[180px]">
          <Select id="transfer-reason" defaultValue={draft.reason}>
            {draft.reasons.map((reason) => (
              <option key={reason}>{reason}</option>
            ))}
          </Select>
        </Field>
      </div>

      <Callout dismissible className="mt-10">
        Routing for this request: {draft.routing} (from the configurable workflow, F23 · Q3).
      </Callout>

      <SectionLabel className="mt-4">Items to move</SectionLabel>
      <div className="mt-2 max-w-[940px]">
        <Table>
          <THead>
            <TR>
              <TH>SKU · scan</TH>
              <TH>Item</TH>
              <TH align="right">Free at {draft.from_location_short}</TH>
              <TH>Transfer qty</TH>
              <TH align="center">Batch</TH>
              <TH align="right">Value (₹)</TH>
              <TH>
                <span className="sr-only">Remove</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {lines.map((line) => (
              <TR key={line.key}>
                <TD className="w-[150px]">
                  {line.added ? (
                    <Input
                      compact
                      aria-label="SKU"
                      placeholder="Scan or type SKU"
                      value={line.item_code}
                      onChange={(event) => update(line.key, { item_code: event.target.value })}
                    />
                  ) : (
                    line.item_code
                  )}
                </TD>
                <TD>{line.name || <span className="text-gray-400">—</span>}</TD>
                <TD align="right" numeric>
                  {line.free_qty ? formatQty(line.free_qty) : "—"}
                </TD>
                <TD className="w-[110px]">
                  <Input
                    compact
                    inputMode="decimal"
                    aria-label={`Transfer quantity${line.item_code ? ` of ${line.item_code}` : ""}`}
                    value={line.qty}
                    onChange={(event) => update(line.key, { qty: event.target.value })}
                    className="w-[82px] tabular"
                  />
                </TD>
                <TD align="center">{line.batch_no ?? "—"}</TD>
                <TD align="right" numeric>
                  {line.value ? formatQty(line.value) : "—"}
                </TD>
                <TD align="center" className="w-12">
                  <button
                    type="button"
                    aria-label={`Remove ${line.item_code || "line"}`}
                    className="text-gray-500 hover:text-gray-900"
                    onClick={() => setLines((current) => current.filter((other) => other.key !== line.key))}
                  >
                    <X aria-hidden className="size-3" strokeWidth={1.8} />
                  </button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
        <button
          type="button"
          onClick={addLine}
          className="flex h-11 w-full items-center gap-3 rounded-md border-[1.4px] border-dashed border-blue-200 px-5 text-left text-[12.5px] font-semibold text-blue-600 hover:bg-blue-50"
        >
          <Plus aria-hidden className="size-4 shrink-0" strokeWidth={1.8} />
          Add line — free stock is shown live per source location (locked units excluded)
        </button>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1fr)_408px]">
        <NoteBox tone="gray" className="px-4 py-4">
          <SectionLabel>What happens on approval</SectionLabel>
          <ul className="mt-2 space-y-1.5 text-[12px] text-gray-700">
            {[
              "Approval granted → qty becomes reserved at source (not issued yet)",
              "Dispatch → stock leaves source, becomes in-transit",
              "Receive at destination → stock becomes available there",
            ].map((text) => (
              <li key={text} className="flex items-center gap-2.5">
                <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-blue-600" />
                {text}
              </li>
            ))}
          </ul>
        </NoteBox>
        <Card>
          <CardHeader title="Notes for approver" />
          <CardBody className="pt-2">
            <Textarea
              aria-label="Notes for approver"
              defaultValue={draft.notes}
              className="min-h-[60px] text-[11.5px] text-gray-600"
            />
          </CardBody>
        </Card>
      </div>
    </>
  );
}
