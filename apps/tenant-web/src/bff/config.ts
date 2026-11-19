import "server-only";

import type { BffConfig } from "@ims/web-session";

import { coreBaseUrl, publicOrigin, sessionSource } from "@/session/config";
import { refreshOnce, TENANT_COOKIES } from "@/session/tokens";

/** The Tenant Web App's BFF: IMS Core's UI API (/ui/v1), in `core` session mode (LD-49, LLD 15). */
export const tenantBff: BffConfig = {
  apiBase: () => `${coreBaseUrl()}/ui/v1`,
  enabled: () => sessionSource() === "core",
  publicOrigin,
  cookies: TENANT_COOKIES,
  refresh: refreshOnce,
};
