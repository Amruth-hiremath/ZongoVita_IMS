import { NextResponse, type NextRequest } from "next/server";

import { callCore, readJson, refuseCrossSite, refuseInFixtureMode, relay } from "@/bff/http";
import { CHALLENGE_COOKIE, cookieOptions } from "@/session/tokens";

interface LoginAnswer {
  status: "mfa_required" | "mfa_enrolment_required";
  challenge_token: string;
  challenge_expires_in: number;
}

/**
 * Password step (LLD 6.2): POST /ui/v1/auth/login. The single-use MFA challenge token is kept in
 * an HttpOnly cookie for the code step; the browser only learns which step comes next.
 */
export async function POST(request: NextRequest) {
  const refused = refuseInFixtureMode() ?? refuseCrossSite(request);
  if (refused) return refused;
  const body = (await readJson(request)) as { login_identifier?: unknown; password?: unknown } | null;
  const answer = await callCore("/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ login_identifier: body?.login_identifier, password: body?.password }),
  });
  if (!answer.ok) return relay(answer);
  const login = (await answer.json()) as LoginAnswer;
  const response = NextResponse.json({ status: login.status }, { headers: { "cache-control": "no-store" } });
  response.cookies.set(CHALLENGE_COOKIE, login.challenge_token, cookieOptions({ maxAge: login.challenge_expires_in }));
  return response;
}
