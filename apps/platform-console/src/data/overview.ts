import "server-only";

import { platformOverview } from "@/fixtures/overview";

import { fromFixture } from "./source";

export interface TenantPulseRow {
  enterprise_code: string;
  company: string;
  /** Plan name, or null while the customer is still being provisioned. */
  plan: string | null;
  /** Customer database name, or the provisioning state while there is none yet. */
  database: string;
  seats_used: number;
  seats_licensed: number;
  /** API calls over the last 7 days as drawn ("412 K"), or null when there are none. */
  api_calls_7d: string | null;
  /** As drawn: "today 09:41", "wizard step 3". */
  last_activity_label: string;
}

export interface PlatformActivity {
  title: string;
  meta: string;
}

export interface PlatformOverview {
  kpis: {
    enterprises: { total: number; active: number; onboarding: number; trial: number };
    seats: { used: number; licensed: number; utilisation_percent: number };
    uptime: { percent: string; window: string; sla_percent: string };
    api_today: { calls: string; p95_ms: number; failures: number };
  };
  tenants: TenantPulseRow[];
  activity: PlatformActivity[];
  health: { label: string; value: string }[];
}

/** F51 Platform Overview. */
export function getPlatformOverview(): Promise<PlatformOverview> {
  return fromFixture(
    {
      endpoint: "GET /platform/v1/customers",
      note: "Needs, per customer, plan, database name or provisioning state, seats used / licensed, 7-day API call count and last activity; plus platform totals (enterprises by state, seats, uptime, API calls today), recent platform activity (GET /platform/v1/audit) and NFR health figures, which no /platform/v1 resource in LLD section 12 provides.",
    },
    platformOverview,
  );
}
