import { NextResponse, type NextRequest } from "next/server";

import { callCore, problem, readJson, refuseCrossSite, refuseInFixtureMode, relay } from "@/bff/http";
import { accessCookie, CHALLENGE_COOKIE, refreshCookie, type SessionTokens } from "@/session/tokens";

/**
 * Second factor (LLD 6.2, LD-79): an authenticator code or a recovery code. On success Core opens
 * the session; its tokens go into HttpOnly cookies and never reach the page. Recovery codes, shown
 * once after enrolment, are passed back to be displayed.
 */
export async function POST(request: NextRequest) {
  const refused = refuseInFixtureMode() ?? refuseCrossSite(request);
  if (refused) return refused;
  const challenge = request.cookies.get(CHALLENGE_COOKIE)?.value;
  if (!challenge) return problem(401, "AUTH_REQUIRED", "Sign in again");
  const body = (await readJson(request)) as { code?: unknown; recovery_code?: unknown } | null;
  const answer = await callCore("/auth/mfa", {
    method: "POST",
    headers: { "content-type": "application/json" },
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
  response.cookies.set(...accessCookie(tokens));
  response.cookies.set(...refreshCookie(tokens));
  response.cookies.delete(CHALLENGE_COOKIE);
  return response;
}
