import { NextResponse, type NextRequest } from "next/server";

import { callCore, refuseCrossSite, refuseInFixtureMode } from "@/bff/http";
import { ACCESS_COOKIE, CHALLENGE_COOKIE, REFRESH_COOKIE } from "@/session/tokens";

/** Sign out (LLD 6.2): Core revokes the session; the cookies are cleared whatever it answers. */
export async function POST(request: NextRequest) {
  const refused = refuseInFixtureMode() ?? refuseCrossSite(request);
  if (refused) return refused;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await callCore("/auth/logout", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }
  const response = new NextResponse(null, { status: 204, headers: { "cache-control": "no-store" } });
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CHALLENGE_COOKIE]) response.cookies.delete(name);
  return response;
}
