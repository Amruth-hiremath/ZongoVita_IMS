"use client";

import { cn } from "@ims/ui";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import type { TaxonomyNode } from "@/data/categories";
import { formatQty } from "@/lib/format";

function countLine(node: TaxonomyNode): string {
  const items = `${formatQty(node.item_count)} ${node.item_count === 1 ? "item" : "items"}`;
  return node.detail ? `${items} · ${node.detail}` : items;
}

/** Nodes whose children arrived with the response start expanded, as drawn. */
function initiallyOpen(nodes: TaxonomyNode[], into: Set<string> = new Set()): Set<string> {
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      into.add(node.node_id);
      initiallyOpen(node.children, into);
    }
  }
  return into;
}

/** Indent of a child row per level below L1 (px, as drawn: 36 px per level). */
const indent: Record<number, string> = { 1: "pl-[36px]", 2: "pl-[72px]", 3: "pl-[108px]" };

function Toggle({ node, open, onToggle }: { node: TaxonomyNode; open: boolean; onToggle: () => void }) {
  if (!node.has_children) {
    return (
      <span aria-hidden className="flex size-4 items-center justify-center">
        <span className="size-1.5 rounded-full bg-gray-300" />
      </span>
    );
  }
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-label={`${open ? "Collapse" : "Expand"} ${node.name}`}
      onClick={onToggle}
      className="flex size-4 items-center justify-center text-gray-500 hover:text-gray-900"
    >
      <Icon className="size-3.5" strokeWidth={1.8} />
    </button>
  );
}

function Branch({
  node,
  open,
  toggle,
}: {
  node: TaxonomyNode;
  open: Set<string>;
  toggle: (id: string) => void;
}) {
  const isOpen = open.has(node.node_id);
  const children = isOpen ? node.children : [];

  return (
    <li>
      {node.level === 0 ? (
        <div className="flex h-9 items-center gap-3 rounded-md border-[1.4px] border-gray-200 bg-gray-50 pl-3 pr-3">
          <Toggle node={node} open={isOpen} onToggle={() => toggle(node.node_id)} />
          <span className="min-w-0 flex-1 text-[13px] font-semibold text-gray-900">{node.name}</span>
          <span className="text-right text-[10.5px] text-gray-400">{countLine(node)}</span>
        </div>
      ) : (
        <div className={cn("flex items-center gap-3 pr-3", node.level === 3 ? "h-7" : "h-8", indent[node.level])}>
          <span aria-hidden className="-mt-3 ml-0.5 h-3 w-2.5 shrink-0 border-b border-l border-gray-300" />
          <Toggle node={node} open={isOpen} onToggle={() => toggle(node.node_id)} />
          <span
            className={cn(
              "min-w-0 flex-1 text-gray-900",
              node.level === 1 ? "text-[13px] font-semibold" : "text-[12.5px] text-gray-700",
            )}
          >
            {node.name}
          </span>
          <span className="text-right text-[10.5px] text-gray-500">{countLine(node)}</span>
        </div>
      )}
      {isOpen && children === null ? (
        <p className={cn("py-1.5 text-[10.5px] text-gray-400", indent[Math.min(node.level + 1, 3)])}>
          Subcategories are not in the sample data.
        </p>
      ) : null}
      {children && children.length > 0 ? (
        <ul>
          {children.map((child) => (
            <Branch key={child.node_id} node={child} open={open} toggle={toggle} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** F25 taxonomy tree: every node with children expands and collapses. */
export function TaxonomyTree({ roots }: { roots: TaxonomyNode[] }) {
  const [open, setOpen] = useState<Set<string>>(() => initiallyOpen(roots));
  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <ul className="space-y-1">
      {roots.map((node) => (
        <Branch key={node.node_id} node={node} open={open} toggle={toggle} />
      ))}
    </ul>
  );
}
