import { type NextRequest } from "next/server";

import { callCore, readJson, refuseCrossSite, refuseInFixtureMode, relay } from "@/bff/http";

/** New user: set a password with the one-time activation code (POST /ui/v1/auth/activate). */
export async function POST(request: NextRequest) {
  const refused = refuseInFixtureMode() ?? refuseCrossSite(request);
  if (refused) return refused;
  const body = (await readJson(request)) as Record<string, unknown> | null;
  return relay(
    await callCore("/auth/activate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        login_identifier: body?.login_identifier,
        activation_code: body?.activation_code,
        new_password: body?.new_password,
      }),
    }),
  );
}
