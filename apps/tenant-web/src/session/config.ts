/**
 * Where the signed-in session comes from, and where IMS Core is.
 *
 * - `core` (the default): the BFF holds Core's tokens in HttpOnly cookies and the session is
 *   GET /ui/v1/me (LLD 15, LD-49).
 * - `fixtures`: the wireframe personas, chosen on the sign-in screen without a credential. For
 *   viewing screens whose backend does not exist yet; it must be switched on explicitly.
 *
 * Read on the server at request time (never inlined into the browser bundle).
 */
export type SessionSource = "core" | "fixtures";

export function sessionSource(): SessionSource {
  const value = process.env.IMS_SESSION_SOURCE ?? "core";
  if (value !== "core" && value !== "fixtures") {
    throw new Error(`IMS_SESSION_SOURCE must be "core" or "fixtures", not ${JSON.stringify(value)}`);
  }
  return value;
}

/** Base URL of IMS Core's UI API host, e.g. http://ims-core:8080 (no trailing slash). */
export function coreBaseUrl(): string {
  return (process.env.IMS_CORE_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
}

/**
 * The origin browsers use for this app, for the BFF's Origin check. Defaults to the origin of
 * the request itself; set IMS_PUBLIC_ORIGIN when a reverse proxy rewrites the Host header.
 */
export function publicOrigin(requestUrl: string): string {
  return process.env.IMS_PUBLIC_ORIGIN?.replace(/\/+$/, "") ?? new URL(requestUrl).origin;
}

/** Request header the proxy sets with the path, for the (app) layout's permission guard. */
export const PATH_HEADER = "x-ims-pathname";
