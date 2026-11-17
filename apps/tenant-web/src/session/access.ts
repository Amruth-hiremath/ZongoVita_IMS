import { hasPermission, type Me, type PermissionCode } from "@ims/api-client";

import type { Workspace } from "./workspace";

/**
 * The permission each screen needs (LLD 15 "Permission-aware UI"; LLD 12 route table): the
 * permission of the Core endpoint the screen is built on. The sidebar shows an entry only when
 * its screen opens, and the (app) layout refuses a screen reached by its address without it.
 * This is the one table for both, so the menu and the guard cannot disagree.
 *
 * `null` means any signed-in user (LLD 7 "authenticated"). Where one route draws a different
 * frame per workspace (Docs/UI_Implementation.md section 5), the permission follows the frame.
 */
type Needs = PermissionCode | null;
type Rule = { prefix: string; needs: Needs | Partial<Record<Workspace, Needs>> & { default: Needs } };

const SCREENS: Rule[] = [
  { prefix: "/dashboard", needs: null },
  // Catalogue: GET items, taxonomy (catalog.item.view); POST items; PATCH assets
  { prefix: "/items/new", needs: "catalog.item.create" },
  { prefix: "/items/assets", needs: "catalog.asset.manage" },
  { prefix: "/items", needs: "catalog.item.view" },
  { prefix: "/categories", needs: "catalog.item.view" },
  // Purchasing and quality
  { prefix: "/vendors", needs: "purchasing.vendor.view" },
  { prefix: "/purchase-records", needs: "purchasing.record.view" },
  { prefix: "/quality-register", needs: "quality.register.view" },
  // Organisation, access, workflow, settings
  { prefix: "/locations", needs: "org.location.manage" },
  { prefix: "/users", needs: "access.user.manage" },
  { prefix: "/privileges", needs: "access.role.manage" },
  { prefix: "/approvals/configuration", needs: "workflow.policy.manage" },
  { prefix: "/approvals/workflows", needs: "workflow.policy.manage" },
  { prefix: "/approvals", needs: { admin: "workflow.policy.manage", default: "workflow.task.view" } },
  { prefix: "/settings", needs: "config.settings.manage" },
  // Stock operations
  { prefix: "/issuance", needs: "issuance.request.view_all" },
  { prefix: "/fulfilment", needs: "issuance.issue.fulfil" },
  { prefix: "/scan-issue", needs: "issuance.issue.fulfil" },
  // F42 (manager) is the purchase-record inward pipeline; F10 (store) creates the GRN.
  { prefix: "/receive", needs: { manager: "purchasing.record.view", default: "receiving.grn.create" } },
  { prefix: "/quarantine", needs: "returns.return.validate" },
  // F43 (manager) decides verdicts; F49 (store) takes returns in.
  { prefix: "/returns", needs: { manager: "returns.verdict.decide", default: "returns.return.receive" } },
  { prefix: "/transfers/new", needs: "transfers.transfer.create" },
  { prefix: "/transfers", needs: "inventory.stock.view" },
  // F17 (manager) approves count adjustments; F16 (store) counts.
  { prefix: "/stock-counts", needs: { manager: "counts.adjustment.approve", default: "counts.session.count" } },
  { prefix: "/alerts/reorder-rules", needs: "replenishment.planning.view" },
  { prefix: "/alerts", needs: "alerts.alert.view" },
  { prefix: "/reports", needs: "reporting.report.view" },
  { prefix: "/audit", needs: "audit.log.view" },
];

/** Longest prefix first, so /items/new is matched before /items. */
const RULES = [...SCREENS].sort((a, b) => b.prefix.length - a.prefix.length);

function matches(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix}/`);
}

/** What a screen needs; `undefined` for a path that is not a screen of this app. */
export function screenPermission(path: string, workspace: Workspace): Needs | undefined {
  const rule = RULES.find((candidate) => matches(path, candidate.prefix));
  if (!rule) return undefined;
  if (rule.needs === null || typeof rule.needs === "string") return rule.needs;
  return workspace in rule.needs ? (rule.needs[workspace] ?? null) : rule.needs.default;
}

export function canOpen(me: Me, workspace: Workspace, path: string): boolean {
  const needs = screenPermission(path, workspace);
  return needs === undefined || needs === null || hasPermission(me, needs);
}
