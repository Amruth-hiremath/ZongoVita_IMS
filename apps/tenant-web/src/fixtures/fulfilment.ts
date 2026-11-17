/** FIXTURE: sample data from wireframe F29. Temporary; see src/data/source.ts. */
import type { FulfilmentQueueData } from "@/data/fulfilment";

export const fulfilmentQueue: FulfilmentQueueData = {
  rows: [
    {
      queue_id: "018f6f2a-0000-7000-8000-00000000f417",
      request_ref: "REQ-0417",
      requester: "Rahul Verma",
      site_code: "WH-BLR-01",
      lines_summary: "1 line · 6 pcs",
      locked_label: "10:12 today",
      sla_label: "Today 17:00",
      state: { kind: "ready_to_pick", label: "Ready to pick" },
    },
    {
      queue_id: "018f6f2a-0000-7000-8000-00000000f413",
      request_ref: "REQ-0413",
      requester: "Ananya Iyer",
      site_code: "ST-MAA-01",
      lines_summary: "1 line · 24 pairs",
      locked_label: "24 Sep 16:20",
      sla_label: "Today 17:00",
      state: { kind: "ready_to_pick", label: "Ready to pick" },
    },
    {
      queue_id: "018f6f2a-0000-7000-8000-00000000f416",
      request_ref: "REQ-0416",
      requester: "Kavita Rao",
      site_code: "WH-PUN-02",
      lines_summary: "1 line · 3 tubs",
      locked_label: "11:35 today",
      sla_label: "Sun 12:00",
      state: { kind: "picking", label: "Picking" },
    },
  ],
  pick_lists: {
    "REQ-0417": {
      request_ref: "REQ-0417",
      requester: "Rahul Verma",
      department: "Maintenance",
      location_code: "WH-BLR-01",
      lines: [
        {
          kind: "stocked",
          item_code: "SPB-6204",
          name: "Ball Bearing 6204-2RS",
          qty: "6",
          uom: "pcs",
          lot: "LOT-SPB-0124",
          bin_label: "bin A-12 · BLR-01",
          scanned: true,
        },
        {
          kind: "external",
          item_code: "HYD-HOS-12",
          name: "Hydraulic Hose 12 mm",
          qty: "2",
          uom: "m",
          external_request_ref: "EPR-0034",
        },
      ],
      issue_qty: "6",
      issue_uom: "pcs",
      ack_reminder_label: "daily 09:00 to the requester after 48 h",
    },
  },
};
