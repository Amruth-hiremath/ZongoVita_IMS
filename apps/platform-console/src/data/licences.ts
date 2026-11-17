import "server-only";

import { licencesPage } from "@/fixtures/licences";

import { fromFixture } from "./source";

export type PlanBadgeTone = "gray" | "blue" | "dark";

export interface PlanCard {
  plan_id: string;
  name: string;
  badge: { label: string; tone: PlanBadgeTone };
  /** Decimal string, INR. */
  price_per_seat_month: string;
  /** Entitlement lines as drawn ("Seats · up to 5"). */
  entitlements: string[];
}

export type LicenceStatusTone = "green" | "amber" | "blue" | "red" | "gray";

export interface LicenceRow {
  enterprise_code: string;
  company: string;
  plan: string;
  /** As drawn: "31 Mar 2027", "08 Oct 2026 · 12 d", "trial · 14 d". */
  valid_till_label: string;
  /** ISO date the licence is valid until, or null during a trial. */
  valid_until: string | null;
  sites_used: number;
  /** null means unlimited. */
  sites_licensed: number | null;
  users_used: number;
  users_licensed: number;
  modules: string[];
  database: string;
  status: { tone: LicenceStatusTone; label: string };
}

export interface RenewalPanel {
  enterprise_code: string;
  company: string;
  status_label: string;
  reminder: string;
  grace_period: string;
  auto_suspend: string;
}

export interface LicencesPage {
  plans: PlanCard[];
  registry: LicenceRow[];
  renewal: RenewalPanel;
}

/** F52 Licenses & Plans. */
export function getLicencesPage(): Promise<LicencesPage> {
  return fromFixture(
    {
      endpoint: "GET /platform/v1/licences",
      note: "Registry rows need plan, validity, sites and users used / licensed, modules, the customer database and a status; plan cards (price per seat, entitlements) and the renewal & dunning state of the customer nearest expiry have no /platform/v1 resource in LLD section 12.",
    },
    licencesPage,
  );
}
