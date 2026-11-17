import { hasPermission } from "@ims/api-client";
import { Card, PageHeader, Pill, type Tone } from "@ims/ui";
import { Plus } from "lucide-react";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getTaxonomy, listTaxonomyProposals, type ProposalStatus } from "@/data/categories";
import { requireSession } from "@/session/server";

import { TaxonomyTree } from "./taxonomy-tree";

export const metadata: Metadata = { title: "Category & Subcategory Management" };

const statusPill: Record<ProposalStatus, { tone: Tone; label: string }> = {
  under_check: { tone: "blue", label: "Under check" },
  pending_approval: { tone: "amber", label: "Pending approval" },
  rejected_duplicate: { tone: "red", label: "Rejected · duplicate" },
};

const governance = [
  "Propose → semantic dedupe → approval → active — no silent taxonomy changes",
  "Category alone is too broad: the taxonomy is two-level by design",
  "Dedupe re-runs on every later proposal as the taxonomy grows",
  "Approved nodes appear in item-registration dropdowns tenant-wide",
];

/** F25 Category & Subcategory Management. */
export default async function CategoriesPage() {
  const [{ me }, taxonomy, proposals] = await Promise.all([requireSession(), getTaxonomy(), listTaxonomyProposals()]);
  const canPropose = hasPermission(me, "catalog.taxonomy.propose");
  const canApprove = hasPermission(me, "catalog.taxonomy.approve");
  const rejection = taxonomy.latest_rejection;

  return (
    <>
      <PageHeader
        title="Category & Subcategory Management"
        subtitle="Two-level taxonomy as configuration — proposals pass a semantic duplicate check and approval before activation"
        actions={
          <>
            {hasPermission(me, "reporting.export.run") ? (
              <ActionButton endpoint="POST /ui/v1/exports">Export taxonomy</ActionButton>
            ) : null}
            {canPropose ? (
              <ActionButton endpoint="POST /ui/v1/taxonomy/proposals" variant="primary">
                + Propose category
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)_412px] items-start gap-6 max-lg:grid-cols-1">
        <Card className="min-w-0 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-[13px] font-semibold text-gray-900">Taxonomy — active · {taxonomy.levels} levels</h2>
            <Pill tone="blue">L0 → L{taxonomy.levels - 1}</Pill>
          </div>
          <TaxonomyTree roots={taxonomy.roots} />
          {rejection ? (
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border-[1.4px] border-dashed border-red-200 px-4 py-2">
              <Plus aria-hidden className="size-3.5 shrink-0 text-red-600" strokeWidth={2} />
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] text-gray-700">{rejection.name}</p>
                <p className="text-[9.5px] text-gray-400">
                  proposed by {rejection.proposed_by} · {rejection.proposed_on} · {rejection.parent_path}
                </p>
              </div>
              <Pill tone="red" className="mr-20 max-sm:mr-0">
                {rejection.match_percent}% match → {rejection.matched_node}
              </Pill>
            </div>
          ) : null}
          <p className="mt-3 text-[10.5px] leading-4 text-gray-500">
            Near-duplicate proposals are rejected with the matched node attached — the system suggests reuse instead of
            proliferation at every level.
          </p>
        </Card>

        <div className="flex flex-col gap-5">
          <Card className="min-h-[316px] p-4">
            <h2 className="text-[13px] font-semibold text-gray-900">Proposal queue</h2>
            <ul className="mt-4 space-y-4">
              {proposals.map((proposal) => (
                <li key={proposal.proposal_id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[12.5px] font-semibold text-gray-900">{proposal.name}</p>
                      <p className="mt-0.5 text-[10.5px] text-gray-500">
                        {proposal.parent_name} · by {proposal.proposed_by}
                      </p>
                      <p className="text-[9.5px] text-gray-400">{proposal.dedupe_note}</p>
                    </div>
                    <Pill tone={statusPill[proposal.status].tone} className="shrink-0">
                      {statusPill[proposal.status].label}
                    </Pill>
                  </div>
                  {proposal.status === "pending_approval" && proposal.approval_task_id && canApprove ? (
                    <div className="mt-1 flex justify-end gap-3">
                      <ActionButton endpoint="POST /ui/v1/approval-tasks/{id}/reject" className="w-[82px]">
                        Reject
                      </ActionButton>
                      <ActionButton
                        endpoint="POST /ui/v1/approval-tasks/{id}/approve"
                        variant="primary"
                        className="w-[98px]"
                      >
                        Approve
                      </ActionButton>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="p-4">
            <h2 className="text-[13px] font-semibold text-gray-900">Governance rules</h2>
            <ul className="mt-4 space-y-3.5">
              {governance.map((line) => (
                <li key={line} className="flex gap-3 text-[11.5px] leading-4 text-gray-700">
                  <span aria-hidden className="mt-1 size-[7px] shrink-0 rounded-full bg-blue-600" />
                  <span className="max-w-[280px]">{line}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
