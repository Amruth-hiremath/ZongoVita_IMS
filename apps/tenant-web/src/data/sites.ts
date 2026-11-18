import "server-only";

import { fromCore } from "./source";

/** A site as GET /ui/v1/sites returns it (LLD 5.1 org.sites). */
export interface Site {
  id: string;
  code: string;
  name: string;
  timezone: string;
  status: "staged" | "active" | "inactive";
  version: number;
}

export interface SitePage {
  items: Site[];
  next_cursor: string | null;
}

/** Every site by id, to show codes where other records carry a site id (F22 location scope). */
export function siteDirectory(): Promise<Map<string, Site>> {
  return fromCore<SitePage, Map<string, Site>>(
    { endpoint: "GET /ui/v1/sites", note: "Site codes for records that carry a site id." },
    "/sites?limit=200",
    (page) => new Map(page.items.map((site) => [site.id, site])),
    () => new Map(),
  );
}
