import type { LicenceState } from "./licence";

/**
 * The Platform Service's administration API (/platform/v1, LLD 6.8) as the Platform Console reads
 * it. Written by hand like the rest of this package; tests/static/test_typescript_contracts.py
 * keeps the enumerations equal to the Python ones.
 */

/** ZongoVita staff roles (HLD section 3 actors: system admin, support engineer). */
export const STAFF_ROLES = ["system_admin", "support_engineer"] as const;
export type StaffRole = (typeof STAFF_ROLES)[number];

/** Customer status in the registry (LLD 4). */
export const CUSTOMER_STATUSES = ["provisioning", "active", "suspended", "terminated"] as const;
export type CustomerStatus = (typeof CUSTOMER_STATUSES)[number];

/** The provisioning steps in order (LLD 6.6, AD-28). */
export const PROVISIONING_STEPS = [
  "register",
  "database",
  "register_database",
  "migrate",
  "initial_users",
  "activate",
  "done",
] as const;
export type ProvisioningStep = (typeof PROVISIONING_STEPS)[number];

/** GET /platform/v1/me */
export interface StaffMe {
  id: string;
  display_name: string;
  login_identifier: string;
  email: string | null;
  role: StaffRole;
}

export interface PlatformLicence {
  id: string;
  licence_no: string;
  record_status: "draft" | "active" | "superseded";
  valid_from: string;
  valid_until: string;
  grace_days: number;
  max_sites: number;
  max_users: number;
  modules: string[];
}

/** GET /platform/v1/customers (items) and /customers/{id}. */
export interface PlatformCustomer {
  id: string;
  code: string;
  legal_name: string;
  status: CustomerStatus;
  gxp_mode: boolean;
  gxp_locked: boolean;
  placement: "shared" | "dedicated";
  created_at: string;
  /** The active licence, or the latest one while none is active. */
  licence: PlatformLicence | null;
  /** Derived at read time (LLD 6.4); null while provisioning or without an active licence. */
  licence_state: LicenceState | null;
  grace_ends_at: string | null;
  database: { database_name: string; cluster_ref: string; status: string; schema_version: string | null } | null;
  provisioning_run: { id: string; status: "running" | "failed" | "completed"; current_step: ProvisioningStep } | null;
}

export interface PlatformModule {
  code: string;
  name: string;
  active: boolean;
}

/** GET /platform/v1/audit (items): the append-only platform audit. */
export interface PlatformAuditEntry {
  seq: number;
  occurred_at: string;
  /** "platform_user:<id>", "system:<job>" or another service identity. */
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  customer_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
  request_id: string | null;
}

/** GET /platform/v1/users (items). */
export interface PlatformStaffUser {
  id: string;
  login_identifier: string;
  display_name: string;
  email: string | null;
  role: StaffRole;
  status: "invited" | "active" | "suspended" | "deactivated";
  mfa_enrolled: boolean;
  created_at: string;
  version: number;
}

export interface Items<T> {
  items: T[];
}
