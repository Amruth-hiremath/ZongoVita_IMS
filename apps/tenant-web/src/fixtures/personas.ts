/**
 * FIXTURE: the three people the wireframes are drawn for, as GET /ui/v1/me would describe them.
 *
 * Temporary. Identity (unit 2) and access control (unit 3) replace this with the real session:
 * the BFF holds the tokens in HttpOnly cookies and /ui/v1/me returns effective permissions and
 * the licence state. Permission sets below are the LLD's seeded user types (LLD 5.1).
 */
import { PERMISSIONS, type Me, type PermissionCode } from "@ims/api-client";

export type PersonaId = "type1" | "type2" | "type3";

const ALL = Object.keys(PERMISSIONS) as PermissionCode[];
const VIEWS = ALL.filter((code) => code.endsWith(".view"));

const SITES = [
  { id: "018f6f2a-0000-7000-8000-0000000000b1", code: "WH-BLR-01", name: "Bengaluru" },
  { id: "018f6f2a-0000-7000-8000-0000000000b2", code: "WH-PUN-02", name: "Pune" },
  { id: "018f6f2a-0000-7000-8000-0000000000b3", code: "ST-MAA-01", name: "Chennai" },
  { id: "018f6f2a-0000-7000-8000-0000000000b4", code: "WH-HYD-03", name: "Hyderabad" },
];
const BLR = SITES[0]!;

const LICENCE: Me["licence"] = {
  state: "active",
  grace_ends_at: null,
  gxp_mode: false,
  modules: ["ims.core", "ims.replenishment", "ims.supplier_register", "ims.integration"],
};

function grant(codes: PermissionCode[], siteIds: string[] | null): Me["permissions"] {
  return codes.map((code) => ({ code, site_ids: PERMISSIONS[code].siteScoped ? siteIds : null }));
}

// User Type 2: view all; approve issuance, transfers, adjustments, verdicts, categories,
// thresholds; manage vendors and formulas.
//
// The wireframes also give Type 2 item creation ("+ Add item" on F07; "Create / configure
// items: Yes" on F22), which the LLD's seeded Type 2 does not list. The sample persona follows
// the wireframes here; the seeded default is a point to confirm (Docs/UI_Implementation.md).
const TYPE_2: PermissionCode[] = [
  ...VIEWS,
  "catalog.item.create",
  "catalog.item.edit",
  "issuance.request.view_all",
  "issuance.request.approve",
  "transfers.transfer.approve",
  "counts.adjustment.approve",
  "receiving.grn.inspect",
  "returns.verdict.decide",
  "quality.case.dispose",
  "catalog.taxonomy.approve",
  "replenishment.threshold.approve",
  "replenishment.formula.manage",
  "purchasing.vendor.manage",
  "reporting.export.run",
];

// User Type 3: view stock; receive, issue, transfer, count, validate returns; raise requests.
const TYPE_3: PermissionCode[] = [
  "catalog.item.view",
  "inventory.stock.view",
  "inventory.ledger.view",
  "audit.log.view",
  "alerts.alert.view",
  "receiving.grn.create",
  "receiving.grn.post",
  "issuance.issue.fulfil",
  "issuance.request.create",
  "transfers.transfer.create",
  "transfers.transfer.dispatch",
  "transfers.transfer.receive",
  "counts.session.count",
  "returns.return.receive",
  "returns.return.validate",
];

export const personas: Record<PersonaId, Me> = {
  type1: {
    principal: {
      id: "018f6f2a-1000-7000-8000-00000000a001",
      type: "user",
      display_name: "Arjun Mehta",
      email: "arjun.mehta@zongovita.in",
    },
    user_type_no: 1,
    is_super_admin: true,
    role_label: "Super Admin · Type 1",
    sites: SITES,
    home_site_id: null,
    permissions: grant(ALL, null),
    licence: LICENCE,
    unread_notifications: 3,
  },
  type2: {
    principal: {
      id: "018f6f2a-1000-7000-8000-00000000a002",
      type: "user",
      display_name: "Priya Sharma",
      email: "priya.sharma@zongovita.in",
    },
    user_type_no: 2,
    is_super_admin: false,
    role_label: "User Type 2",
    sites: SITES,
    home_site_id: BLR.id,
    permissions: grant(TYPE_2, null),
    licence: LICENCE,
    unread_notifications: 3,
  },
  type3: {
    principal: {
      id: "018f6f2a-1000-7000-8000-00000000a003",
      type: "user",
      display_name: "Suresh Patil",
      email: "suresh.patil@zongovita.in",
    },
    user_type_no: 3,
    is_super_admin: false,
    role_label: "User Type 3 · Store",
    sites: [BLR],
    home_site_id: BLR.id,
    permissions: grant(TYPE_3, [BLR.id]),
    licence: LICENCE,
    unread_notifications: 3,
  },
};

export function isPersonaId(value: unknown): value is PersonaId {
  return value === "type1" || value === "type2" || value === "type3";
}
