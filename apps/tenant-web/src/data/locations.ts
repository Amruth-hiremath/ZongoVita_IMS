import "server-only";

import { locationList } from "@/fixtures/locations";

import { fromFixture } from "./source";

/** Go-live state of a location (Q9: multi-location from day one, the rest staged). */
export type LocationStatus = "live" | "staged";

export interface LocationRow {
  id: string;
  location_code: string;
  name: string;
  /** Display label of the location type ("Warehouse", "Plant Store", "Transit Depot"). */
  type_label: string;
  city: string;
  item_count: number;
  /** Decimal string in the customer's currency. */
  stock_value: string;
  /** How SKUs are numbered here, as the list shows it ("own prefix", "transit only"). */
  sku_rule: string;
  status: LocationStatus;
  /** Users scoped to the location, by user type; null while the location is not live. */
  users: { total: number; by_type: { type_label: string; count: number }[] } | null;
}

export interface LocationList {
  rows: LocationRow[];
}

/** F21 Locations. */
export function listLocations(): Promise<LocationList> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/sites",
      note:
        "The frame calls sites 'locations'. Each row needs type, city, item count, stock value, SKU numbering rule, " +
        "go-live status (live / staged) and a count of assigned users by user type.",
    },
    locationList,
  );
}
