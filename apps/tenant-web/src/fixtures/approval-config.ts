/** FIXTURE: the configuration drawn in wireframe F23. Temporary; see src/data/source.ts. */
import type { ApprovalActivity, ApprovalConfiguration, Escalation } from "@/data/approval-config";

function activity(
  activity_id: string,
  name: string,
  workflow_id: string,
  workflow_label: string,
  trigger_label: string,
  escalation: Escalation | null,
): ApprovalActivity {
  return { activity_id, activity: name, workflow_id, workflow_label, trigger_label, escalation, enabled: true };
}

export const approvalConfiguration: ApprovalConfiguration = {
  activities: [
    activity("issuance_request", "Issuance request", "WF-011", "lock chain", "every request", {
      after_hours: 24,
      target: "Ops Head",
    }),
    activity("stock_adjustment", "Stock adjustment", "WF-012", "value gate", "value > ₹500", {
      after_hours: 48,
      target: "Ops",
    }),
    activity("transfer", "Transfer", "WF-013", "two-step chain", "every request", { after_hours: 24, target: "Ops" }),
    activity("category_proposal", "Category proposal", "WF-014", "dedupe gate", "every proposal", null),
    activity("item_creation", "Item creation", "WF-015", "catalog guard", "new item · always", null),
    activity("count_variance", "Count variance", "WF-016", "tolerance gate", "±2% or ₹500", {
      after_hours: 48,
      target: "Ops",
    }),
    activity("purchase_order", "Purchase order", "WF-018", "value split", "value > ₹25,000", null),
    activity("scrap_write_off", "Scrap / write-off", "WF-017", "finance route", "always", {
      after_hours: 72,
      target: "Ops",
    }),
  ],
  editing: {
    activity_id: "transfer",
    activity: "Transfer",
    chain: [
      { step_no: 1, approver: "Type 2 · Store", condition: "any location" },
      { step_no: 2, approver: "Type 2 · Operations", condition: "value > ₹5,000 only" },
    ],
    options: [
      { option_id: "skip_below_value", label: "Skip chain below ₹5,000", enabled: true },
      { option_id: "require_challan_scan", label: "Require challan scan on dispatch", enabled: false },
    ],
  },
  reminders: {
    reminder_cadence: "Daily 09:00 IST",
    escalation_target: "Operations Head",
    override_rule: "None — chain is final",
  },
};
