import "server-only";

import { platformConfig } from "@/fixtures/config";

import { fromFixture } from "./source";

export interface ModuleFlag {
  flag_id: string;
  label: string;
  enabled: boolean;
}

export interface PlatformConfig {
  environment: string;
  module_flags: ModuleFlag[];
  environment_rails: { label: string; value: string }[];
  tenants_may_tune: string[];
  tenants_may_not_touch: string[];
}

/** F53 Platform Config. */
export function getPlatformConfig(): Promise<PlatformConfig> {
  return fromFixture(
    {
      endpoint: "GET /platform/v1/config (no such resource in LLD 6.8)",
      note: "Module flags, environment rails and the tenant override boundary have no /platform/v1 resource in LLD section 12; the frame's plan entitlement rails are not part of the design.",
    },
    platformConfig,
  );
}
