"use client";

import {
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
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { StoreReturns } from "@/data/returns";

import { BulletList, ToneNoteBox, stateTone } from "./parts";

/**
 * Body of F49 below the KPI tiles. Selecting a return that is being validated shows its
 * validation panel; the recommendation select is local until it is written.
 */
export function StoreReturnsBoard({ data, canValidate }: { data: StoreReturns; canValidate: boolean }) {
  const [selectedRef, setSelectedRef] = useState(data.selected_ref);
  const validation = data.validations.find((entry) => entry.return_ref === selectedRef);
  const hasPanel = (ref: string) => data.validations.some((entry) => entry.return_ref === ref);

  return (
    <div className="mt-3.5 grid grid-cols-[minmax(0,1fr)_412px] gap-6 max-lg:grid-cols-1">
      <div className="min-w-0">
        <SectionLabel>Returns in flight — intake to disposition, your queue</SectionLabel>
        <div className="mt-2">
          <Table className="[&_td]:whitespace-nowrap [&_td]:px-3 [&_th]:px-3">
            <THead>
              <TR>
                <TH>Ref</TH>
                <TH>Items</TH>
                <TH align="center">Qty</TH>
                <TH>Reason</TH>
                <TH>Returned by</TH>
                <TH>Store action</TH>
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
                    className={cn("h-12", selectable && "cursor-pointer hover:bg-blue-50")}
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

        <Card className="mt-[30px]">
          <CardHeader title={data.routing.title} />
          <CardBody className="grid grid-cols-2 gap-4 pt-2.5 max-md:grid-cols-1">
            {data.routing.routes.map((route) => (
              <ToneNoteBox key={route.title} note={route} className="min-h-[82px]" />
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="flex min-w-0 flex-col gap-3 lg:mt-[22px]">
        {validation ? (
          <Card id="validation-panel" className="scroll-mt-6">
            <CardHeader title={validation.title} />
            <CardBody className="pt-1.5">
              <dl>
                {validation.facts.map((fact) => (
                  <KeyValue key={fact.label} label={fact.label} className="py-[5px] text-[12px]">
                    {fact.value}
                  </KeyValue>
                ))}
              </dl>
              <div className="mt-4 border-t border-gray-200 pt-4">
                <SectionLabel>Store check</SectionLabel>
                <p className="mt-1 max-w-[260px] text-[11.5px] leading-4 text-gray-700">{validation.store_check}</p>
                <label htmlFor="recommendation" className="label-caps mb-1.5 mt-3 block">
                  Recommendation
                </label>
                <Select
                  id="recommendation"
                  key={validation.return_ref}
                  defaultValue={validation.recommendation_default}
                >
                  {validation.recommendation_options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </div>
              {canValidate ? (
                <div className="mt-4 flex flex-wrap justify-center gap-3 pb-6">
                  <ActionButton endpoint="PUT /ui/v1/returns/{id}/validation (photo evidence)">
                    Attach photos
                  </ActionButton>
                  <ActionButton variant="primary" endpoint="PUT /ui/v1/returns/{id}/validation">
                    Write recommendation
                  </ActionButton>
                </div>
              ) : null}
            </CardBody>
          </Card>
        ) : null}

        <Card>
          <CardHeader title={data.never_back.title} />
          <CardBody className="pt-3">
            <p className="max-w-[300px] text-[11.5px] leading-4 text-gray-700">{data.never_back.intro}</p>
            <div className="mt-3">
              <BulletList bullets={data.never_back.bullets} />
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
