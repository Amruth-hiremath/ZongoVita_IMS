import { randomUUID } from "node:crypto";

import { type NextRequest } from "next/server";

import { callCore, problem, refuseCrossSite, refuseInFixtureMode, relay } from "@/bff/http";
import { accessCookie, ACCESS_COOKIE, REFRESH_COOKIE, refreshCookie, refreshOnce } from "@/session/tokens";

/**
 * /bff/<path> -> IMS Core /ui/v1/<path> (LLD 15, LD-49).
 *
 * - Adds the bearer token from the HttpOnly cookie.
 * - Writes need X-IMS-CSRF and a matching Origin; each user action carries an Idempotency-Key,
 *   generated here when the page did not send one (LLD 12).
 * - On TOKEN_EXPIRED the session is refreshed once and the call replayed with the same key;
 *   otherwise the answer goes back as it is, and the page sends the user to /login.
 * - Credential routes are not forwarded: they would hand tokens to page JavaScript. They have
 *   their own handlers under /bff/auth.
 */
type Context = { params: Promise<{ path: string[] }> };

const SEGMENT = /^[A-Za-z0-9._~-]+$/;
const FORWARDED_REQUEST_HEADERS = ["content-type", "if-match", "idempotency-key", "traceparent", "accept"];

async function forward(request: NextRequest, context: Context): Promise<Response> {
  const refused = refuseInFixtureMode();
  if (refused) return refused;
  const { path } = await context.params;
  if (path.length === 0 || path[0] === "auth" || !path.every((segment) => SEGMENT.test(segment) && segment !== "." && segment !== "..")) {
    return problem(404, "NOT_FOUND", "Not found");
  }
  const method = request.method.toUpperCase();
  const mutating = !["GET", "HEAD"].includes(method);
  if (mutating) {
    const crossSite = refuseCrossSite(request);
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
    callCore(target, {
      method,
      body,
      headers: token ? { ...headers, authorization: `Bearer ${token}` } : headers,
    });

  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  let token = request.cookies.get(ACCESS_COOKIE)?.value;
  // The access cookie lives as long as its token; with only the refresh cookie left, refresh first.
  let tokens = !token && refreshToken ? await refreshOnce(refreshToken) : null;
  if (tokens) token = tokens.access_token;

  let answer = await send(token);
  if (answer.status === 401 && !tokens && refreshToken) {
    const failure = (await answer.clone().json().catch(() => null)) as { code?: string } | null;
    if (failure?.code === "TOKEN_EXPIRED") {
      tokens = await refreshOnce(refreshToken);
      if (tokens) answer = await send(tokens.access_token);
    }
  }
  const response = await relay(answer);
  if (tokens) {
    response.cookies.set(...accessCookie(tokens));
    response.cookies.set(...refreshCookie(tokens));
  }
  return response;
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
