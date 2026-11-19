import { NextResponse, type NextRequest } from "next/server";

import { renewBeforeRender } from "@ims/web-session";

import { tenantBff } from "@/bff/config";
import { PATH_HEADER } from "@/session/config";

function contentSecurityPolicy(nonce: string, isDev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' ${isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}

/**
 * Runs before every page and BFF request.
 *
 * 1. Per-request Content Security Policy with a nonce (LD-49, AD-65). Scripts run only with the
 *    request's nonce; styles come from the app's own stylesheets; the page cannot be framed;
 *    nothing is loaded from another origin. In development React needs eval for its debugging
 *    overlays and the dev server injects style tags, so those two relaxations apply there only.
 * 2. Session upkeep for pages in `core` mode: an access token that has expired, or is about to,
 *    is exchanged with the refresh token before the page renders (server components cannot set
 *    cookies), so the page reads /ui/v1/me with a live token. BFF routes refresh on their own.
 */
export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);
  requestHeaders.set(PATH_HEADER, request.nextUrl.pathname);

  // Pages only: BFF routes refresh on their own.
  const renewal = request.nextUrl.pathname.startsWith("/bff/")
    ? null
    : await renewBeforeRender(request, tenantBff);
  if (renewal?.cookieHeader) requestHeaders.set("cookie", renewal.cookieHeader);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  renewal?.apply(response);
  return response;
}

export const config = {
  matcher: [
    {
      // Everything except static assets and prefetches, which need no policy of their own.
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
