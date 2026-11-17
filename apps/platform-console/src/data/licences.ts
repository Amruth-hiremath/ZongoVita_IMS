import "server-only";

import { licencesPage } from "@/fixtures/licences";

import { fromFixture } from "./source";

export type LicenceStatusTone = "green" | "amber" | "blue" | "red" | "gray";

export interface LicenceRow {
  enterprise_code: string;
  company: string;
  /** "31 Mar 2027", "08 Oct 2026 · 12 d". */
  valid_till_label: string;
  /** ISO date the licence is valid until. */
  valid_until: string;
  sites_used: number;
  sites_licensed: number;
  users_used: number;
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
  valid_until: string;
  grace_until: string;
  after_grace: string;
}

export interface LicencesPage {
  registry: LicenceRow[];
  expiry: ExpiryPanel;
}

/** F52 Licenses (price plans and billing are not part of the design; see UI_Implementation 10). */
export function getLicencesPage(): Promise<LicencesPage> {
  return fromFixture(
    {
      endpoint: "GET /platform/v1/licences",
      note: "Registry rows need validity, sites and users used / licensed, modules, the customer database and a status; the grace and read-only dates of the customer nearest expiry are derived from its licence (LLD 6.4).",
    },
    licencesPage,
  );
}
