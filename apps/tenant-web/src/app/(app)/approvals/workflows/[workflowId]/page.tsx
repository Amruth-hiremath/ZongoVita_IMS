import { hasPermission } from "@ims/api-client";
import { formatDayShort } from "@/lib/dates";
import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getWorkflow } from "@/data/workflows";
import { requireSession } from "@/session/server";

import { WorkflowBuilder } from "./workflow-builder";

type Params = Promise<{ workflowId: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { workflowId } = await params;
  return { title: `Workflow Builder — ${workflowId}` };
}

/** Column widths of the facts strip as drawn. */
const factWidths = ["w-[152px]", "w-[159px]", "w-[162px]", "w-[197px]", ""];


/** F61 Workflow Builder. */
export default async function WorkflowBuilderPage({ params }: { params: Params }) {
  const { workflowId } = await params;
  const [{ me }, workflow] = await Promise.all([requireSession(), getWorkflow(workflowId)]);
  if (workflow === null) notFound();

  const canEdit = hasPermission(me, "workflow.policy.manage");
  const active = workflow.versions.find((version) => version.status === "active") ?? null;
  const latest = Math.max(0, ...workflow.versions.map((version) => version.version_no));
  const typeLabel = me.user_type_no ? `Type ${me.user_type_no}` : me.role_label;

  const facts: { label: string; value: string }[] = [
    { label: "Applies to", value: workflow.applies_to },
    { label: "Trigger", value: workflow.trigger_label },
    { label: "Condition basis", value: workflow.condition_basis },
    {
      label: "Version",
      value: active ? `v${active.version_no} · active since ${formatDayShort(active.created_on)}` : "—",
    },
    { label: "Editing as", value: `${me.principal.display_name} · ${typeLabel}` },
  ];

  return (
    <>
      <PageHeader
        title={`Workflow Builder — ${workflow.workflow_id} · ${workflow.name}`}
        subtitle="Custom-defined: steps, conditions and escalations are assembled here — no code, applied the moment a version activates (Q3 · NFR-8)"
        actions={
          <>
            {hasPermission(me, "audit.log.view") ? <ButtonLink href="/audit">Version history</ButtonLink> : null}
            {canEdit ? (
              <ActionButton endpoint="PUT /ui/v1/approval-policies/{id}" variant="primary">
                Save &amp; activate v{latest + 1}
              </ActionButton>
            ) : null}
          </>
        }
      />

      <dl className="flex flex-wrap gap-x-6 gap-y-3 rounded-lg border-[1.4px] border-gray-200 bg-gray-50 px-6 py-3.5">
        {facts.map((fact, index) => (
          <div
            key={fact.label}
            className={factWidths[index]}
          >
            <dt className="text-[9.5px] font-semibold uppercase tracking-[0.04em] text-gray-400">{fact.label}</dt>
            <dd className="mt-1 text-[12.5px] text-gray-700">{fact.value}</dd>
          </div>
        ))}
      </dl>

      <WorkflowBuilder workflow={workflow} canEdit={canEdit} nextVersion={latest + 1} />
    </>
  );
}
