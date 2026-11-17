import "server-only";

import { platformConfig } from "@/fixtures/config";

import { fromFixture } from "./source";

export interface ModuleFlag {
  flag_id: string;
  label: string;
  enabled: boolean;
}

export interface PlanRail {
  rail: string;
  starter: string;
  growth: string;
  enterprise: string;
}

export interface PlatformConfig {
  environment: string;
  module_flags: ModuleFlag[];
  environment_rails: { label: string; value: string }[];
  plan_rails: PlanRail[];
  tenants_may_tune: string[];
  tenants_may_not_touch: string[];
}

/** F53 Platform Config. */
export function getPlatformConfig(): Promise<PlatformConfig> {
  return fromFixture(
    {
      endpoint: "GET /platform/v1/licences",
      note: "Plan entitlement rails are the closest licence data. Module flags, environment rails and the tenant override boundary have no /platform/v1 resource in LLD section 12.",
    },
    platformConfig,
  );
}
