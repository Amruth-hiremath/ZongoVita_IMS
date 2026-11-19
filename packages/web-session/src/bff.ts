import { randomUUID } from "node:crypto";

import { NextResponse, type NextRequest } from "next/server";

import {
  accessCookie,
  cookieOptions,
  refreshCookie,
  REFRESH_MARGIN_SECONDS,
  secondsLeft,
  type CookieNames,
  type Refresher,
  type SessionTokens,
} from "./tokens";

/**
 * Backend-for-frontend route handlers (LD-49; LLD 15 "BFF"), shared by the Tenant Web App (to
 * IMS Core /ui/v1) and the Platform Console (to the Platform Service /platform/v1).
 *
 * - The browser talks only to its own app; handlers add the bearer token from the HttpOnly
 *   cookie and forward to the backend API.
 * - Writes need the X-IMS-CSRF header and an Origin equal to the app's own; with SameSite=Lax
 *   cookies that keeps other sites from acting with the user's session.
 * - Each write carries an Idempotency-Key, generated here when the page sent none (LLD 12).
 * - On TOKEN_EXPIRED the session is refreshed once and the call replayed with the same key.
 * - Credential routes are never forwarded by the catch-all: they would hand tokens to page
 *   JavaScript. The sign-in steps have their own handlers, which keep tokens in cookies.
 */
export const CSRF_HEADER = "x-ims-csrf";

export interface BffConfig {
  /** Base URL of the backend API, e.g. "http://ims-core:8080/ui/v1". */
  apiBase(): string;
  /** False when the app runs on sample data and has no backend session. */
  enabled(): boolean;
  /** The origin browsers use for this app, for the Origin check. */
  publicOrigin(requestUrl: string): string;
  cookies: CookieNames;
  refresh: Refresher;
}

type Handler = (request: NextRequest) => Promise<Response>;
type CatchAllHandler = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => Promise<Response>;

export function problem(status: number, code: string, title: string, detail?: string): NextResponse {
  return NextResponse.json(
    { type: "about:blank", title, status, code, detail: detail ?? null, errors: [] },
    { status, headers: { "content-type": "application/problem+json", "cache-control": "no-store" } },
  );
}

/** Refuses a cross-site or scripted-from-elsewhere write before anything is forwarded. */
export function refuseCrossSite(request: NextRequest, config: BffConfig): NextResponse | null {
  if (request.headers.get(CSRF_HEADER) !== "1") {
    return problem(403, "PERMISSION_DENIED", "Missing CSRF header", `Send ${CSRF_HEADER}: 1 with every change.`);
  }
  const origin = request.headers.get("origin");
  if (origin === null || origin !== config.publicOrigin(request.url)) {
    return problem(403, "PERMISSION_DENIED", "Cross-site request refused");
  }
  return null;
}

function refuseInFixtureMode(config: BffConfig): NextResponse | null {
  return config.enabled() ? null : problem(404, "NOT_FOUND", "Not found");
}

