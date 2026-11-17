import "server-only";

import { proposalQueue, taxonomy } from "@/fixtures/categories";

import { fromFixture } from "./source";

export interface TaxonomyNode {
  node_id: string;
  name: string;
  /** 0 for a top-level category, up to 3 (L0 → L3). */
  level: number;
  item_count: number;
  /** Second part of the count line ("3 lines", "manual code LAP-5540", "4 assets → F60"). */
  detail: string | null;
  has_children: boolean;
  /** Child nodes when loaded with this response; null when they load on expand. */
  children: TaxonomyNode[] | null;
}

export interface RejectedProposal {
  proposal_id: string;
  name: string;
  proposed_by: string;
  /** Display string as drawn ("25 Sep"). */
  proposed_on: string;
  /** Requested parent path as drawn ("Spares > Bearings > Ball"). */
  parent_path: string;
  match_percent: number;
  matched_node: string;
}

export interface Taxonomy {
  /** Depth of the active taxonomy. */
  levels: number;
  roots: TaxonomyNode[];
  /** Latest near-duplicate rejection, shown under the tree with its matched node. */
  latest_rejection: RejectedProposal | null;
}

/** F25 taxonomy tree. */
export function getTaxonomy(): Promise<Taxonomy> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/taxonomy",
      note: "Each node needs item count and a short line summary; deeper levels load per parent on expand. The latest near-duplicate rejection with its matched node is shown under the tree.",
    },
    taxonomy,
  );
}

export type ProposalStatus = "under_check" | "pending_approval" | "rejected_duplicate";

export interface TaxonomyProposal {
  proposal_id: string;
  name: string;
  /** Parent the node is proposed under ("Consumables"). */
  parent_name: string;
  proposed_by: string;
  status: ProposalStatus;
  /** Result of the semantic duplicate check, as a line of text. */
  dedupe_note: string;
  /** Approval task to approve or reject, while pending approval. */
  approval_task_id: string | null;
}

/** F25 proposal queue. */
export function listTaxonomyProposals(): Promise<TaxonomyProposal[]> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/taxonomy/proposals",
      note: "Not in the endpoint list (only POST /taxonomy/proposals is); the queue needs status, proposer, parent and the dedupe result. Approve and reject go through the approval task (WF-014).",
    },
    proposalQueue,
  );
}
