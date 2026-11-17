"use client";

import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  KeyValue,
  Pill,
  SectionLabel,
  Select,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  cn,
} from "@ims/ui";
import { ArrowRight } from "lucide-react";
import { Fragment, useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { ManagerReturns } from "@/data/returns";

import { BulletList, ToneNoteBox, stateTone } from "./parts";

/**
 * Body of F43 below the KPI tiles. Selecting a return that has a quarantine record awaiting
 * verdict shows its verdict panel; the disposition select is local until the verdict is sent.
 */
export function ManagerReturnsBoard({ data, canDecide }: { data: ManagerReturns; canDecide: boolean }) {
  const [selectedRef, setSelectedRef] = useState(data.selected_ref);
  const verdict = data.verdicts.find((entry) => entry.return_ref === selectedRef);
  const hasPanel = (ref: string) => data.verdicts.some((entry) => entry.return_ref === ref);

  return (
    <div className="mt-3.5 grid grid-cols-[minmax(0,1fr)_412px] gap-6 max-lg:grid-cols-1">
      <div className="min-w-0">
        <SectionLabel>Returns in flight — intake to disposition</SectionLabel>
        <div className="mt-2">
          <Table className="[&_td]:whitespace-nowrap [&_td]:px-3 [&_th]:px-3">
            <THead>
              <TR>
                <TH>Ref</TH>
                <TH>Items</TH>
                <TH align="center">Qty</TH>
                <TH>Reason</TH>
                <TH>Returned by</TH>
                <TH>Stage</TH>
                <TH>State</TH>
              </TR>
            </THead>
            <TBody zebra>
              {data.rows.map((row) => {
                const selectable = hasPanel(row.return_ref);
                return (
                  <TR
                    key={row.return_ref}
                    aria-selected={selectable ? row.return_ref === selectedRef : undefined}
                    onClick={selectable ? () => setSelectedRef(row.return_ref) : undefined}
                    className={cn(selectable && "cursor-pointer hover:bg-blue-50")}
                  >
                    <TD>
                      {selectable ? (
                        <button type="button" onClick={() => setSelectedRef(row.return_ref)}>
                          {row.return_ref}
                        </button>
                      ) : (
                        row.return_ref
                      )}
                    </TD>
                    <TD muted>{row.items_summary}</TD>
                    <TD muted align="center">
                      {row.qty_display}
                    </TD>
                    <TD muted>{row.reason}</TD>
                    <TD muted>{row.returned_by}</TD>
                    <TD muted>{row.stage}</TD>
                    <TD>
                      <Pill tone={stateTone[row.state.kind]}>{row.state.label}</Pill>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>

        <Callout tone="warning" dismissible className="mt-5">
          {data.notice}
        </Callout>

        <Card className="mt-5">
          <CardHeader title={data.semantics.title} />
          <CardBody className="pt-3">
            <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)] items-stretch gap-2 max-md:grid-cols-1">
              {data.semantics.steps.map((step, index) => (
                <Fragment key={step.title}>
                  {index > 0 ? (
                    <span aria-hidden className="flex items-center justify-center text-gray-500 max-md:hidden">
                      <ArrowRight className="size-3" strokeWidth={1.8} />
                    </span>
                  ) : null}
                  <ToneNoteBox note={step} className="min-h-[112px]" />
                </Fragment>
              ))}
            </div>
            <p className="mt-2 text-[11.5px] text-gray-700">{data.semantics.footnote}</p>
          </CardBody>
        </Card>
      </div>

      <div className="flex min-w-0 flex-col gap-3 lg:mt-[22px]">
        {verdict ? (
          <Card id="verdict-panel" className="scroll-mt-6">
            <CardHeader title={verdict.title} />
            <CardBody className="pt-1.5">
              <dl>
                {verdict.facts.map((fact) => (
                  <KeyValue key={fact.label} label={fact.label} className="py-[5px] text-[12px]">
                    {fact.value}
                  </KeyValue>
                ))}
              </dl>
              <div className="mt-4 border-t border-gray-200 pt-4">
                <SectionLabel>Store validation</SectionLabel>
                <p className="mt-1 max-w-[260px] text-[11.5px] leading-4 text-gray-700">{verdict.store_validation}</p>
                <label htmlFor="disposition" className="label-caps mb-1.5 mt-3 block">
                  {verdict.disposition_label}
                </label>
                <Select id="disposition" key={verdict.return_ref} defaultValue={verdict.disposition_default}>
                  {verdict.disposition_options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </div>
              {canDecide ? (
                <div className="mt-4 flex flex-wrap justify-center gap-3">
                  <ActionButton variant="danger" endpoint="POST /ui/v1/returns/{id}/verdict">
                    Fail → quality-hold
                  </ActionButton>
                  <ActionButton variant="primary" endpoint="POST /ui/v1/returns/{id}/verdict">
                    Override → restock
                  </ActionButton>
                </div>
              ) : null}
            </CardBody>
          </Card>
        ) : null}

        <Card>
          <CardHeader title={data.attribution.title} />
          <CardBody className="pt-3">
            <p className="text-[11.5px] text-gray-700">{data.attribution.intro}</p>
            <div className="mt-2.5">
              <BulletList bullets={data.attribution.bullets} />
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
