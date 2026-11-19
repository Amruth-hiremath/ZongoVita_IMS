import "server-only";

import type { Items, PlatformCustomer } from "@ims/api-client";

import { staff } from "@/fixtures/staff";

import { fromPlatform } from "./source";

export interface EnterpriseOption {
  code: string;
  name: string;
}

/** The top bar's enterprise selector: every customer in the registry (LLD 4). */
export function getEnterpriseOptions(): Promise<EnterpriseOption[]> {
  return fromPlatform(
    { endpoint: "GET /platform/v1/customers", note: "Customer code and legal name for the enterprise selector." },
    async (get) =>
      (await get<Items<PlatformCustomer>>("/customers")).items
        .filter((customer) => customer.status !== "terminated")
        .map((customer) => ({ code: customer.code, name: customer.legal_name })),
    () => staff.enterprises,
  );
}
