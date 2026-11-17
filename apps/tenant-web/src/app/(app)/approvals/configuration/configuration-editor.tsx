"use client";

import { Card, Checkbox, KeyValue, NoteBox, Pill, SectionLabel, TBody, TD, TH, THead, TR, Table } from "@ims/ui";
import { Plus, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { ApprovalConfiguration, Escalation } from "@/data/approval-config";

function escalationLabel(escalation: Escalation | null): string {
  return escalation ? `${escalation.after_hours} h → ${escalation.target}` : "—";
}

const wiring = [
  "F05 queue · F15 transfer stepper · F17 variance · F27 approval workspace — all render whatever chain is configured here.",
  "Turning an activity off makes it post instantly, still writing to the immutable audit trail.",
  "Every configuration change is itself audited: who changed which rule, when, from what value.",
];

/**
 * F23 body. On/off, chain steps and options change on the page; "Save configuration" is where
 * Core takes them (PUT /ui/v1/approval-policies/{id}).
 */
export function ConfigurationEditor({ config, canEdit }: { config: ApprovalConfiguration; canEdit: boolean }) {
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(config.activities.map((activity) => [activity.activity_id, activity.enabled])),
  );
  const [chain, setChain] = useState(config.editing.chain);
  const [options, setOptions] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(config.editing.options.map((option) => [option.option_id, option.enabled])),
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_388px] items-start gap-4 max-lg:grid-cols-1">
      <div className="min-w-0">
        <SectionLabel>Activities &amp; chains</SectionLabel>
        <div className="mt-2.5">
          <Table>
            <THead>
              <TR>
                <TH>Activity</TH>
                <TH>Custom workflow</TH>
                <TH>Trigger condition</TH>
                <TH>Escalation</TH>
                <TH align="center">On</TH>
                <TH>
                  <span className="sr-only">Actions</span>
                </TH>
              </TR>
            </THead>
            <TBody zebra>
              {config.activities.map((activity) => {
                const on = enabled[activity.activity_id] ?? false;
                return (
                  <TR key={activity.activity_id}>
                    <TD strong className="h-11">
                      {activity.activity}
                    </TD>
                    <TD muted className="h-11">
                      {activity.workflow_id} · {activity.workflow_label}
                    </TD>
                    <TD muted className="h-11">
                      {activity.trigger_label}
                    </TD>
                    <TD muted className="h-11 whitespace-nowrap">
                      {escalationLabel(activity.escalation)}
                    </TD>
                    <TD align="center" className="h-11 px-1">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={on}
                        aria-label={`${activity.activity} approval ${on ? "on" : "off"}`}
                        disabled={!canEdit}
                        onClick={() => setEnabled((current) => ({ ...current, [activity.activity_id]: !on }))}
                        className="disabled:cursor-not-allowed"
                      >
                        <Pill tone={on ? "green" : "gray"}>{on ? "On" : "Off"}</Pill>
                      </button>
                    </TD>
                    <TD align="right" muted className="h-11">
                      <Link href={`/approvals/workflows/${activity.workflow_id}`} className="hover:text-gray-700">
                        Edit
                      </Link>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>

        <NoteBox tone="gray" className="mt-4 max-w-[724px] px-4 py-3.5">
          <SectionLabel>How it wires into the app</SectionLabel>
          <ul className="mt-2 space-y-2">
            {wiring.map((line) => (
              <li key={line} className="flex gap-2.5 text-[11.5px] leading-4 text-gray-700">
                <span aria-hidden className="mt-1 size-[7px] shrink-0 rounded-full bg-blue-600" />
                {line}
              </li>
            ))}
          </ul>
        </NoteBox>
      </div>

      <div className="flex flex-col gap-6">
        <Card className="p-4">
          <h2 className="text-[13px] font-semibold text-gray-900">Editing: {config.editing.activity}</h2>
          <SectionLabel className="mt-7 text-gray-500">Approval chain</SectionLabel>
          <ol className="mt-2.5 space-y-2">
            {chain.map((step, index) => (
              <li
                key={step.step_no}
                className="flex min-h-14 items-center gap-3 rounded-md border-[1.4px] border-gray-200 bg-gray-50 px-2.5 py-2"
              >
                <span className="flex size-[22px] shrink-0 items-center justify-center rounded-full bg-gray-900 text-[10.5px] font-semibold text-white">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px] font-semibold text-gray-900">{step.approver}</p>
                  <p className="text-[10.5px] text-gray-500">{step.condition}</p>
                </div>
                {canEdit ? (
                  <button
                    type="button"
                    aria-label={`Remove step ${index + 1}`}
                    className="mr-2 text-gray-400 hover:text-gray-700"
                    onClick={() => setChain((current) => current.filter((other) => other.step_no !== step.step_no))}
                  >
                    <X className="size-3.5" strokeWidth={1.6} />
                  </button>
                ) : null}
              </li>
            ))}
          </ol>
          {canEdit ? (
            <ActionButton
              endpoint="PUT /ui/v1/approval-policies/{id}"
              variant="link"
              className="mt-2 h-11 w-full justify-start gap-2.5 rounded-md border-[1.4px] border-dashed border-blue-200 px-4 font-semibold hover:no-underline"
              icon={<Plus aria-hidden className="size-3.5" strokeWidth={2} />}
            >
              Add approver step
            </ActionButton>
          ) : null}
          <div className="mt-5 flex flex-col gap-2.5">
            {config.editing.options.map((option) => (
              <Checkbox
                key={option.option_id}
                label={option.label}
                checked={options[option.option_id] ?? false}
                disabled={!canEdit}
                onChange={(event) =>
                  setOptions((current) => ({ ...current, [option.option_id]: event.target.checked }))
                }
                className="text-[13px]"
              />
            ))}
          </div>
        </Card>

        <Card className="p-4 pb-2">
          <h2 className="text-[13px] font-semibold text-gray-900">Escalation &amp; reminders</h2>
          <dl className="mt-3 space-y-1.5">
            <KeyValue label="Reminder cadence">{config.reminders.reminder_cadence}</KeyValue>
            <KeyValue label="Escalation target">{config.reminders.escalation_target}</KeyValue>
            <KeyValue label="Override rule">{config.reminders.override_rule}</KeyValue>
          </dl>
        </Card>
      </div>
    </div>
  );
}
