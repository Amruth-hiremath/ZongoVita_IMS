import "server-only";

import { sessionSource } from "@/session/config";
import { readCore } from "@/session/core";

/**
 * The single switch point between sample data and IMS Core.
 *
 * Every read in the app goes through a function in src/data.
 *
 * - fromFixture(): the endpoint does not exist in Core yet; the value comes from src/fixtures and
 *   the call names the endpoint it stands in for.
 * - fromCore(): the endpoint exists. Signed in to Core the value is read from it as the user; in
 *   `fixtures` mode (sample personas, no tokens) the sample value is used instead.
 *
 * Docs/UI_Implementation.md lists every dependency declared either way.
 */
export interface Dependency {
  /** Method and path as in the LLD route tables, e.g. "GET /ui/v1/items". */
  endpoint: string;
  /** What the screen needs from it that the LLD does not spell out, if anything. */
  note?: string;
}

export async function fromFixture<T>(dependency: Dependency, value: T): Promise<T> {
  void dependency;
  return value;
}

/**
 * ``path`` is the Core path under /ui/v1 (with its query); ``live`` turns Core's answer into
 * what the screen shows; ``sample`` is the value for `fixtures` mode.
 */
export async function fromCore<Raw, T>(
  dependency: Dependency,
  path: string,
  live: (raw: Raw) => T,
  sample: () => T | Promise<T>,
): Promise<T> {
  void dependency;
  if (sessionSource() !== "core") return sample();
  return live(await readCore<Raw>(path));
}
