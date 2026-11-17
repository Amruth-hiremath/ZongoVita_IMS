import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { coreBaseUrl, publicOrigin, sessionSource } from "@/session/config";

/**
 * Backend-for-frontend helpers (LD-49; LLD 15 "BFF").
 *
 * The browser talks only to this app. Route handlers under /bff forward to IMS Core's UI API,
 * adding the bearer token from the HttpOnly cookie. Mutating calls must carry the X-IMS-CSRF
 * header and an Origin equal to this app's own; with SameSite=Lax cookies that keeps other
 * sites from acting with the user's session.
 */
export const CSRF_HEADER = "x-ims-csrf";

export function problem(status: number, code: string, title: string, detail?: string): NextResponse {
  return NextResponse.json(
    { type: "about:blank", title, status, code, detail: detail ?? null, errors: [] },
    { status, headers: { "content-type": "application/problem+json", "cache-control": "no-store" } },
  );
}

/** Refuses a cross-site or scripted-from-elsewhere write before anything is forwarded. */
export function refuseCrossSite(request: NextRequest): NextResponse | null {
  if (request.headers.get(CSRF_HEADER) !== "1") {
    return problem(403, "PERMISSION_DENIED", "Missing CSRF header", `Send ${CSRF_HEADER}: 1 with every change.`);
  }
  const origin = request.headers.get("origin");
  if (origin === null || origin !== publicOrigin(request.url)) {
    return problem(403, "PERMISSION_DENIED", "Cross-site request refused");
  }
  return null;
}

/** The BFF exists only when the app talks to Core. */
export function refuseInFixtureMode(): NextResponse | null {
  return sessionSource() === "core" ? null : problem(404, "NOT_FOUND", "Not found");
}

export async function callCore(
  path: string,
  init: { method: string; body?: string | null; headers?: Record<string, string> },
): Promise<Response> {
  try {
    return await fetch(`${coreBaseUrl()}/ui/v1${path}`, {
      method: init.method,
      body: init.body ?? null,
      headers: init.headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return new Response(
      JSON.stringify({
        type: "about:blank",
        title: "IMS Core is unreachable",
        status: 503,
        code: "DB_BUSY",
        detail: null,
        errors: [],
      }),
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

export async function readJson(request: NextRequest): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return null;
  }
}
