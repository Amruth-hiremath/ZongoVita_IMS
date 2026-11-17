"use client";

import { formatDay } from "@/lib/dates";
import { Card, KeyValue, Pill, Toggle, cn } from "@ims/ui";
import { Check, Clock, Plug, Plus, Send, Users, Zap, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { ApproverStep, FlowNode, WorkflowDetail } from "@/data/workflows";

const palette: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "approver_role", label: "Approver role", icon: Users },
  { id: "condition_split", label: "Condition split", icon: Zap },
  { id: "notify", label: "Notify", icon: Send },
  { id: "escalate", label: "Escalate", icon: Clock },
  { id: "webhook_out", label: "Webhook out", icon: Plug },
];

const guardrails = [
  "Every workflow change is itself audited (F24)",
  "Deactivate = posts instantly, never silent",
  "Conditions re-evaluate per request — nothing cached",
];


function Stub() {
  return <div aria-hidden className="mx-auto h-4 w-px bg-gray-300" />;
}

function StepCard({ step, index }: { step: ApproverStep; index: number }) {
  return (
    <div className="flex min-h-[72px] gap-3 rounded-md border-[1.4px] border-gray-300 bg-white px-3 py-3">
      <span className="mt-1.5 flex size-[22px] shrink-0 items-center justify-center rounded-full bg-gray-900 text-[10.5px] font-semibold text-white">
        {index + 1}
      </span>
      <div className="min-w-0">
        <p className="text-[12.5px] font-semibold text-gray-900">{step.approver}</p>
        <p className="mt-0.5 text-[10.5px] text-gray-500">{step.detail}</p>
        {step.escalation_label ? (
          <Pill tone="amber" small className="mt-1.5 border-amber-200 bg-amber-100">
            {step.escalation_label}
          </Pill>
        ) : null}
      </div>
    </div>
  );
}

function Outcome({ node, tone }: { node: FlowNode; tone: "green" | "gray" }) {
  return (
    <div
      className={cn(
        "rounded-md border-[1.4px] px-4 py-3",
        tone === "green" ? "border-green-200 bg-green-50" : "min-h-[72px] border-gray-200 bg-gray-50",
      )}
    >
      <p className={cn("text-[12.5px] font-semibold", tone === "green" ? "text-green-700" : "text-gray-900")}>
        {node.title}
      </p>
      <p className="mt-1 text-[10.5px] text-gray-500">{node.detail}</p>
    </div>
  );
}

/**
 * F61 canvas and side panels. Choosing a palette tile and the Active switch work on the page;
 * changing the graph itself is a new policy version (PUT /ui/v1/approval-policies/{id}).
 */
