import "server-only";

import { workflows } from "@/fixtures/workflows";

import { fromFixture } from "./source";

export interface FlowNode {
  title: string;
  detail: string;
}

export interface ApproverStep {
  step_no: number;
  /** Approver role ("Type 2 · Store"). */
  approver: string;
  detail: string;
  /** Escalation shown on the step ("24 h → Ops Head"), if any. */
  escalation_label: string | null;
}

export interface WorkflowVersion {
  version_no: number;
  /** ISO date the version was created. */
  created_on: string;
  summary: string;
  status: "active" | "replaced" | "draft";
}

export interface WorkflowDetail {
  workflow_id: string;
  name: string;
  /** "Transfers (F14)". */
  applies_to: string;
  /** "Request submitted". */
  trigger_label: string;
  /** "Request value (₹)". */
  condition_basis: string;
  active: boolean;
  /** Days within which a replaced version can be rolled back to. */
  rollback_days: number;
  canvas: {
    trigger: FlowNode;
    condition: FlowNode;
    yes_branch: { label: string; steps: ApproverStep[]; outcome: FlowNode };
    no_branch: { label: string; steps: ApproverStep[]; outcome: FlowNode; note: string };
  };
  versions: WorkflowVersion[];
}

/** F61 Workflow Builder. Null when no such workflow exists. */
export function getWorkflow(workflowId: string): Promise<WorkflowDetail | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/approval-policies/{id}",
      note:
        "The builder needs the policy as a graph (trigger, condition split, approver steps per branch, outcomes) " +
        "plus its version history; the LLD describes policies as chains, so the branch shape is to be confirmed.",
    },
    workflows[workflowId] ?? null,
  );
}
