/** FIXTURE: sample rows from wireframe F21. Temporary; see src/data/source.ts. */
import type { LocationRow } from "@/data/locations";

export const locationList: { rows: LocationRow[] } = {
  rows: [
    {
      id: "018f6f2a-0000-7000-8000-0000000000b1",
      location_code: "WH-BLR-01",
      name: "Bengaluru Central Warehouse",
      type_label: "Warehouse",
      city: "Bengaluru, KA",
      item_count: 1284,
      stock_value: "2864200",
      sku_rule: "own prefix",
      status: "live",
      users: {
        total: 4,
        by_type: [
          { type_label: "Type 3", count: 3 },
          { type_label: "Type 2", count: 1 },
        ],
      },
    },
    {
      id: "018f6f2a-0000-7000-8000-0000000000b2",
      location_code: "WH-PUN-02",
      name: "Pune Plant Store",
      type_label: "Plant Store",
      city: "Pune, MH",
      item_count: 862,
      stock_value: "928400",
      sku_rule: "own prefix",
      status: "staged",
      users: null,
    },
    {
      id: "018f6f2a-0000-7000-8000-0000000000b3",
      location_code: "ST-MAA-01",
      name: "Chennai Retail Store",
      type_label: "Retail Store",
      city: "Chennai, TN",
      item_count: 431,
      stock_value: "410800",
      sku_rule: "own prefix",
      status: "staged",
      users: null,
    },
    {
      id: "018f6f2a-0000-7000-8000-0000000000b4",
      location_code: "WH-HYD-03",
      name: "Hyderabad Depot",
      type_label: "Transit Depot",
      city: "Hyderabad, TS",
      item_count: 203,
      stock_value: "83000",
      sku_rule: "transit only",
      status: "staged",
      users: null,
    },
  ],
};
