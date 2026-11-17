"use client";

import {
  Button,
  Card,
  CardHeader,
  Checkbox,
  Pill,
  SectionLabel,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  cn,
  type ButtonProps,
  type Tone,
} from "@ims/ui";
import { Check } from "lucide-react";
import { useState, type ReactNode } from "react";

import { ActionButton } from "@/components/action-button";
import type {
  FulfilmentQueueData,
  FulfilmentQueueRow,
  FulfilmentStateKind,
  PickLine,
  PickList,
} from "@/data/fulfilment";
import { formatQty } from "@/lib/format";

const stateTone: Record<FulfilmentStateKind, Tone> = {
  ready_to_pick: "blue",
  picking: "amber",
};

/** Prints the page; the browser's print dialog lists what is on screen. */
export function PrintButton({ children, ...rest }: Omit<ButtonProps, "onClick">) {
  return (
    <Button {...rest} onClick={() => window.print()}>
      {children}
    </Button>
  );
}

/**
 * F29 body: the queue, the pick list of the selected request, the scan station and what an
 * issue sets off. Selecting a queue row shows that request's pick list.
 */
export function FulfilmentWorkspace({ queue }: { queue: FulfilmentQueueData }) {
  const [selectedRef, setSelectedRef] = useState(queue.rows[0]?.request_ref ?? "");
  const selected = queue.rows.find((row) => row.request_ref === selectedRef);
  const pickList = queue.pick_lists[selectedRef];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
      <div className="min-w-0">
        <Table>
          <THead>
            <TR>
              <TH>Ref</TH>
              <TH>Requester</TH>
              <TH>Site</TH>
              <TH align="center">Lines</TH>
              <TH>Locked ago</TH>
              <TH>SLA</TH>
              <TH>State</TH>
            </TR>
          </THead>
          <TBody zebra>
            {queue.rows.map((row) => (
              <QueueRow
                key={row.request_ref}
                row={row}
                selected={row.request_ref === selectedRef}
                onSelect={() => setSelectedRef(row.request_ref)}
              />
            ))}
          </TBody>
        </Table>
        <p className="mt-4 text-[11px] text-gray-500">
          Only unlocked stock can leave the store — the system blocks over-issue at scan, every time (Q7).
        </p>

        {selected ? <NowPicking row={selected} pickList={pickList} /> : null}
      </div>

      <div className="min-w-0 space-y-4">
        <ScanStation />
        <IssueLoop pickList={pickList} />
      </div>
    </div>
  );
}

function QueueRow({ row, selected, onSelect }: { row: FulfilmentQueueRow; selected: boolean; onSelect: () => void }) {
  return (
    <TR aria-selected={selected} onClick={onSelect} className={cn("h-[52px] cursor-pointer", selected && "bg-blue-50!")}>
      <TD className="text-[12.5px]">
        <button type="button" onClick={onSelect} className="text-left hover:text-blue-600">
          {row.request_ref}
        </button>
      </TD>
      <TD className="whitespace-nowrap">{row.requester}</TD>
      <TD muted>{row.site_code}</TD>
      <TD align="center" muted className="whitespace-nowrap">
        {row.lines_summary}
      </TD>
      <TD muted className="whitespace-nowrap">
        {row.locked_label}
      </TD>
      <TD muted className="whitespace-nowrap">
        {row.sla_label}
      </TD>
      <TD>
        <Pill tone={stateTone[row.state.kind]}>{row.state.label}</Pill>
      </TD>
    </TR>
  );
}

function NowPicking({ row, pickList }: { row: FulfilmentQueueRow; pickList: PickList | undefined }) {
  const title = pickList
    ? `Now picking — ${pickList.request_ref} · ${pickList.requester} · ${pickList.department}`
    : `Now picking — ${row.request_ref} · ${row.requester}`;

  return (
    <Card className="mt-5 min-h-[384px]">
      <CardHeader title={title} />
      {pickList ? (
        <div className="px-4 pb-4 pt-7">
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] items-baseline gap-4">
            <SectionLabel>Pick list</SectionLabel>
            <p className="text-[10.5px] text-gray-400">scan each line to verify before issuing</p>
          </div>
          <ul className="mt-2 space-y-3">
            {pickList.lines.map((line) => (
              <PickLineRow key={line.item_code} line={line} />
            ))}
          </ul>
          <p className="mt-3 text-[11px] leading-[17px] text-gray-500">
            The out-of-stock line never reaches this queue — it left IMS as an external purchase-request
            <br className="max-md:hidden" /> event ({externalRefs(pickList).join(", ")}) at approval. The store issues what exists; purchasing handles what doesn&apos;t (FB-10).
          </p>
          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <ActionButton endpoint={`POST /ui/v1/fulfilment-queue/${row.queue_id}/problem (not in the LLD route table)`}>
              Report problem
            </ActionButton>
            <ActionButton variant="primary" endpoint={`POST /ui/v1/fulfilment-queue/${row.queue_id}/complete`}>
              Confirm issue — {formatQty(pickList.issue_qty)} {pickList.issue_uom}
            </ActionButton>
          </div>
        </div>
      ) : (
        <p className="px-4 pb-4 pt-4 text-[11.5px] text-gray-500">
          The pick list for this request ({row.lines_summary}) is not in the sample data.
        </p>
      )}
    </Card>
  );
}

function externalRefs(pickList: PickList): string[] {
  return pickList.lines.flatMap((line) => (line.kind === "external" ? [line.external_request_ref] : []));
}

