import type { PlatformAuditEntry, PlatformCustomer, ProvisioningStep } from "@ims/api-client";

/**
 * Display labels for /platform/v1 values. Module names are the wireframes' short ones (F52); the
 * registry's own names are longer ("IMS core inventory").
 */
export const MODULE_LABELS: Record<string, string> = {
  "ims.core": "Core",
  "ims.replenishment": "Replenishment",
  "ims.supplier_register": "Supplier register",
  "ims.integration": "Integration",
};

export const STEP_LABELS: Record<ProvisioningStep, string> = {
  register: "registering",
  database: "creating the database",
  register_database: "registering the database",
  migrate: "migrating",
  initial_users: "creating the super admin",
  activate: "activating",
  done: "done",
};

/** Customer database name, or where provisioning stands while there is none ready. */
export function databaseLabel(customer: PlatformCustomer): string {
  const run = customer.provisioning_run;
  if (customer.status === "provisioning" && run) {
    const step = STEP_LABELS[run.current_step];
    return run.status === "failed" ? `provisioning failed · ${step}` : `provisioning · ${step}`;
  }
  return customer.database?.database_name ?? "—";
}

const ACTIONS: Record<string, string> = {
  "customer.registered": "Customer registered",
  "customer.activated": "Customer activated",
  "customer.suspended": "Customer suspended",
  "customer.reinstated": "Customer reinstated",
  "customer.terminated": "Customer terminated",
  "customer.gxp_locked": "GxP mode locked",
  "licence.created": "Licence created",
  "licence.activated": "Licence activated",
  "database.registered": "Database registered",
  "database.state_recorded": "Database state recorded",
  "platform.provisioning.started": "Onboarding started",
  "platform.provisioning.step_completed": "Provisioning step completed",
  "platform.provisioning.step_failed": "Provisioning step failed",
  "platform.provisioning.resumed": "Provisioning resumed",
  "platform.provisioning.handover_revealed": "Activation code handed over",
  "platform.user.created": "Staff account created",
  "platform.user.activated": "Staff account activated",
  "platform.user.deactivated": "Staff account deactivated",
  "platform.user.locked": "Staff account locked",
};

/**
 * Platform activity is administration: customers, licences, databases, provisioning and staff
 * accounts. Sign-ins, authenticator events and login-directory bookkeeping are in the same audit
 * but are not shown here.
 */
export function isActivity(entry: PlatformAuditEntry): boolean {
  return entry.action in ACTIONS;
}

export function actionLabel(entry: PlatformAuditEntry): string {
  const label = ACTIONS[entry.action] ?? entry.action;
  const step = entry.after?.step;
  return typeof step === "string" && step in STEP_LABELS ? `${label}: ${STEP_LABELS[step as ProvisioningStep]}` : label;
}

/** "platform_user:<id>" -> the staff member's name; "system:<job>" -> "System". */
export function actorLabel(actor: string, staffNames: Map<string, string>): string {
  const [kind, id] = actor.split(":", 2);
  if (kind === "platform_user" && id) return staffNames.get(id) ?? "Staff member";
  if (kind === "system") return "System";
  return actor;
}
