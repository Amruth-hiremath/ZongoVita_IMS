/**
 * Permission catalogue (LLD section 7): one code per action on a resource, module.resource.action.
 * Site-scoped permissions are marked. Mirrors Core's code-defined catalogue
 * (ims_contracts/permissions.py); a static test keeps the two equal.
 */
export const PERMISSIONS = {
  "catalog.item.view": { siteScoped: false },
  "catalog.item.create": { siteScoped: false },
  "catalog.item.edit": { siteScoped: false },
  "catalog.item.approve": { siteScoped: false },
  "catalog.item.deactivate": { siteScoped: false },
  "catalog.taxonomy.propose": { siteScoped: false },
  "catalog.taxonomy.approve": { siteScoped: false },
  "catalog.attribute.manage": { siteScoped: false },
  "catalog.numbering.manage": { siteScoped: false },
  "catalog.asset.manage": { siteScoped: true },
  "inventory.stock.view": { siteScoped: true },
  "inventory.ledger.view": { siteScoped: true },
  "receiving.grn.create": { siteScoped: true },
  "receiving.grn.inspect": { siteScoped: true },
  "receiving.grn.post": { siteScoped: true },
  "issuance.request.create": { siteScoped: true },
  "issuance.request.view_all": { siteScoped: true },
  "issuance.request.approve": { siteScoped: true },
  "issuance.issue.fulfil": { siteScoped: true },
  "transfers.transfer.create": { siteScoped: true },
  "transfers.transfer.approve": { siteScoped: true },
  "transfers.transfer.dispatch": { siteScoped: true },
  "transfers.transfer.receive": { siteScoped: true },
  "counts.session.manage": { siteScoped: true },
  "counts.session.count": { siteScoped: true },
  "counts.adjustment.approve": { siteScoped: true },
  "returns.return.create": { siteScoped: true },
  "returns.return.receive": { siteScoped: true },
  "returns.return.validate": { siteScoped: true },
  "returns.verdict.decide": { siteScoped: true },
  "quality.case.dispose": { siteScoped: true },
  "quality.register.view": { siteScoped: false },
  "purchasing.vendor.view": { siteScoped: false },
  "purchasing.vendor.manage": { siteScoped: false },
  "purchasing.vendor.approve": { siteScoped: false },
  "purchasing.record.view": { siteScoped: false },
  "purchasing.record.manage": { siteScoped: false },
  "replenishment.planning.view": { siteScoped: true },
  "replenishment.planning.edit": { siteScoped: true },
  "replenishment.threshold.approve": { siteScoped: true },
  "replenishment.formula.manage": { siteScoped: false },
  "workflow.policy.manage": { siteScoped: false },
  "workflow.task.view": { siteScoped: false },
  "access.user.manage": { siteScoped: false },
  "access.role.manage": { siteScoped: false },
  "access.api_client.manage": { siteScoped: false },
  "access.super_admin.transfer": { siteScoped: false },
  "access.support.grant": { siteScoped: false },
  "access.recovery_approver.manage": { siteScoped: false },
  "org.site.manage": { siteScoped: false },
  "org.location.manage": { siteScoped: false },
  "org.department.manage": { siteScoped: false },
  "alerts.alert.view": { siteScoped: true },
  "alerts.alert.manage": { siteScoped: true },
  "reporting.report.view": { siteScoped: true },
  "reporting.export.run": { siteScoped: true },
  "audit.log.view": { siteScoped: true },
  "integration.webhook.manage": { siteScoped: false },
  "integration.connector.manage": { siteScoped: false },
  "integration.mapping.manage": { siteScoped: false },
  "integration.sync.view": { siteScoped: false },
  "config.settings.manage": { siteScoped: false },
} as const satisfies Record<string, { siteScoped: boolean }>;

export type PermissionCode = keyof typeof PERMISSIONS;

/** Permissions the LLD reserves to the Super Admin role. */
export const RESERVED_TO_SUPER_ADMIN: readonly PermissionCode[] = [
  "access.super_admin.transfer",
  "access.support.grant",
  "access.recovery_approver.manage",
];

export const ALL_PERMISSION_CODES = Object.keys(PERMISSIONS) as PermissionCode[];

/**
 * Seeded roles (LLD 5.1, "Seeded roles"), as written at provisioning. Customers may edit every
 * seeded role except Super Admin (#10), so these are defaults, not facts about a customer: the
 * web app reads a principal's real permissions from GET /ui/v1/me. Used by the sample personas.
 */
export const USER_TYPE_2: readonly PermissionCode[] = [
  "alerts.alert.view",
  "audit.log.view",
  "catalog.item.view",
  "catalog.taxonomy.approve",
  "counts.adjustment.approve",
  "integration.sync.view",
  "inventory.ledger.view",
  "inventory.stock.view",
  "issuance.request.approve",
  "issuance.request.view_all",
  "purchasing.record.view",
  "purchasing.vendor.manage",
  "purchasing.vendor.view",
  "quality.register.view",
  "replenishment.formula.manage",
  "replenishment.planning.view",
  "replenishment.threshold.approve",
  "reporting.report.view",
  "returns.verdict.decide",
  "transfers.transfer.approve",
  "workflow.task.view",
];

export const USER_TYPE_3: readonly PermissionCode[] = [
  "catalog.item.view",
  "counts.session.count",
  "inventory.stock.view",
  "issuance.issue.fulfil",
  "issuance.request.create",
  "receiving.grn.create",
  "receiving.grn.inspect",
  "receiving.grn.post",
  "returns.return.receive",
  "returns.return.validate",
  "transfers.transfer.create",
  "transfers.transfer.dispatch",
  "transfers.transfer.receive",
];

export const USER_TYPE_4: readonly PermissionCode[] = ["issuance.request.create", "returns.return.create"];

/** User Type 1: every permission except those reserved to the Super Admin. */
export const USER_TYPE_1: readonly PermissionCode[] = ALL_PERMISSION_CODES.filter(
  (code) => !RESERVED_TO_SUPER_ADMIN.includes(code),
);
