/**
 * Where the signed-in staff session comes from, and where the Platform Service is.
 *
 * - `platform` (the default): the console's BFF holds the Platform Service's tokens in HttpOnly
 *   cookies and the session is GET /platform/v1/me (LLD 15: "the Platform Console uses the same
 *   structure with its own BFF to /platform/v1, requires MFA for all staff").
 * - `fixtures`: the wireframes' sample administrator and sample data, without a credential. For
 *   viewing the screens without a Platform Service; it must be switched on explicitly.
 *
 * Read on the server at request time (never inlined into the browser bundle).
 */
export type ConsoleSource = "platform" | "fixtures";

export function sessionSource(): ConsoleSource {
  const value = process.env.IMS_CONSOLE_SESSION_SOURCE ?? "platform";
  if (value !== "platform" && value !== "fixtures") {
    throw new Error(`IMS_CONSOLE_SESSION_SOURCE must be "platform" or "fixtures", not ${JSON.stringify(value)}`);
  }
  return value;
}

/** Base URL of the Platform Service, e.g. http://ims-platform:8081 (no trailing slash). */
export function platformBaseUrl(): string {
  return (process.env.IMS_PLATFORM_URL ?? "http://127.0.0.1:8081").replace(/\/+$/, "");
}

/**
 * The origin browsers use for the console, for the BFF's Origin check. Defaults to the origin of
 * the request itself; set IMS_PUBLIC_ORIGIN when a reverse proxy rewrites the Host header.
 */
export function publicOrigin(requestUrl: string): string {
  return process.env.IMS_PUBLIC_ORIGIN?.replace(/\/+$/, "") ?? new URL(requestUrl).origin;
}

/** Request header the proxy sets with the path, for the console layout's guard. */
export const PATH_HEADER = "x-ims-pathname";
