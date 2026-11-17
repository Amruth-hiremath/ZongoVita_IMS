"use client";

import {
  Card,
  CardBody,
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
  type Tone,
} from "@ims/ui";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { QuarantineQueue, QuarantineState } from "@/data/quarantine";

const stateTone: Record<QuarantineState, Tone> = {
  due_today: "amber",
  overdue: "red",
  spec_check: "blue",
};

/**
 * Queue, checklist and verdict paths of F32. Selecting a held line that has a checklist shows
 * it; ticks are local until the store's recommendation is written through
 * PUT /ui/v1/returns/{id}/validation.
 */
export function QuarantineBoard({ data, canValidate }: { data: QuarantineQueue; canValidate: boolean }) {
  const [selectedRef, setSelectedRef] = useState(data.selected_ref);
  const [ticks, setTicks] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      data.checklists.flatMap((list) => list.checks.map((check) => [`${list.quarantine_ref}:${check.id}`, check.checked])),
    ),
  );
  const checklist = data.checklists.find((entry) => entry.quarantine_ref === selectedRef);
  const hasChecklist = (ref: string) => data.checklists.some((entry) => entry.quarantine_ref === ref);

  return (
    <div className="mt-3.5 grid grid-cols-[minmax(0,1fr)_412px] gap-6 max-lg:grid-cols-1">
      <div className="min-w-0">
        <SectionLabel>Quarantine hold — nothing here is issuable or free stock</SectionLabel>
        <div className="mt-2">
          <Table className="[&_td]:whitespace-nowrap [&_td]:px-3 [&_th]:px-3">
            <THead>
              <TR>
                <TH>Ref</TH>
                <TH>Item</TH>
                <TH align="center">Qty</TH>
                <TH>Reason</TH>
                <TH>Since</TH>
                <TH>Vendor · PO</TH>
                <TH>State</TH>
              </TR>
            </THead>
            <TBody zebra>
              {data.rows.map((row) => {
                const selectable = hasChecklist(row.quarantine_ref);
                return (
                  <TR
                    key={row.quarantine_ref}
                    aria-selected={selectable ? row.quarantine_ref === selectedRef : undefined}
                    onClick={selectable ? () => setSelectedRef(row.quarantine_ref) : undefined}
                    className={cn("h-12", selectable && "cursor-pointer hover:bg-blue-50")}
                  >
                    <TD>
                      {selectable ? (
                        <button type="button" onClick={() => setSelectedRef(row.quarantine_ref)}>
                          {row.quarantine_ref}
                        </button>
                      ) : (
                        row.quarantine_ref
                      )}
                    </TD>
                    <TD muted>{row.item_name}</TD>
                    <TD align="center">{row.qty_display}</TD>
                    <TD>{row.reason}</TD>
                    <TD muted className="whitespace-nowrap px-1.5">
                      {row.since}
                    </TD>
                    <TD muted className="whitespace-nowrap px-1.5">
                      {row.vendor_po}
                    </TD>
                    <TD className="px-1.5">
                      <Pill small tone={stateTone[row.state.kind]}>
                        {row.state.label}
                      </Pill>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>

        {checklist ? (
          <Card id="validation-checklist" className="mt-9 scroll-mt-6">
            <CardHeader title={checklist.title} />
            <CardBody className="pt-6">
              <ul className="space-y-3">
                {checklist.checks.map((check) => {
                  const key = `${checklist.quarantine_ref}:${check.id}`;
                  return (
                    <li key={key} className="grid grid-cols-[228px_minmax(0,1fr)] items-center gap-2 max-sm:grid-cols-1">
                      <Checkbox
                        checked={ticks[key] ?? false}
                        onChange={(event) => setTicks((current) => ({ ...current, [key]: event.target.checked }))}
                        label={<span className="font-semibold text-gray-900">{check.label}</span>}
                      />
                      <span className="text-[11px] text-gray-500 max-sm:pl-[26px]">{check.detail}</span>
                    </li>
                  );
                })}
              </ul>
              <div className="mt-4 border-t border-gray-200 pt-3">
                <p className="max-w-[520px] text-[11px] leading-4 text-gray-500">{checklist.footnote}</p>
                {canValidate ? (
                  <div className="mt-1 flex flex-wrap justify-end gap-3">
                    <ActionButton variant="danger" endpoint="PUT /ui/v1/returns/{id}/validation">
                      Fail → quality-hold
                    </ActionButton>
                    <ActionButton variant="primary" endpoint="PUT /ui/v1/returns/{id}/validation">
                      Override → restock
                    </ActionButton>
                  </div>
                ) : null}
              </div>
            </CardBody>
          </Card>
        ) : null}
      </div>

      <div className="min-w-0 lg:mt-[22px]">
        <Card className="lg:min-h-[404px]">
          <CardHeader title="Verdict paths" />
          <CardBody className="space-y-4 pt-6">
            {data.verdict_paths.map((path) => (
              <div key={path.label} className="min-h-[116px] rounded-md border-[1.4px] border-gray-300 p-4">
                <Pill tone={path.tone}>{path.label}</Pill>
                <p className="mt-1.5 max-w-[270px] text-[11px] leading-[15px] text-gray-700">{path.body}</p>
              </div>
            ))}
            <p className="max-w-[210px] text-[10.5px] leading-4 text-gray-500">{data.paths_footnote}</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