export async function callBackend(
  config: BffConfig,
  path: string,
  init: { method: string; body?: string | null; headers?: Record<string, string> },
): Promise<Response> {
  try {
    return await fetch(`${config.apiBase()}${path}`, {
      method: init.method,
      body: init.body ?? null,
      headers: init.headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return new Response(
      JSON.stringify({ type: "about:blank", title: "The service is unreachable", status: 503, code: "DB_BUSY", detail: null, errors: [] }),
      { status: 503, headers: { "content-type": "application/problem+json", "retry-after": "2" } },
    );
  }
}

/** Response headers worth passing back to the browser. */
const PASSED = ["content-type", "etag", "retry-after", "idempotent-replay", "x-request-id", "cache-control"];

export async function relay(response: Response): Promise<NextResponse> {
  const headers = new Headers();
  for (const name of PASSED) {
    const value = response.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  if (!headers.has("cache-control")) headers.set("cache-control", "no-store");
  const body = response.status === 204 ? null : await response.arrayBuffer();
  return new NextResponse(body, { status: response.status, headers });
}

async function readJson(request: NextRequest): Promise<Record<string, unknown> | null> {
  try {
    return (await request.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

const JSON_HEADERS = { "content-type": "application/json" };

// ------------------------------------------------------------------------ sign-in handlers
/** Password step: the single-use MFA challenge stays in an HttpOnly cookie. */
export function loginHandler(config: BffConfig): Handler {
  return async (request) => {
    const refused = refuseInFixtureMode(config) ?? refuseCrossSite(request, config);
    if (refused) return refused;
    const body = await readJson(request);
    const answer = await callBackend(config, "/auth/login", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ login_identifier: body?.login_identifier, password: body?.password }),
    });
    if (!answer.ok) return relay(answer);
    const login = (await answer.json()) as { status: string; challenge_token: string; challenge_expires_in: number };
    const response = NextResponse.json({ status: login.status }, { headers: { "cache-control": "no-store" } });
    response.cookies.set(config.cookies.challenge, login.challenge_token, cookieOptions({ maxAge: login.challenge_expires_in }));
    return response;
  };
}

/** First sign-in: the authenticator secret, shown once to the person enrolling. */
export function enrolHandler(config: BffConfig): Handler {
  return async (request) => {
    const refused = refuseInFixtureMode(config) ?? refuseCrossSite(request, config);
    if (refused) return refused;
    const challenge = request.cookies.get(config.cookies.challenge)?.value;
    if (!challenge) return problem(401, "AUTH_REQUIRED", "Sign in again");
    return relay(
      await callBackend(config, "/auth/mfa/enrol", {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ challenge_token: challenge }),
      }),
    );
  };
}

/** Second factor; on success the session's tokens go into HttpOnly cookies. */
export function mfaHandler(config: BffConfig): Handler {
  return async (request) => {
    const refused = refuseInFixtureMode(config) ?? refuseCrossSite(request, config);
    if (refused) return refused;
    const challenge = request.cookies.get(config.cookies.challenge)?.value;
    if (!challenge) return problem(401, "AUTH_REQUIRED", "Sign in again");
    const body = await readJson(request);
    const answer = await callBackend(config, "/auth/mfa", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        challenge_token: challenge,
        code: typeof body?.code === "string" ? body.code : null,
        recovery_code: typeof body?.recovery_code === "string" ? body.recovery_code : null,
      }),
    });
    if (!answer.ok) return relay(answer);
    const tokens = (await answer.json()) as SessionTokens;
    const response = NextResponse.json(
      { signed_in: true, recovery_codes: tokens.recovery_codes ?? null },
      { headers: { "cache-control": "no-store" } },
    );
    response.cookies.set(...accessCookie(config.cookies, tokens));
    response.cookies.set(...refreshCookie(config.cookies, tokens));
    response.cookies.delete(config.cookies.challenge);
    return response;
  };
}

/** New account: set a password with the one-time activation code. */
export function activateHandler(config: BffConfig): Handler {
  return async (request) => {
    const refused = refuseInFixtureMode(config) ?? refuseCrossSite(request, config);
    if (refused) return refused;
    const body = await readJson(request);
    return relay(
      await callBackend(config, "/auth/activate", {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({
          login_identifier: body?.login_identifier,
          activation_code: body?.activation_code,
          new_password: body?.new_password,
        }),
      }),
    );
  };
}

