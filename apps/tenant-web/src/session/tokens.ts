import { createRefresher, type CookieNames } from "@ims/web-session";

import { coreBaseUrl } from "./config";

/**
 * The Tenant Web App's session cookies (LD-49; LLD 6.2 "tokens set as HttpOnly, Secure,
 * SameSite=Lax cookies"). Page JavaScript never sees a token: only the BFF route handlers and
 * the proxy read them (@ims/web-session).
 */
export const ACCESS_COOKIE = "ims_at";
export const REFRESH_COOKIE = "ims_rt";
/** The single-use MFA challenge between the password step and the code step (5 minutes). */
export const CHALLENGE_COOKIE = "ims_mfa";

export const TENANT_COOKIES: CookieNames = { access: ACCESS_COOKIE, refresh: REFRESH_COOKIE, challenge: CHALLENGE_COOKIE };

/** Exchanges a refresh token with IMS Core once per process (LD-26, decision I-33). */
export const refreshOnce = createRefresher(() => `${coreBaseUrl()}/ui/v1/auth/refresh`);
