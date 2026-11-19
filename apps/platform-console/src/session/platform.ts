import "server-only";

import { isProblemDetails, type ProblemDetails } from "@ims/api-client";
import { cookies } from "next/headers";

import { platformBaseUrl } from "./config";
import { CONSOLE_COOKIES } from "./tokens";

/** A problem-details answer from the Platform Service (LLD 12). */
export class PlatformProblem extends Error {
  constructor(
    readonly status: number,
    readonly problem: ProblemDetails | null,
  ) {
    super(problem ? `${status} ${problem.code}` : `The Platform Service answered ${status}`);
  }
}

/**
 * Read from /platform/v1 for a server component, as the signed-in staff member. The access token
 * comes from the HttpOnly cookie; the proxy has already refreshed it if it was about to expire.
 * Changes go through the BFF route handlers instead (CSRF and Origin checks, LD-49).
 */
export async function readPlatform<T>(path: string, token?: string): Promise<T> {
  const bearer = token ?? (await cookies()).get(CONSOLE_COOKIES.access)?.value;
  if (!bearer) throw new PlatformProblem(401, null);
  const response = await fetch(`${platformBaseUrl()}/platform/v1${path}`, {
    headers: { authorization: `Bearer ${bearer}`, accept: "application/json" },
    cache: "no-store",
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new PlatformProblem(response.status, isProblemDetails(body) ? body : null);
  return body as T;
}