/** Sign out: the backend revokes the session; the cookies are cleared whatever it answers. */
export function logoutHandler(config: BffConfig): Handler {
  return async (request) => {
    const refused = refuseInFixtureMode(config) ?? refuseCrossSite(request, config);
    if (refused) return refused;
    const refreshToken = request.cookies.get(config.cookies.refresh)?.value;
    if (refreshToken) {
      await callBackend(config, "/auth/logout", {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
    const response = new NextResponse(null, { status: 204, headers: { "cache-control": "no-store" } });
    for (const name of [config.cookies.access, config.cookies.refresh, config.cookies.challenge]) response.cookies.delete(name);
    return response;
  };
}

// -------------------------------------------------------------------------------- catch-all
const SEGMENT = /^[A-Za-z0-9._~-]+$/;
const FORWARDED_REQUEST_HEADERS = ["content-type", "if-match", "idempotency-key", "traceparent", "accept"];

/** /bff/<path> -> <api base>/<path>, as the signed-in person. */
export function forwardHandler(config: BffConfig): CatchAllHandler {
  return async (request, context) => {
    const refused = refuseInFixtureMode(config);
    if (refused) return refused;
    const { path } = await context.params;
    if (
      path.length === 0 ||
      path[0] === "auth" ||
      !path.every((segment) => SEGMENT.test(segment) && segment !== "." && segment !== "..")
    ) {
      return problem(404, "NOT_FOUND", "Not found");
    }
    const method = request.method.toUpperCase();
    const mutating = !["GET", "HEAD"].includes(method);
    if (mutating) {
      const crossSite = refuseCrossSite(request, config);
      if (crossSite) return crossSite;
    }

    const headers: Record<string, string> = {};
    for (const name of FORWARDED_REQUEST_HEADERS) {
      const value = request.headers.get(name);
      if (value !== null) headers[name] = value;
    }
    if (mutating && !headers["idempotency-key"]) headers["idempotency-key"] = `bff-${randomUUID()}`;
    const body = mutating ? await request.text() : null;
    const target = `/${path.join("/")}${request.nextUrl.search}`;
    const send = (token: string | undefined) =>
      callBackend(config, target, { method, body, headers: token ? { ...headers, authorization: `Bearer ${token}` } : headers });

    const refreshToken = request.cookies.get(config.cookies.refresh)?.value;
    let token = request.cookies.get(config.cookies.access)?.value;
    // The access cookie lives as long as its token; with only the refresh cookie left, refresh first.
    let tokens = !token && refreshToken ? await config.refresh(refreshToken) : null;
    if (tokens) token = tokens.access_token;

    let answer = await send(token);
    if (answer.status === 401 && !tokens && refreshToken) {
      const failure = (await answer.clone().json().catch(() => null)) as { code?: string } | null;
      if (failure?.code === "TOKEN_EXPIRED") {
        tokens = await config.refresh(refreshToken);
        if (tokens) answer = await send(tokens.access_token);
      }
    }
    const response = await relay(answer);
    if (tokens) {
      response.cookies.set(...accessCookie(config.cookies, tokens));
      response.cookies.set(...refreshCookie(config.cookies, tokens));
    }
    return response;
  };
}

// ------------------------------------------------------------------------------------ proxy
/**
 * For the proxy, before a page renders (server components cannot set cookies): an access token
 * that has expired, or is about to, is exchanged with the refresh token. The request's cookies
 * are updated in place; the returned function applies the same change to the response.
 */
export async function renewBeforeRender(
  request: NextRequest,
  config: BffConfig,
): Promise<{ cookieHeader: string | null; apply: (response: NextResponse) => void }> {
  const nothing = { cookieHeader: null, apply: () => undefined };
  if (!config.enabled()) return nothing;
  const access = request.cookies.get(config.cookies.access)?.value;
  const refresh = request.cookies.get(config.cookies.refresh)?.value;
  if (!refresh || (access && secondsLeft(access) >= REFRESH_MARGIN_SECONDS)) return nothing;
  const tokens = await config.refresh(refresh);
  if (tokens) {
    request.cookies.set(config.cookies.access, tokens.access_token);
    request.cookies.set(config.cookies.refresh, tokens.refresh_token);
  } else {
    request.cookies.delete(config.cookies.access);
    request.cookies.delete(config.cookies.refresh);
  }
  return {
    cookieHeader: request.cookies.toString(),
    apply: (response) => {
      if (tokens) {
        response.cookies.set(...accessCookie(config.cookies, tokens));
        response.cookies.set(...refreshCookie(config.cookies, tokens));
      } else {
        response.cookies.delete(config.cookies.access);
        response.cookies.delete(config.cookies.refresh);
      }
    },
  };
}
