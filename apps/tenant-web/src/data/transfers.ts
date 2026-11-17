import "server-only";

import { featuredTransferNo, newTransferDraft, transfers } from "@/fixtures/transfers";

import { fromFixture } from "./source";

/** One point on the transfer's request → approve → dispatch → receive path (F15 stepper). */
export interface TransferStep {
  label: string;
  /** Display line under the label, as drawn ("25 Sep 14:02", "in transit · ETA 27 Sep"). */
  meta: string;
  state: "done" | "current" | "upcoming";
}

export interface TransferPerson {
  name: string;
  /** "Type 3", as the wireframes label the person's user type. */
  type_label: string;
}

export interface TransferLine {
  item_code: string;
  name: string;
  sent_qty: string;
  /** Null until the destination confirms receipt. */
  received_qty: string | null;
  /** Decimal string in the customer's currency. */
  value: string;
}

export interface TransferAuditEntry {
  title: string;
  meta: string;
}

export type StageActionState = "done" | "current" | "if_needed";

export interface TransferStageAction {
  label: string;
  actor: string;
  state: StageActionState;
}

export interface TransferDetail {
  transfer_no: string;
  from_location_code: string;
  to_location_code: string;
  requested_by: TransferPerson;
  approved_by: TransferPerson;
  /** Display timestamp from the frame ("25 Sep 17:30"). */
  dispatched_at_display: string;
  priority: string;
  reason: string;
  steps: TransferStep[];
  lines: TransferLine[];
  audit: TransferAuditEntry[];
  stage_actions: TransferStageAction[];
}

/** F15 Transfer lifecycle, one transfer. Null when the transfer does not exist. */
export function getTransfer(transferNo: string): Promise<TransferDetail | null> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/transfers/{id}",
      note: "Needs the step chain with timestamps, lines with sent and received quantities and value, the transfer's audit entries and the type-aware stage actions (who acts at each step and its state).",
    },
    transfers[transferNo] ?? null,
  );
}

/**
 * The transfer the manager's Transfers entry opens on. The wireframes draw no transfer list,
 * only F15 for one transfer, so the menu entry shows that transfer.
 */
export function getFeaturedTransfer(): Promise<TransferDetail | null> {
  return getTransfer(featuredTransferNo);
}

export interface LocationOption {
  id: string;
  /** "WH-BLR-01 · Bengaluru". */
  label: string;
}

export interface DraftTransferLine {
  item_code: string;
  name: string;
  /** Free stock at the source location: on hand less locked and quarantined units. */
  free_qty: string;
  qty: string;
  batch_no: string | null;
  value: string;
}

export interface NewTransferDraft {
  locations: LocationOption[];
  from_location_id: string;
  to_location_id: string;
  /** Short code of the source location for the "Free at …" column ("BLR-01"). */
  from_location_short: string;
  /** ISO 8601 date. */
  requested_date: string;
  priorities: string[];
  priority: string;
  reasons: string[];
  reason: string;
  /** Approval chain the configured workflow would apply ("Type 2 · Store → Type 2 · Operations"). */
  routing: string;
  lines: DraftTransferLine[];
  notes: string;
}

/** F14 Transfer — New Request, pre-filled as drawn. */
export function getNewTransferDraft(): Promise<NewTransferDraft> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/stock",
      note: "Free stock per source location (locked units excluded) for each line; also needs GET /ui/v1/locations for the from/to lists, GET /ui/v1/reason-codes for reasons, and the routing preview from GET /ui/v1/approval-policies, which no endpoint returns for a draft yet.",
    },
    newTransferDraft,
  );
}
