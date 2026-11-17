import "server-only";

import { isProblemDetails, type ProblemDetails } from "@ims/api-client";
import { cookies } from "next/headers";

import { coreBaseUrl } from "./config";
import { ACCESS_COOKIE } from "./tokens";

/** A problem-details answer from Core (LLD 12). */
export class CoreProblem extends Error {
  constructor(
    readonly status: number,
    readonly problem: ProblemDetails | null,
  ) {
    super(problem ? `${status} ${problem.code}` : `IMS Core answered ${status}`);
  }

  get code(): string | null {
    return this.problem?.code ?? null;
  }
}

/**
 * Read from IMS Core's UI API for a server component, as the signed-in user. The access token
 * comes from the HttpOnly cookie; the proxy has already refreshed it if it was about to expire.
 * Writes go through the BFF route handlers instead (CSRF and Origin checks, LD-49).
 */
export async function readCore<T>(path: string, token?: string): Promise<T> {
  const bearer = token ?? (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!bearer) throw new CoreProblem(401, null);
  const response = await fetch(`${coreBaseUrl()}/ui/v1${path}`, {
    headers: { authorization: `Bearer ${bearer}`, accept: "application/json" },
    cache: "no-store",
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new CoreProblem(response.status, isProblemDetails(body) ? body : null);
  return body as T;
}
