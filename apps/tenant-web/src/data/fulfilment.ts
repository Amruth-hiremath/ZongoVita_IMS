import "server-only";

import { fulfilmentQueue } from "@/fixtures/fulfilment";

import { fromFixture } from "./source";

export type FulfilmentStateKind = "ready_to_pick" | "picking";

export interface FulfilmentQueueRow {
  /** Queue entry id, used by POST /ui/v1/fulfilment-queue/{id}/scans and /complete. */
  queue_id: string;
  request_ref: string;
  requester: string;
  site_code: string;
  lines_summary: string;
  /** Display strings from the frame ("10:12 today", "Today 17:00"). */
  locked_label: string;
  sla_label: string;
  state: { kind: FulfilmentStateKind; label: string };
}

/** A line the store holds: picked from a bin and verified by scan. */
export interface PickLineStocked {
  kind: "stocked";
  item_code: string;
  name: string;
  qty: string;
  uom: string;
  lot: string;
  bin_label: string;
  scanned: boolean;
}

/** A line that was out of stock at approval and left IMS as an external purchase request (FB-10). */
export interface PickLineExternal {
  kind: "external";
  item_code: string;
  name: string;
  qty: string;
  uom: string;
  external_request_ref: string;
}

export type PickLine = PickLineStocked | PickLineExternal;

export interface PickList {
  request_ref: string;
  requester: string;
  department: string;
  location_code: string;
  lines: PickLine[];
  /** Total the store will issue, per UoM. */
  issue_qty: string;
  issue_uom: string;
  /** Acknowledgement reminder rule as configured (customer setting). */
  ack_reminder_label: string;
}

export interface FulfilmentQueueData {
  rows: FulfilmentQueueRow[];
  /** Pick lists per request ref; only the requests the sample data covers. */
  pick_lists: Record<string, PickList>;
}

/** F29 Store Fulfilment Queue. */
export function getFulfilmentQueue(): Promise<FulfilmentQueueData> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/fulfilment-queue",
      note: "Rows need the lock time and SLA; each entry needs its pick list with lot and bin per stocked line, scan status, and lines that left as external purchase requests (FB-10) with their reference; the acknowledgement reminder rule comes from GET /ui/v1/settings.",
    },
    fulfilmentQueue,
  );
}
