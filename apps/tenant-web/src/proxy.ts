import { NextResponse, type NextRequest } from "next/server";

import { PATH_HEADER, sessionSource } from "@/session/config";
import {
  ACCESS_COOKIE,
  accessCookie,
  REFRESH_COOKIE,
  REFRESH_MARGIN_SECONDS,
  refreshCookie,
  refreshOnce,
  secondsLeft,
} from "@/session/tokens";

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

  let refreshed: Awaited<ReturnType<typeof refreshOnce>> = null;
  let signedOut = false;
  const isPage = !request.nextUrl.pathname.startsWith("/bff/");
  if (isPage && sessionSource() === "core") {
    const access = request.cookies.get(ACCESS_COOKIE)?.value;
    const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
    if (refresh && (!access || secondsLeft(access) < REFRESH_MARGIN_SECONDS)) {
      refreshed = await refreshOnce(refresh);
      if (refreshed) {
        request.cookies.set(ACCESS_COOKIE, refreshed.access_token);
        request.cookies.set(REFRESH_COOKIE, refreshed.refresh_token);
      } else {
        request.cookies.delete(ACCESS_COOKIE);
        request.cookies.delete(REFRESH_COOKIE);
        signedOut = true;
      }
      requestHeaders.set("cookie", request.cookies.toString());
    }
  }

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  if (refreshed) {
    response.cookies.set(...accessCookie(refreshed));
    response.cookies.set(...refreshCookie(refreshed));
  } else if (signedOut) {
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(REFRESH_COOKIE);
  }
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
