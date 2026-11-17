/** FIXTURE: the workflow drawn in wireframe F61. Temporary; see src/data/source.ts. */
import type { WorkflowDetail } from "@/data/workflows";

export const workflows: Record<string, WorkflowDetail> = {
  "WF-013": {
    workflow_id: "WF-013",
    name: "Transfer approval",
    applies_to: "Transfers (F14)",
    trigger_label: "Request submitted",
    condition_basis: "Request value (₹)",
    active: true,
    rollback_days: 30,
    canvas: {
      trigger: { title: "transfer request submitted", detail: "any user with transfer rights (F14)" },
      condition: { title: "request value > ₹5,000?", detail: "evaluated per request — never cached" },
      yes_branch: {
        label: "YES — value > ₹5,000",
        steps: [
          {
            step_no: 1,
            approver: "Type 2 · Store",
            detail: "approves for any location",
            escalation_label: "24 h → Ops Head",
          },
          {
            step_no: 2,
            approver: "Type 2 · Operations",
            detail: "second signature if value > ₹25,000",
            escalation_label: null,
          },
        ],
        outcome: { title: "POSTED — stock moves · audited", detail: "transfer stepper advances (F15)" },
      },
      no_branch: {
        label: "NO — at or below",
        steps: [],
        outcome: { title: "POSTS INSTANTLY", detail: "no approver · still audited (F24)" },
        note: "Both paths end in the immutable trail — a rejected request releases locks exactly as today (F12).",
      },
    },
    versions: [
      { version_no: 3, created_on: "2026-09-12", summary: "Store → Ops (value split)", status: "active" },
      { version_no: 2, created_on: "2026-06-04", summary: "single step · Store only", status: "replaced" },
      { version_no: 1, created_on: "2024-01-12", summary: "seeded default", status: "replaced" },
    ],
  },
};
