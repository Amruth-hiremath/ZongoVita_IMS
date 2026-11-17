/**
 * Every screen drawn in the wireframes (Docs/ZongoVita-IMS.zip) and where it lives.
 *
 * One table drives the smoke tests and the screenshot capture, so a frame cannot be
 * implemented without being checked. `title` is the page heading exactly as drawn.
 */
export type Persona = "type1" | "type2" | "type3";

export interface Screen {
  /** Wireframe frame, as named in the ZIP. */
  frame: string;
  route: string;
  /** Sample persona that sees this screen; null for screens outside the signed-in shell. */
  persona: Persona | null;
  title: string;
}

export const tenantScreens: Screen[] = [
  { frame: "F03-Login", route: "/login", persona: null, title: "IMS" },
  { frame: "F04-Dashboard-Type-1", route: "/dashboard", persona: "type1", title: "Dashboard — Type 1" },
  { frame: "F05-Dashboard-Type-2", route: "/dashboard", persona: "type2", title: "Inventory Overview" },
  { frame: "F48-Store-Dashboard-Type-3", route: "/dashboard", persona: "type3", title: "Namaste, Suresh" },
  { frame: "F07-Items-List", route: "/items", persona: "type2", title: "Items & Catalog" },
  { frame: "F08-Item-Add-Configure", route: "/items/new", persona: "type1", title: "Add / Configure Item" },
  { frame: "F09-Item-Detail", route: "/items/SPB-6204", persona: "type2", title: "Ball Bearing 6204-2RS" },
  { frame: "F60-IT-Asset-Mapping", route: "/items/assets", persona: "type1", title: "IT Asset Mapping" },
  { frame: "F25-Category-Management", route: "/categories", persona: "type1", title: "Category & Subcategory Management" },
  { frame: "F37-Vendors-List", route: "/vendors", persona: "type1", title: "Vendors" },
  { frame: "F38-Vendor-Detail", route: "/vendors/VD-0028", persona: "type1", title: "Shakti Bearings Pvt Ltd" },
  { frame: "F39-Vendor-Onboarding", route: "/vendors/onboarding/VD-0043", persona: "type1", title: "Vendor Onboarding — VD-0043" },
  { frame: "F40-Purchase-Records", route: "/purchase-records", persona: "type1", title: "Purchase Records" },
  { frame: "F41-Purchase-Record-Detail", route: "/purchase-records/PO-2214", persona: "type1", title: "Purchase Record — PO-2214" },
  { frame: "F33-Supplier-Quality-Register", route: "/quality-register", persona: "type1", title: "Supplier Quality Register" },
  { frame: "F21-Locations", route: "/locations", persona: "type1", title: "Locations" },
  { frame: "F22-Users-Types", route: "/users", persona: "type1", title: "Users & User Types" },
  { frame: "F36-Privilege-Matrix", route: "/privileges", persona: "type1", title: "Privilege Matrix" },
  { frame: "F23-Approval-Config", route: "/approvals/configuration", persona: "type1", title: "Approval Workflow Configuration" },
  { frame: "F61-Workflow-Builder", route: "/approvals/workflows/WF-013", persona: "type1", title: "Workflow Builder — WF-013 · Transfer approval" },
  { frame: "F27-Approval-Workspace", route: "/approvals", persona: "type2", title: "Approval Workspace — REQ-0417" },
  { frame: "F28-Lock-Reservation-View", route: "/issuance", persona: "type2", title: "Locks & Reservations" },
  { frame: "F29-Store-Fulfilment-Queue", route: "/fulfilment", persona: "type3", title: "Store Fulfilment Queue" },
  { frame: "F11-Issue-Stock", route: "/scan-issue", persona: "type3", title: "Issue Stock — ISS-0342" },
  { frame: "F12-Issue-Blocked-States", route: "/scan-issue/guard-rails", persona: "type3", title: "Issue — Guard-rail States" },
  { frame: "F42-Receive-Type-2", route: "/receive", persona: "type2", title: "Receiving — Inward Pipeline" },
  { frame: "F10-Receive-Stock", route: "/receive", persona: "type3", title: "Receive Stock — GRN-2081" },
  { frame: "F32-Quarantine-Queue", route: "/quarantine", persona: "type3", title: "Quarantine Validation Queue" },
  { frame: "F43-Returns-Type-2", route: "/returns", persona: "type2", title: "Returns — Lifecycle & Dispositions" },
  { frame: "F49-Store-Returns-Type-3", route: "/returns", persona: "type3", title: "Returns — Store Processing" },
  { frame: "F15-Transfer-Lifecycle", route: "/transfers", persona: "type2", title: "TRF-0092 — BLR-01 → PUN-02" },
  { frame: "F14-Transfer-Request", route: "/transfers", persona: "type3", title: "Transfer — New Request" },
  { frame: "F17-Variance-Review", route: "/stock-counts", persona: "type2", title: "Variance Review — CC-0057" },
  { frame: "F16-Stock-Count", route: "/stock-counts", persona: "type3", title: "Stock Count — CC-0057" },
  { frame: "F18-Alerts-Reorder", route: "/alerts", persona: "type2", title: "Alerts & Reorder Suggestions" },
  { frame: "F19-Reorder-Rule-Builder", route: "/alerts/reorder-rules/SPB-6204", persona: "type2", title: "Reorder Rule — SPB-6204" },
  { frame: "F44-Reports-Type-2", route: "/reports", persona: "type2", title: "Reports — Catalog & Deliveries" },
  { frame: "F24-Audit-Trail-v1", route: "/audit", persona: "type1", title: "Audit Trail" },
  { frame: "F24-Audit-Trail", route: "/audit", persona: "type2", title: "Audit Trail" },
  { frame: "F50-Store-Audit-Type-3", route: "/audit", persona: "type3", title: "Audit Trail — WH-BLR-01" },
];

/** The same screens reached through their own address rather than the sidebar entry. */
export const tenantDeepLinks: Screen[] = [
  { frame: "F15-Transfer-Lifecycle", route: "/transfers/TRF-0092", persona: "type2", title: "TRF-0092 — BLR-01 → PUN-02" },
  { frame: "F14-Transfer-Request", route: "/transfers/new", persona: "type3", title: "Transfer — New Request" },
  { frame: "F16-Stock-Count", route: "/stock-counts/CC-0057", persona: "type3", title: "Stock Count — CC-0057" },
  { frame: "F17-Variance-Review", route: "/stock-counts/CC-0057/variance", persona: "type2", title: "Variance Review — CC-0057" },
];

/** Detail routes hold only the record drawn in the wireframe; anything else is not found. */
export const tenantUnknownRecords: { route: string; persona: Persona }[] = [
  { route: "/items/NO-SUCH-ITEM", persona: "type2" },
  { route: "/vendors/VD-9999", persona: "type1" },
  { route: "/purchase-records/PO-0000", persona: "type1" },
  { route: "/approvals/workflows/WF-999", persona: "type1" },
  { route: "/transfers/TRF-0000", persona: "type2" },
  { route: "/stock-counts/CC-0000", persona: "type3" },
  { route: "/alerts/reorder-rules/NO-SUCH-ITEM", persona: "type2" },
];

export const platformScreens: Screen[] = [
  { frame: "F51-Platform-Overview", route: "/overview", persona: null, title: "Platform Overview" },
  { frame: "F52-Platform-Licenses", route: "/licenses", persona: null, title: "Licenses & Plans" },
  { frame: "F53-Platform-Config", route: "/config", persona: null, title: "Platform Config" },
];
