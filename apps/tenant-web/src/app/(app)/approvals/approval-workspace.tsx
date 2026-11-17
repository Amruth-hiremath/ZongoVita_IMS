"use client";

import { formatDay as formatDate } from "@/lib/dates";
import {
  Card,
  CardHeader,
  KeyValue,
  NoteBox,
  PageHeader,
  Pill,
  SectionLabel,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  cn,
  type Tone,
} from "@ims/ui";
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type {
  ApprovalDetail,
  ApprovalQueueRow,
  ApprovalStateKind,
  ApprovalWorkspaceData,
  LockExample,
} from "@/data/approvals";
import { formatQty } from "@/lib/format";

const stateTone: Record<ApprovalStateKind, Tone> = {
  pending_approval: "amber",
  approved_locked: "blue",
  issued_awaiting_ack: "violet",
  rejected_lock_released: "gray",
};


/**
 * F27 Approval Workspace: request queue on the left, the selected request and its lock impact
 * on the right. Selecting a queue row shows that request.
 */
export function ApprovalWorkspace({ data, canApprove }: { data: ApprovalWorkspaceData; canApprove: boolean }) {
  const [selectedRef, setSelectedRef] = useState(data.queue[0]?.request_ref ?? "");
  const selected = data.queue.find((row) => row.request_ref === selectedRef);
  const detail = data.details[selectedRef];
  const pending = data.queue.filter((row) => row.state.kind === "pending_approval").length;
  const canAct = canApprove && selected?.state.kind === "pending_approval";

  return (
    <>
      <PageHeader
        title={`Approval Workspace — ${selectedRef}`}
        actions={
          canAct && selected ? (
            <>
              <ActionButton variant="danger" endpoint={`POST /ui/v1/approval-tasks/${selected.task_id}/reject`}>
                Reject
              </ActionButton>
              <ActionButton variant="primary" endpoint={`POST /ui/v1/approval-tasks/${selected.task_id}/approve`}>
                Approve &amp; lock stock
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="grid grid-cols-1 max-w-[1136px] gap-6 lg:grid-cols-[minmax(0,1fr)_468px]">
        <div className="min-w-0">
          <SectionLabel>Request queue</SectionLabel>
          <div className="mt-2.5">
            <Table>
              <THead>
                <TR>
                  <TH>Ref</TH>
                  <TH>Requester</TH>
                  <TH>Purpose</TH>
                  <TH align="center">Lines</TH>
                  <TH>State</TH>
                </TR>
              </THead>
              <TBody zebra>
                {data.queue.map((row) => (
                  <QueueRow
                    key={row.request_ref}
                    row={row}
                    selected={row.request_ref === selectedRef}
                    onSelect={() => setSelectedRef(row.request_ref)}
                  />
                ))}
              </TBody>
            </Table>
          </div>
          <p className="mt-3 text-[11.5px] text-gray-500">
            {data.queue.length} requests · {pending} pending approval · median wait {data.median_wait} · queue scoped to
            your sites
          </p>

          <LockSemantics example={data.lock_example} />

          <p className="mt-9 text-[11.5px] text-gray-500">
            Approving is a two-sided promise — the requester gets the stock, the inventory loses it from free
            immediately.
          </p>
        </div>

        <div className="min-w-0 lg:pt-6">
          {detail ? <RequestDetail detail={detail} /> : selected ? <RequestSummary row={selected} /> : null}
        </div>
      </div>
    </>
  );
}

function QueueRow({ row, selected, onSelect }: { row: ApprovalQueueRow; selected: boolean; onSelect: () => void }) {
  return (
    <TR aria-selected={selected} onClick={onSelect} className={cn("cursor-pointer", selected && "bg-blue-50!")}>
      <TD>
        <button type="button" onClick={onSelect} className="text-left hover:text-blue-600">
          {row.request_ref}
        </button>
      </TD>
      <TD className="text-[13.5px]">{row.requester}</TD>
      <TD muted>{row.purpose}</TD>
      <TD align="center" muted className="whitespace-nowrap">
        {row.lines_summary}
      </TD>
      <TD>
        <Pill tone={stateTone[row.state.kind]}>{row.state.label}</Pill>
      </TD>
    </TR>
  );
}

function LockSemantics({ example }: { example: LockExample }) {
  return (
    <Card className="mt-7">
      <CardHeader title="Lock semantics — how first-approval works" />
      <div className="px-4 pb-5 pt-6">
        <div className="flex items-stretch gap-2.5 max-md:flex-col">
          <NoteBox tone="blue" className="min-h-[142px] flex-1 px-3.5 py-3">
            <p className="text-[12.5px] font-semibold text-blue-600">1 · Request approved</p>
            <p className="mt-2 text-[12px] leading-4 text-gray-700">
              {example.request_ref} · {formatQty(example.qty)} {example.uom} of {example.item_code}
            </p>
            <p className="mt-3 text-[10.5px] leading-[15px] text-gray-500">
              approval by {example.approver} · {example.approved_at_label}
            </p>
          </NoteBox>
          <StepArrow />
          <NoteBox tone="amber" className="min-h-[142px] flex-1 px-3.5 py-3">
            <p className="text-[12.5px] font-semibold text-amber-700">2 · Units lock instantly</p>
            <p className="mt-2 text-[12px] leading-4 text-gray-700">
              {formatQty(example.qty)} {example.uom} at {example.location_code} move to LOCKED
            </p>
            <p className="mt-3 text-[10.5px] leading-[15px] text-gray-500">
              visible · counted · not issuable elsewhere
            </p>
          </NoteBox>
          <StepArrow />
          <NoteBox tone="green" className="min-h-[142px] flex-1 px-3.5 py-3">
            <p className="text-[12.5px] font-semibold text-green-700">3 · Everyone sees the truth</p>
            <p className="mt-2 text-[12px] leading-4 text-gray-700">
              free stock drops {formatQty(example.free_before)} → {formatQty(example.free_after)}
            </p>
            <p className="mt-7 text-[10.5px] leading-[15px] text-gray-500">second requesters cannot take locked units</p>
          </NoteBox>
        </div>

        <SectionLabel className="mt-8">Release rules</SectionLabel>
        <p className="mt-1.5 text-[12px] leading-4 text-gray-900">
          Lock releases on issue · rejection · cancellation · 48 h timeout — and on nothing else.
          <br />
          Over-issue stays impossible (Q7).
        </p>
      </div>
    </Card>
  );
}

function StepArrow() {
  return (
    <span aria-hidden className="flex shrink-0 items-center justify-center text-gray-500 max-md:rotate-90">
      <ArrowRight className="size-3.5" strokeWidth={1.8} />
    </span>
  );
}

function RequestDetail({ detail }: { detail: ApprovalDetail }) {
  const preview = detail.lock_preview;
  return (
    <>
      <Card>
        <CardHeader title={`${detail.request_ref} · ${detail.requester} · ${detail.department}`} />
        <div className="px-4 pb-4 pt-3">
          <dl className="border-b border-gray-200 pb-5">
            <KeyValue label="Purpose">{detail.purpose}</KeyValue>
            <KeyValue label="Site">{detail.site_label}</KeyValue>
            <KeyValue label="Needed by">{formatDate(detail.needed_by)}</KeyValue>
            <KeyValue label="Raised">{detail.raised_label}</KeyValue>
          </dl>

          {detail.lines.map((line, index) => (
            <div
              key={line.item_code}
              className={cn("py-3.5", index < detail.lines.length - 1 && "border-b border-gray-200")}
            >
              <p className="text-[12.5px] font-semibold text-gray-900">
                {line.item_code} · {line.name} — {formatQty(line.qty)} {line.uom}
              </p>
              {line.kind === "in_stock" ? (
                <>
                  <p className="mt-1 text-[11.5px] text-green-700">
                    Live free:{" "}
                    {line.live_free.map((entry) => `${entry.location_code} ${formatQty(entry.free)}`).join(" · ")}
                  </p>
                  <p className="text-[11.5px] text-gray-500">
                    Approve locks {formatQty(line.qty)} at {line.lock_location_code} → {formatQty(line.free_after_lock)}{" "}
                    remain free
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-1 text-[11.5px] text-red-700">
                    {formatQty(line.free_total)} free across {line.location_count} locations — out of stock
                  </p>
                  <Pill tone="violet" className="mt-2 uppercase">
                    On approve → {line.external_request_ref}
                  </Pill>
                </>
              )}
            </div>
          ))}
        </div>
      </Card>
      <p className="px-4 text-[11px] text-gray-500">unavailable lines leave IMS to the purchasing product (FB-10)</p>

      <Card className="mt-1.5">
        <CardHeader title="Lock impact preview" />
        <div className="px-4 pb-4 pt-5">
          <div className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-1.5 border-b border-gray-200 pb-4">
            <span className="tabular text-[30px] font-bold leading-8 text-gray-900">
              {formatQty(preview.qty)} {preview.uom}
            </span>
            <span className="text-[12.5px] text-gray-700">will lock at {preview.location_code}</span>
            <span className="col-start-2 text-[11px] text-gray-500">the moment you approve</span>
          </div>
          <dl className="pt-1.5">
            <KeyValue label="Free stock before">
              {formatQty(preview.free_before)} {preview.uom}
            </KeyValue>
            <KeyValue label="Free stock after">
              {formatQty(preview.free_after)} {preview.uom}
            </KeyValue>
            <KeyValue label="Other pending requests">{preview.other_pending}</KeyValue>
          </dl>
          <NoteBox tone="blue" className="mt-5 px-4">
            <p className="text-[12.5px] font-semibold text-blue-600">First approval wins (FB-09)</p>
            <p className="mt-0.5 text-[11px] text-gray-500">User 2 can never be issued stock locked against User 1.</p>
          </NoteBox>
        </div>
      </Card>
    </>
  );
}

/** A request the sample data has no line detail for: what the queue row says, nothing more. */
function RequestSummary({ row }: { row: ApprovalQueueRow }) {
  return (
    <Card>
      <CardHeader title={`${row.request_ref} · ${row.requester}`} />
      <div className="px-4 pb-4 pt-3">
        <dl>
          <KeyValue label="Purpose">{row.purpose}</KeyValue>
          <KeyValue label="Lines">{row.lines_summary}</KeyValue>
          <KeyValue label="State">
            <Pill tone={stateTone[row.state.kind]}>{row.state.label}</Pill>
          </KeyValue>
        </dl>
        <p className="mt-3 border-t border-gray-200 pt-3 text-[11.5px] text-gray-500">
          Line availability and the lock impact preview for this request are not in the sample data.
        </p>
      </div>
    </Card>
  );
}
