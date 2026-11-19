import "server-only";

import { cache } from "react";

import { sessionSource } from "@/session/config";
import { readPlatform } from "@/session/platform";

/** One read per path and request, however many components ask (the layout and the page share). */
const readOnce = cache((path: string): Promise<unknown> => readPlatform(path));

/**
 * The single switch point between sample data and the Platform Service.
 *
 * Every read in the app goes through a function in src/data.
 *
 * - fromFixture(): no /platform/v1 resource provides the data; the value comes from src/fixtures
 *   and the call names the endpoint it stands in for.
 * - fromPlatform(): the resource exists. Signed in to the Platform Service the value is read from
 *   it as the staff member; in `fixtures` mode the sample value is used instead.
 *
 * Docs/UI_Implementation.md lists every dependency declared either way.
 */
export interface Dependency {
  /** Method and path as in the LLD route tables, e.g. "GET /platform/v1/customers". */
  endpoint: string;
  /** What the screen needs from it that the LLD does not spell out, if anything. */
  note?: string;
}

export async function fromFixture<T>(dependency: Dependency, value: T): Promise<T> {
  void dependency;
  return value;
}

/**
 * ``read`` fetches what the screen needs from /platform/v1 (one or more paths, through
 * readPlatform); ``sample`` is the value for `fixtures` mode.
 */
export async function fromPlatform<T>(
  dependency: Dependency,
  read: (get: <Raw>(path: string) => Promise<Raw>) => Promise<T>,
  sample: () => T | Promise<T>,
): Promise<T> {
  void dependency;
  if (sessionSource() !== "platform") return sample();
  return read(<Raw>(path: string) => readOnce(path) as Promise<Raw>);
}
