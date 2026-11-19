import "server-only";

import type { BffConfig } from "@ims/web-session";

import { platformBaseUrl, publicOrigin, sessionSource } from "@/session/config";
import { CONSOLE_COOKIES, refreshOnce } from "@/session/tokens";

/** The console's BFF: the Platform Service's administration API (/platform/v1), in `platform` mode (LLD 15). */
export const consoleBff: BffConfig = {
  apiBase: () => `${platformBaseUrl()}/platform/v1`,
  enabled: () => sessionSource() === "platform",
  publicOrigin,
  cookies: CONSOLE_COOKIES,
  refresh: refreshOnce,
};
