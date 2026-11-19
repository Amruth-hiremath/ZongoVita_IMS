/**
 * Session cookies and token upkeep for a backend-for-frontend (LD-49; LLD 6.2 "tokens set as
 * HttpOnly, Secure, SameSite=Lax cookies"). Page JavaScript never sees a token: only route
 * handlers and the proxy read these cookies.
 */
export interface CookieOptions {
  httpOnly: true;
  sameSite: "lax";
  secure: boolean;
  path: "/";
  maxAge?: number;
  expires?: Date;
}

export function cookieOptions(lifetime: { maxAge?: number; expires?: Date }): CookieOptions {
  return {
    httpOnly: true,
    sameSite: "lax",
    // IMS_COOKIE_INSECURE=1 exists for local end-to-end runs over plain HTTP only.
    secure: process.env.NODE_ENV === "production" && process.env.IMS_COOKIE_INSECURE !== "1",
    path: "/",
    ...lifetime,
  };
}

export interface SessionTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  refresh_expires_at: string;
  recovery_codes?: string[];
}

export interface CookieNames {
  access: string;
  refresh: string;
  /** The single-use MFA challenge between the password step and the code step. */
  challenge: string;
}

/** Seconds until a JWT's exp claim; -1 if it cannot be read. The backend verifies the token. */
export function secondsLeft(jwt: string, now = Date.now()): number {
  const payload = jwt.split(".")[1];
  if (!payload) return -1;
  try {
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as { exp?: unknown };
    return typeof claims.exp === "number" ? claims.exp - now / 1000 : -1;
  } catch {
    return -1;
  }
}

/** Refresh when the access token has less than this left. */
export const REFRESH_MARGIN_SECONDS = 30;

export type Refresher = (refreshToken: string) => Promise<SessionTokens | null>;

/**
 * Exchanges a refresh token once (LD-26: each use rotates it, and presenting a spent one revokes
 * the whole session). Concurrent requests carrying the same refresh token, such as a page and
 * its parallel requests, share one exchange; the result is kept briefly for requests still in
 * flight with the old cookie. The map lives in this server process (decision I-33, U-13).
 */
export function createRefresher(refreshUrl: () => string): Refresher {
  const inflight = new Map<string, Promise<SessionTokens | null>>();
  async function exchange(refreshToken: string): Promise<SessionTokens | null> {
    const response = await fetch(refreshUrl(), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as SessionTokens;
  }
  return (refreshToken: string) => {
    let pending = inflight.get(refreshToken);
    if (!pending) {
      pending = exchange(refreshToken).catch(() => null);
      inflight.set(refreshToken, pending);
      setTimeout(() => inflight.delete(refreshToken), 30_000).unref?.();
    }
    return pending;
  };
}

export function accessCookie(names: CookieNames, tokens: SessionTokens): [string, string, CookieOptions] {
  return [names.access, tokens.access_token, cookieOptions({ maxAge: tokens.expires_in })];
}

export function refreshCookie(names: CookieNames, tokens: SessionTokens): [string, string, CookieOptions] {
  return [names.refresh, tokens.refresh_token, cookieOptions({ expires: new Date(tokens.refresh_expires_at) })];
}