function PickLineRow({ line }: { line: PickLine }) {
  const stocked = line.kind === "stocked";
  const [checked, setChecked] = useState(false);
  return (
    <li
      className={cn(
        "grid grid-cols-[28px_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] items-center gap-x-3 rounded-md border-[1.4px] px-3.5 py-3 max-sm:grid-cols-[28px_minmax(0,1fr)]",
        stocked && line.scanned ? "border-green-200 bg-green-50" : "border-gray-200 bg-gray-50",
      )}
    >
      <Checkbox
        aria-label={`Picked ${line.item_code}`}
        checked={checked}
        onChange={(event) => setChecked(event.target.checked)}
        className={cn(stocked && line.scanned && "[&>input]:border-blue-600 [&>input]:bg-blue-50")}
      />
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-gray-900">{line.item_code}</p>
        <p className="mt-0.5 text-[11px] text-gray-500">{line.name}</p>
      </div>
      <div className="min-w-0 max-sm:col-start-2">
        <p className="text-[13px] font-semibold text-gray-900">
          {formatQty(line.qty)} {line.uom}
        </p>
        <p className="mt-0.5 text-[11px] text-gray-500">{stocked ? line.lot : "— external purchase —"}</p>
      </div>
      <div className="min-w-0 max-sm:col-start-2">
        {stocked ? (
          <>
            <p className="text-[11.5px] text-gray-700">{line.bin_label}</p>
            {line.scanned ? (
              <p className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-green-700">
                scanned <Check aria-hidden className="size-3" strokeWidth={2.4} />
              </p>
            ) : (
              <p className="mt-1 text-[11px] text-gray-500">not scanned</p>
            )}
          </>
        ) : (
          <>
            <p className="text-[11.5px] text-gray-700">not stocked</p>
            <p className="mt-1 text-[11px] font-semibold text-violet-700">{line.external_request_ref}</p>
          </>
        )}
      </div>
    </li>
  );
}

function ScanStation() {
  return (
    <Card>
      <CardHeader title="Scan & issue station" />
      <div className="px-4 pb-4 pt-5">
        <div className="relative h-[152px] rounded-md border-[1.4px] border-gray-200 bg-gray-50">
          <Corner className="left-3.5 top-3.5 border-l-2 border-t-2" />
          <Corner className="right-3.5 top-3.5 border-r-2 border-t-2" />
          <Corner className="bottom-3.5 left-3.5 border-b-2 border-l-2" />
          <Corner className="bottom-3.5 right-3.5 border-b-2 border-r-2" />
          <span aria-hidden className="absolute inset-x-6 top-[73px] border-t-2 border-dashed border-blue-600" />
          <p className="absolute inset-x-12 bottom-6 text-center text-[11.5px] text-gray-500">
            Align the SKU barcode — issue posts on scan
          </p>
        </div>
        <Barcode className="mx-auto mt-3.5 h-[34px] w-[160px]" />
        <p className="mt-5 text-[10.5px] leading-4 text-gray-500">
          Scan verifies SKU · batch · and that units are unlocked —
          <br className="max-md:hidden" /> then deducts stock and releases the lock atomically.
        </p>
      </div>
    </Card>
  );
}

function Corner({ className }: { className: string }) {
  return <span aria-hidden className={cn("absolute size-7 border-blue-600", className)} />;
}

/** Bar widths (in SVG units) of the decorative barcode under the scan frame. */
const BARS = [3, 1, 2, 1, 1, 3, 2, 1, 1, 2, 3, 1, 1, 1, 2, 1, 3, 2, 1, 1, 2, 1, 1, 3, 1, 2, 2, 1, 3, 1, 1, 2, 1, 1, 2, 3];

function Barcode({ className }: { className?: string }) {
  let x = 0;
  const rects: { x: number; w: number }[] = [];
  BARS.forEach((width, index) => {
    // Even entries are bars, odd entries the gaps between them.
    if (index % 2 === 0) rects.push({ x, w: width });
    x += width;
  });
  return (
    <svg aria-hidden viewBox={`0 0 ${x} 20`} preserveAspectRatio="none" className={className}>
      <rect x="0" y="0" width={x} height="20" className="fill-white" />
      {rects.map((bar) => (
        <rect key={bar.x} x={bar.x} y="0" width={bar.w} height="20" className="fill-gray-900" />
      ))}
    </svg>
  );
}

function IssueLoop({ pickList }: { pickList: PickList | undefined }) {
  const steps: { title: string; meta: ReactNode }[] = [
    {
      title: "Lock released · stock deducted",
      meta: pickList
        ? `${formatQty(pickList.issue_qty)} ${pickList.issue_uom} leave ${pickList.location_code} — audit + webhook fire`
        : "audit + webhook fire",
    },
    {
      title: "Acknowledgement loop starts",
      meta: `${pickList ? pickList.requester : "The requester"} confirms receipt (FB-12)`,
    },
    { title: "Pending acks are reminded", meta: pickList?.ack_reminder_label ?? "" },
    { title: "Sign-off recorded", meta: "who issued what, when — against which request" },
  ];

  return (
    <Card>
      <CardHeader title="Issue closes the loop" />
      <ol className="px-4 pb-6 pt-5">
        {steps.map((step, index) => (
          <li key={step.title} className="relative flex min-h-[68px] gap-3.5 last:min-h-0">
            {index < steps.length - 1 ? (
              <span aria-hidden className="absolute bottom-0 left-[10px] top-6 w-px bg-gray-300" />
            ) : null}
            <span
              className={cn(
                "relative flex size-[22px] shrink-0 items-center justify-center rounded-full border-[1.4px] text-[10.5px] font-semibold",
                index === 0
                  ? "border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep text-white"
                  : "border-gray-300 bg-white text-gray-500",
              )}
            >
              {index + 1}
            </span>
            <div className="min-w-0 pb-4">
              <p className="text-[12.5px] font-semibold text-gray-900">{step.title}</p>
              {step.meta ? <p className="mt-0.5 max-w-[240px] text-[11px] leading-4 text-gray-500">{step.meta}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
