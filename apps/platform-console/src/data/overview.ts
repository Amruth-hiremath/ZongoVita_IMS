import "server-only";

import type { Items, PlatformAuditEntry, PlatformCustomer, PlatformStaffUser } from "@ims/api-client";

import { platformOverview } from "@/fixtures/overview";
import { formatDayTime } from "@/lib/dates";

import { actionLabel, actorLabel, databaseLabel, isActivity } from "./labels";
import { fromPlatform } from "./source";

export interface TenantPulseRow {
  enterprise_code: string;
  company: string;
  /** Customer database name, or the provisioning state while there is none yet. */
  database: string;
  /**
   * Invited and active users against the licence user limit (LLD 5.1). Usage inside a customer
   * database is not visible to the platform tier (AD-13): null when not reported.
   */
  users_used: number | null;
  users_licensed: number | null;
  /** API calls over the last 7 days as drawn ("412 K"), or null when not reported. */
  api_calls_7d: string | null;
  /** As drawn: "today 09:41", "wizard step 3"; null when not reported. */
  last_activity_label: string | null;
}

export interface PlatformActivity {
  title: string;
  meta: string;
}

export interface PlatformOverview {
  kpis: {
    /** Customers by status (LLD 4: provisioning, active, suspended, terminated). */
    enterprises: { total: number; active: number; provisioning: number; suspended: number };
    /** ``used`` and ``utilisation_percent`` are null when usage is not reported. */
    users: { used: number | null; licensed: number; utilisation_percent: number | null };
    uptime: { percent: string; window: string; sla_percent: string } | null;
    api_today: { calls: string; p95_ms: number; failures: number } | null;
  };
  tenants: TenantPulseRow[];
  activity: PlatformActivity[];
  health: { label: string; value: string }[];
}

const NOT_REPORTED = "not reported by the Platform Service yet";

/** F51 Platform Overview. */
export function getPlatformOverview(): Promise<PlatformOverview> {
  return fromPlatform(
    {
      endpoint: "GET /platform/v1/customers",
      note: "Also GET /platform/v1/audit (platform activity) and GET /platform/v1/users (who acted). Users and sites in use, API calls, last activity, uptime and the NFR health figures have no /platform/v1 resource in LLD section 12 and show as not reported; usage inside a customer database is not visible to the platform tier (AD-13).",
    },
    async (get) => {
      const [customers, audit, users] = await Promise.all([
        get<Items<PlatformCustomer>>("/customers"),
        get<Items<PlatformAuditEntry>>("/audit?limit=100"),
        get<Items<PlatformStaffUser>>("/users"),
      ]);
      const count = (status: PlatformCustomer["status"]) => customers.items.filter((c) => c.status === status).length;
      const inForce = customers.items.filter((c) => c.status !== "terminated" && c.licence?.record_status === "active");
      const byId = new Map(customers.items.map((c) => [c.id, c]));
      const names = new Map(users.items.map((u) => [u.id, u.display_name]));

      return {
        kpis: {
          enterprises: {
            total: customers.items.length,
            active: count("active"),
            provisioning: count("provisioning"),
            suspended: count("suspended"),
          },
          users: { used: null, licensed: inForce.reduce((sum, c) => sum + (c.licence?.max_users ?? 0), 0), utilisation_percent: null },
          uptime: null,
          api_today: null,
        },
        tenants: customers.items.map((customer) => ({
          enterprise_code: customer.code,
          company: customer.legal_name,
          database: databaseLabel(customer),
          users_used: null,
          users_licensed: customer.licence?.max_users ?? null,
          api_calls_7d: null,
          last_activity_label: null,
        })),
        activity: audit.items
          .filter(isActivity)
          .slice(0, 5)
          .map((entry) => {
            const customer = entry.customer_id ? byId.get(entry.customer_id) : undefined;
            return {
              title: customer ? `${actionLabel(entry)} · ${customer.code} ${customer.legal_name}` : actionLabel(entry),
              meta: `${actorLabel(entry.actor, names)} · ${formatDayTime(entry.occurred_at)}`,
            };
          }),
        health: platformOverview.health.map((row) => ({ label: row.label, value: NOT_REPORTED })),
      };
    },
    () => platformOverview,
  );
}
