/** FIXTURE: the taxonomy and proposal queue drawn in wireframe F25. Temporary; see src/data/source.ts. */
import type { Taxonomy, TaxonomyNode, TaxonomyProposal } from "@/data/categories";

function node(
  node_id: string,
  name: string,
  level: number,
  item_count: number,
  detail: string | null,
  children: TaxonomyNode[] | null | "leaf",
): TaxonomyNode {
  return {
    node_id,
    name,
    level,
    item_count,
    detail,
    has_children: children !== "leaf",
    children: children === "leaf" ? [] : children,
  };
}

export const taxonomy: Taxonomy = {
  levels: 4,
  roots: [
    node("spares", "Spares", 0, 128, "3 lines", [
      node("bearings-bushings", "Bearings & Bushings", 1, 34, "2 lines", [
        node("ball-bearings", "Ball Bearings", 2, 21, "2 lines", [
          node("deep-groove", "Deep Groove", 3, 14, null, "leaf"),
          node("angular-contact", "Angular Contact", 3, 7, null, "leaf"),
        ]),
        node("roller-bearings", "Roller Bearings", 2, 13, "1 line", null),
      ]),
      node("seals-gaskets", "Seals & Gaskets", 1, 21, "1 line", null),
      node("belts-pulleys", "Belts & Pulleys", 1, 18, "1 line", null),
    ]),
    node("consumables", "Consumables", 0, 486, "3 lines", null),
    node("it-equipment", "IT Equipment", 0, 3, "new line — assets map here (F60)", [
      node("computing", "Computing", 1, 2, "2 lines", [
        node("laptops", "Laptops", 2, 1, "manual code LAP-5540", [
          node("business-grade", "Business Grade", 3, 1, "4 assets → F60", "leaf"),
        ]),
        node("monitors", "Monitors", 2, 1, "manual code MON-2440", null),
      ]),
    ]),
    node("electrical", "Electrical", 0, 119, "2 lines", null),
    node("tools", "Tools", 0, 74, "no lines yet", "leaf"),
  ],
  latest_rejection: {
    proposal_id: "prop-bearing-items",
    name: "Bearing Items",
    proposed_by: "Kavita Rao",
    proposed_on: "25 Sep",
    parent_path: "Spares > Bearings > Ball",
    match_percent: 94,
    matched_node: "Deep Groove",
  },
};

export const proposalQueue: TaxonomyProposal[] = [
  {
    proposal_id: "prop-lubrication-oils",
    name: "Lubrication Oils",
    parent_name: "Consumables",
    proposed_by: "Rahul Verma",
    status: "under_check",
    dedupe_note: "similar-word workload running…",
    approval_task_id: null,
  },
  {
    proposal_id: "prop-fasteners",
    name: "Fasteners",
    parent_name: "Spares",
    proposed_by: "Rahul Verma",
    status: "pending_approval",
    dedupe_note: "dedupe PASS — no similar category",
    approval_task_id: "task-prop-fasteners",
  },
  {
    proposal_id: "prop-bearing-items",
    name: "Bearing Items",
    parent_name: "Spares",
    proposed_by: "Kavita Rao",
    status: "rejected_duplicate",
    dedupe_note: "94% similar → Bearings & Bushings",
    approval_task_id: null,
  },
];
