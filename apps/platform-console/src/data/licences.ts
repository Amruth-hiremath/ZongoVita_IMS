import "server-only";

import type { Items, PlatformCustomer } from "@ims/api-client";

import { licencesPage } from "@/fixtures/licences";
import { addDays, daysUntil, formatDay } from "@/lib/dates";

import { databaseLabel, MODULE_LABELS } from "./labels";
import { fromPlatform } from "./source";

export type LicenceStatusTone = "green" | "amber" | "blue" | "red" | "gray";

export interface LicenceRow {
  enterprise_code: string;
  company: string;
  /** "31 Mar 2027", "08 Oct 2026 · 12 d". */
  valid_till_label: string;
  /** ISO date the licence is valid until. */
  valid_until: string;
  /** Sites and users in use are not visible to the platform tier (AD-13): null when not reported. */
  sites_used: number | null;
  sites_licensed: number;
  users_used: number | null;
  users_licensed: number;
  modules: string[];
  database: string;
  status: { tone: LicenceStatusTone; label: string };
}

/** The licence state of the customer nearest its end date (LLD 6.4: active, grace, read-only). */
export interface ExpiryPanel {
  enterprise_code: string;
  company: string;
  status_label: string;
  tone: LicenceStatusTone;
  valid_until: string;
  grace_until: string;
  after_grace: string;
}

export interface LicencesPage {
  registry: LicenceRow[];
  /** Null when no customer has a licence in force. */
  expiry: ExpiryPanel | null;
}

const AFTER_GRACE = "read-only · records viewable · emergency issue only";

/** Registry status of a customer: its status, then the licence state derived from the dates (LLD 6.4). */
function statusOf(customer: PlatformCustomer): LicenceRow["status"] {
  if (customer.status === "provisioning") {
    return customer.provisioning_run?.status === "failed"
      ? { tone: "red", label: "Provisioning failed" }
      : { tone: "blue", label: "Provisioning" };
  }
  if (customer.status === "suspended") return { tone: "red", label: "Suspended" };
  if (customer.status === "terminated") return { tone: "gray", label: "Terminated" };
  switch (customer.licence_state) {
    case "active":
      return { tone: "green", label: "Active" };
    case "grace":
      return { tone: "amber", label: `Grace until ${formatDay(customer.grace_ends_at!)}` };
    case "read_only":
      return { tone: "red", label: "Read-only" };
    default:
      return { tone: "gray", label: "No licence in force" };
  }
}

function expiryOf(customers: PlatformCustomer[]): ExpiryPanel | null {
  const inForce = customers
    .filter((c) => c.licence && (c.licence_state === "active" || c.licence_state === "grace" || c.licence_state === "read_only"))
    .sort((a, b) => a.licence!.valid_until.localeCompare(b.licence!.valid_until));
  const nearest = inForce[0];
  if (!nearest?.licence) return null;
  const { valid_until: validUntil, grace_days: graceDays } = nearest.licence;
  const graceEnds = addDays(validUntil, graceDays);
  const statusLabel =
    nearest.licence_state === "active"
      ? `Active · ends in ${daysUntil(validUntil)} d`
      : nearest.licence_state === "grace"
        ? `Grace period · until ${formatDay(graceEnds)}`
        : "Read-only";
  return {
    enterprise_code: nearest.code,
    company: nearest.legal_name,
    status_label: statusLabel,
    tone: nearest.licence_state === "active" ? "green" : nearest.licence_state === "grace" ? "amber" : "red",
    valid_until: formatDay(validUntil),
    grace_until: `${formatDay(graceEnds)} · ${graceDays} d per licence · full access, banner to the super admin`,
    after_grace: AFTER_GRACE,
  };
}

/** F52 Licenses (price plans and billing are not part of the design; see UI_Implementation 10). */
export function getLicencesPage(): Promise<LicencesPage> {
  return fromPlatform(
    {
      endpoint: "GET /platform/v1/customers",
      note: "Each customer with its active (or latest) licence, database and derived licence state; the grace and read-only dates of the customer nearest expiry are derived from its licence (LLD 6.4). Sites and users in use are not visible to the platform tier (AD-13) and show as not reported.",
    },
    async (get) => {
      const customers = (await get<Items<PlatformCustomer>>("/customers")).items;
      return {
        registry: customers
          .filter((customer) => customer.licence !== null)
          .map((customer) => {
            const licence = customer.licence!;
            return {
              enterprise_code: customer.code,
              company: customer.legal_name,
              valid_till_label: formatDay(licence.valid_until),
              valid_until: licence.valid_until,
              sites_used: null,
              sites_licensed: licence.max_sites,
              users_used: null,
              users_licensed: licence.max_users,
              modules: licence.modules.map((code) => MODULE_LABELS[code] ?? code),
              database: databaseLabel(customer),
              status: statusOf(customer),
            };
          }),
        expiry: expiryOf(customers),
      };
    },
    () => licencesPage,
  );
}
