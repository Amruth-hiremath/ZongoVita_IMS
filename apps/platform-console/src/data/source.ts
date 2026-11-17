import "server-only";

/**
 * The single switch point between sample data and IMS Core.
 *
 * Every read in the app goes through a function in src/data. Until the matching endpoint exists
 * in Core, that function returns a value from src/fixtures via fromFixture(), naming the
 * endpoint it stands in for. To connect a screen, replace the fromFixture() call with a call to
 * the endpoint through the BFF; the screen itself does not change.
 *
 * Docs/UI_Implementation.md lists every dependency declared this way.
 */
export interface Dependency {
  /** Method and path as in the LLD route tables, e.g. "GET /ui/v1/items". */
  endpoint: string;
  /** What the screen needs from it that the LLD does not spell out, if anything. */
  note?: string;
}

export const DATA_SOURCE = "fixtures" as const;

export async function fromFixture<T>(dependency: Dependency, value: T): Promise<T> {
  void dependency;
  return value;
}
