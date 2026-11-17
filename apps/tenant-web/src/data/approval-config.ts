import "server-only";

import { approvalConfiguration } from "@/fixtures/approval-config";

import { fromFixture } from "./source";

export interface Escalation {
  after_hours: number;
  /** Who the task escalates to ("Ops Head", "Ops"). */
  target: string;
}

export interface ApprovalActivity {
  activity_id: string;
  /** "Issuance request", "Transfer". */
  activity: string;
  /** Custom workflow bound to the activity ("WF-013"); opens in the Workflow Builder (F61). */
  workflow_id: string;
  /** Short description of the workflow ("two-step chain"). */
  workflow_label: string;
  /** When the workflow runs, as configured ("every request", "value > ₹500"). */
  trigger_label: string;
  escalation: Escalation | null;
  /** Off: the activity posts instantly, still audited. */
  enabled: boolean;
}

export interface ChainStep {
  step_no: number;
  /** Approver role ("Type 2 · Store"). */
  approver: string;
  /** Scope or condition of the step ("any location", "value > ₹5,000 only"). */
  condition: string;
}

export interface ChainOption {
  option_id: string;
  label: string;
  enabled: boolean;
}

export interface ApprovalConfiguration {
  activities: ApprovalActivity[];
  /** The activity whose chain is open in the side panel. */
  editing: { activity_id: string; activity: string; chain: ChainStep[]; options: ChainOption[] };
  reminders: { reminder_cadence: string; escalation_target: string; override_rule: string };
}

/** F23 Approval Workflow Configuration. */
export function getApprovalConfiguration(): Promise<ApprovalConfiguration> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/approval-policies",
      note:
        "One policy per activity with its workflow id, trigger condition, escalation and on/off state; the chain " +
        "of the selected policy with its options; and the tenant-wide reminder cadence, escalation target and override rule.",
    },
    approvalConfiguration,
  );
}
