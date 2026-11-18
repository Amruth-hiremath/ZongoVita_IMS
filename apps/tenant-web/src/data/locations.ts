import "server-only";

import { locationList } from "@/fixtures/locations";

import type { SitePage } from "./sites";
import { fromCore } from "./source";

/**
 * Go-live state of a location: the LLD's site status (LLD 5.1) as F21 labels it, active sites
 * being "live" (Q9: multi-location from day one, the rest staged).
 */
export type LocationStatus = "live" | "staged" | "inactive";

export interface LocationRow {
  id: string;
  location_code: string;
  name: string;
  /** Display label of the location type ("Warehouse"); not in the LLD's site record, so null from Core. */
  type_label: string | null;
  /** Not in the LLD's site record, so null from Core. */
  city: string | null;
  /** Stock figures come with Inventory Core (unit 9); null until then. */
  item_count: number | null;
  /** Decimal string in the customer's currency; null until Inventory Core (unit 9). */
  stock_value: string | null;
  /** How SKUs are numbered here; numbering schemes arrive with the catalogue (unit 8). */
  sku_rule: string | null;
  status: LocationStatus;
  /** Users assigned at the site, by user type; null while the site is not live. */
  users: { total: number; by_type: { type_label: string; count: number }[] } | null;
}

export interface LocationList {
  rows: LocationRow[];
  live: number;
  staged: number;
  /** Live from Core, or the wireframe's sample rows. */
  source: "core" | "fixtures";
}

/** What GET /ui/v1/users carries that F21 counts. */
interface CoreUserPage {
  items: {
    status: "invited" | "active" | "suspended" | "deactivated";
    assignments: { site_id: string | null; user_type_no: number | null }[];
  }[];
}

const STATUS: Record<"staged" | "active" | "inactive", LocationStatus> = {
  active: "live",
  staged: "staged",
  inactive: "inactive",
};

function usersBySite(page: CoreUserPage | null): Map<string, Map<string, Set<number>>> {
  // site -> type label -> user indexes, counting each user once per site and type
  const sites = new Map<string, Map<string, Set<number>>>();
  page?.items.forEach((user, index) => {
    if (user.status !== "active" && user.status !== "invited") return;
    for (const assignment of user.assignments) {
      if (assignment.site_id === null) continue;
      const label = assignment.user_type_no ? `Type ${assignment.user_type_no}` : "Custom";
      const types = sites.get(assignment.site_id) ?? new Map<string, Set<number>>();
      types.set(label, (types.get(label) ?? new Set()).add(index));
      sites.set(assignment.site_id, types);
    }
  });
  return sites;
}

/** Assigned users per site, read only for people who may list users (access.user.manage). */
function assignedUsers(withUsers: boolean): Promise<CoreUserPage | null> {
  if (!withUsers) return Promise.resolve(null);
  return fromCore<CoreUserPage, CoreUserPage | null>(
    { endpoint: "GET /ui/v1/users", note: "F21 counts the users assigned at each site, by user type." },
    "/users?limit=200",
    (page) => page,
    () => null,
  );
}

/** F21 Locations: the customer's sites. */
export async function listLocations({ withUsers }: { withUsers: boolean }): Promise<LocationList> {
  const users = usersBySite(await assignedUsers(withUsers));
  return fromCore<SitePage, LocationList>(
    {
      endpoint: "GET /ui/v1/sites",
      note:
        "The frame calls sites 'locations'. Type and city are not in the LLD's site record (code, name, timezone, " +
        "status); item count and stock value need Inventory Core (unit 9); the SKU rule needs numbering schemes (unit 8).",
    },
    "/sites?limit=200",
    (page) => {
      const rows: LocationRow[] = page.items.map((site) => {
        const types = users.get(site.id);
        const everyone = new Set([...(types?.values() ?? [])].flatMap((set) => [...set]));
        return {
          id: site.id,
          location_code: site.code,
          name: site.name,
          type_label: null,
          city: null,
          item_count: null,
          stock_value: null,
          sku_rule: null,
          status: STATUS[site.status],
          users:
            site.status === "active" && withUsers
              ? {
                  total: everyone.size,
                  by_type: [...(types?.entries() ?? [])]
                    .map(([type_label, set]) => ({ type_label, count: set.size }))
                    .sort((a, b) => b.count - a.count || a.type_label.localeCompare(b.type_label)),
                }
              : null,
        };
      });
      return {
        rows,
        live: rows.filter((row) => row.status === "live").length,
        staged: rows.filter((row) => row.status === "staged").length,
        source: "core",
      };
    },
    () => ({
      ...locationList,
      live: locationList.rows.filter((row) => row.status === "live").length,
      staged: locationList.rows.filter((row) => row.status === "staged").length,
      source: "fixtures",
    }),
  );
}
