import "server-only";

import { issueDraft, issueGuardRails } from "@/fixtures/issues";

import { fromFixture } from "./source";

export interface Option {
  value: string;
  label: string;
}

export interface IssueLine {
  item_code: string;
  name: string;
  free: string;
  locked: string;
  issue_qty: string;
  /** Lot picked for batch-tracked items; null otherwise. */
  batch: string | null;
  remarks: string;
}

export interface IssueDraft {
  /** Fulfilment queue entry the issue completes (POST /ui/v1/fulfilment-queue/{id}/complete). */
  queue_id: string;
  issue_no: string;
  /** ISO 8601 date. */
  issue_date: string;
  issue_from: { value: string; options: Option[] };
  issue_to: { value: string; options: Option[] };
  request: { value: string; options: Option[] };
  /** The lock this issue releases (F28). */
  lock: { request_ref: string; qty: string; uom: string; item_code: string; locked_at_label: string; locked_by: string };
  requester: string;
  lines: IssueLine[];
  /** Linked Asset Maintenance work order (integration). */
  work_order: { ref: string; asset: string; description: string; source: string } | null;
  /** What posting deducts, per line, as the summary prints it. */
  deducts: { qty: string; uom: string; label: string }[];
  /** Decimal string in the customer's currency. */
  value: string;
}

export interface IssueGuardRails {
  /** State A: the line that tripped the negative-stock rule (Q7). */
  blocked: {
    item_code: string;
    name: string;
    location_code: string;
    uom: string;
    free: string;
    requested: string;
    locked: string;
    lock_ref: string;
    on_hand: string;
  };
  /** State B: a concurrent write changed the stock while the form was open (Q20). */
  concurrent: { other_qty: string; uom: string; at_label: string; snapshot_free: string };
  /** State C: the successful post, for contrast. */
  success: { issue_no: string };
}

/** F11 Issue Stock. */
export function getIssueDraft(): Promise<IssueDraft> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/fulfilment-queue",
      note: "The issue form needs the queue entry with its next issue number, issue-from location, issue-to targets (user, production line, retail sale, linked Asset Maintenance work order), the request and lock it releases, and per line the free and locked stock at that location and the lot; line value comes from item cost.",
    },
    issueDraft,
  );
}

/** F12 Issue — guard-rail states. */
export function getIssueGuardRails(): Promise<IssueGuardRails> {
  return fromFixture(
    {
      endpoint: "POST /ui/v1/fulfilment-queue/{id}/complete",
      note: "The three states are this call's outcomes: a problem response for negative stock (Q7) carrying free, locked and on-hand figures; a problem response for a concurrent write (Q20) naming the competing movement; and success.",
    },
    issueGuardRails,
  );
}
