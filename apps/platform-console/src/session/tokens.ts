import { createRefresher, type CookieNames } from "@ims/web-session";

import { platformBaseUrl } from "./config";

/**
 * The console's session cookies (LD-49; HttpOnly, SameSite=Lax, Secure in production). Page
 * JavaScript never sees a token: only the BFF route handlers and the proxy read them
 * (@ims/web-session). The names differ from the Tenant Web App's, so the two never mix on a
 * shared host name such as localhost.
 */
export const CONSOLE_COOKIES: CookieNames = {
  access: "ims_pc_at",
  refresh: "ims_pc_rt",
  challenge: "ims_pc_mfa",
};

/** Exchanges a refresh token with the Platform Service once per process (rotation, reuse revokes). */
export const refreshOnce = createRefresher(() => `${platformBaseUrl()}/platform/v1/auth/refresh`);