export function WorkflowBuilder({
  workflow,
  canEdit,
  nextVersion,
}: {
  workflow: WorkflowDetail;
  canEdit: boolean;
  nextVersion: number;
}) {
  const [tile, setTile] = useState<string | null>(null);
  const [active, setActive] = useState(workflow.active);
  const { canvas } = workflow;
  const activeVersion = workflow.versions.find((version) => version.status === "active");
  const approverCount = canvas.yes_branch.steps.length + canvas.no_branch.steps.length;
  const basis = workflow.condition_basis.charAt(0).toLowerCase() + workflow.condition_basis.slice(1);

  return (
    <div className="mt-6 grid grid-cols-[minmax(0,1fr)_412px] items-start gap-4 max-lg:grid-cols-1">
      <Card className="min-w-0 p-4">
        <h2 className="text-[13px] font-semibold text-gray-900">
          Builder canvas — {workflow.workflow_id} · {workflow.name}
        </h2>
        <p className="mt-1.5 text-[9.5px] font-semibold uppercase tracking-[0.04em] text-gray-400">
          Step palette — click a tile, then the canvas to insert
        </p>
        <div className="mt-2 grid grid-cols-5 gap-2 max-sm:grid-cols-2">
          {palette.map((entry) => {
            const Icon = entry.icon;
            const selected = tile === entry.id;
            return (
              <button
                key={entry.id}
                type="button"
                aria-pressed={selected}
                disabled={!canEdit}
                onClick={() => setTile(selected ? null : entry.id)}
                className={cn(
                  "flex h-14 flex-col items-center justify-center gap-1.5 rounded-md border-[1.4px] text-[11px] font-semibold text-blue-600 disabled:cursor-not-allowed",
                  selected ? "border-blue-600 bg-blue-50" : "border-dashed border-blue-200 bg-white",
                )}
              >
                <Icon aria-hidden className="size-3.5" strokeWidth={1.8} />
                {entry.label}
              </button>
            );
          })}
        </div>

        <div className="mt-4 border-t border-gray-200 pt-4">
          <div className="mx-auto max-w-[440px] rounded-md bg-gray-900 px-4 py-2.5">
            <p className="text-[12.5px] font-semibold text-white">TRIGGER — {canvas.trigger.title}</p>
            <p className="mt-0.5 text-[10.5px] text-gray-300">{canvas.trigger.detail}</p>
          </div>
          <Stub />
          <div className="mx-auto max-w-[440px] rounded-md border-[1.4px] border-blue-200 bg-blue-50 px-4 py-2.5">
            <p className="text-[12.5px] font-semibold text-blue-600">CONDITION — {canvas.condition.title}</p>
            <p className="mt-1 text-[10.5px] text-gray-500">{canvas.condition.detail}</p>
          </div>
          <Stub />

          <div className="relative grid grid-cols-2 gap-x-16 gap-y-6 max-sm:grid-cols-1">
            <span
              aria-hidden
              className="absolute left-[calc((100%_-_4rem)/4)] right-[calc((100%_-_4rem)/4)] top-0 h-px bg-gray-300 max-sm:hidden"
            />
            <div className="min-w-0">
              <Stub />
              <div className="flex justify-center">
                <Pill tone="blue" small className="h-[22px] px-4 text-[11px]">
                  {canvas.yes_branch.label}
                </Pill>
              </div>
              <div className="mt-1.5">
                {canvas.yes_branch.steps.map((step, index) => (
                  <div key={step.step_no}>
                    {index > 0 ? <Stub /> : null}
                    <StepCard step={step} index={index} />
                  </div>
                ))}
                <Stub />
                <Outcome node={canvas.yes_branch.outcome} tone="green" />
              </div>
            </div>

            <div className="min-w-0">
              <Stub />
              <div className="flex justify-center">
                <Pill tone="gray" small className="h-[22px] px-3 text-[11px]">
                  {canvas.no_branch.label}
                </Pill>
              </div>
              <div className="mt-1.5">
                {canvas.no_branch.steps.map((step, index) => (
                  <div key={step.step_no} className="mb-4">
                    <StepCard step={step} index={index} />
                  </div>
                ))}
                <Outcome node={canvas.no_branch.outcome} tone="gray" />
                {canEdit ? (
                  <ActionButton
                    endpoint="PUT /ui/v1/approval-policies/{id}"
                    variant="link"
                    className="mt-4 h-11 w-full justify-start gap-2.5 rounded-md border-[1.4px] border-dashed border-blue-200 px-4 font-semibold hover:no-underline"
                    icon={<Plus aria-hidden className="size-3.5" strokeWidth={2} />}
                  >
                    Add a step to this path
                  </ActionButton>
                ) : null}
                <p className="mt-4 max-w-[210px] text-[10.5px] leading-4 text-gray-500">{canvas.no_branch.note}</p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div className="flex flex-col gap-4">
        <Card className="p-4">
          <h2 className="text-[13px] font-semibold text-gray-900">Workflow settings</h2>
          <dl className="mt-3 space-y-1.5 pr-4">
            <KeyValue label="Name">
              {workflow.workflow_id} · {workflow.name}
            </KeyValue>
            <KeyValue label="Applies to">{workflow.applies_to}</KeyValue>
            <KeyValue label="Condition basis">{basis}</KeyValue>
            <KeyValue label="Steps">
              {approverCount} approvers · 1 condition
            </KeyValue>
          </dl>
          <Toggle
            className="mt-9"
            checked={active}
            disabled={!canEdit}
            onChange={(event) => setActive(event.target.checked)}
            label={`${active ? "Active" : "Inactive"} — v${activeVersion?.version_no ?? nextVersion - 1}`}
          />
        </Card>

        <Card className="p-4 pb-3">
          <h2 className="text-[13px] font-semibold text-gray-900">Versions</h2>
          <ul className="mt-3 space-y-2">
            {workflow.versions.map((version) => (
              <li key={version.version_no} className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[12px]">
                    <span className="inline-block w-10 font-semibold text-gray-900">v{version.version_no}</span>
                    <span className="text-gray-500">{formatDay(version.created_on)}</span>
                  </p>
                  <p className="text-[10.5px] text-gray-500">{version.summary}</p>
                </div>
                {version.status === "active" ? (
                  <Pill tone="green" className="mt-1">
                    Active
                  </Pill>
                ) : (
                  <Pill tone="gray" className="mt-1">
                    {version.status === "replaced" ? "Replaced" : "Draft"}
                  </Pill>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-0.5 text-[10px] text-gray-400">
            Saving creates v{nextVersion} · roll back within {workflow.rollback_days} days.
          </p>
        </Card>

        <Card className="p-4">
          <h2 className="text-[13px] font-semibold text-gray-900">Guardrails</h2>
          <ul className="mt-4 space-y-3.5">
            {guardrails.map((line) => (
              <li key={line} className="flex gap-2.5 text-[11px] text-gray-700">
                <Check aria-hidden className="mt-1 size-3 shrink-0 text-green-600" strokeWidth={2} />
                {line}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
