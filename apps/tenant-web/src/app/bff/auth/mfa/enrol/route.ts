import { type NextRequest } from "next/server";

import { callCore, problem, refuseCrossSite, refuseInFixtureMode, relay } from "@/bff/http";
import { CHALLENGE_COOKIE } from "@/session/tokens";

/**
 * First sign-in: create the authenticator secret (POST /ui/v1/auth/mfa/enrol, D-16). The secret
 * and its otpauth URI are returned once, to be shown to the user; the first code confirms them.
 */
export async function POST(request: NextRequest) {
  const refused = refuseInFixtureMode() ?? refuseCrossSite(request);
  if (refused) return refused;
  const challenge = request.cookies.get(CHALLENGE_COOKIE)?.value;
  if (!challenge) return problem(401, "AUTH_REQUIRED", "Sign in again");
  return relay(
    await callCore("/auth/mfa/enrol", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ challenge_token: challenge }),
    }),
  );
}
