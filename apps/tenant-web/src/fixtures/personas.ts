/**
 * FIXTURE: the three people the wireframes are drawn for, as GET /ui/v1/me would describe them.
 * Used only when IMS_SESSION_SOURCE=fixtures (src/session/config.ts); in `core` mode the
 * session is Core's /ui/v1/me.
 *
 * Their permissions are the LLD's seeded user types (LLD 5.1), the same defaults Core writes at
 * provisioning (packages/api-client/src/permissions.ts, checked against Core by a static test).
 * Where a wireframe gives a type more or less than that, the LLD decides (Docs/UI_Implementation.md
 * section 10).
 */
import { ALL_PERMISSION_CODES, PERMISSIONS, USER_TYPE_2, USER_TYPE_3, type Me, type PermissionCode } from "@ims/api-client";

export type PersonaId = "type1" | "type2" | "type3" | "type3_audit";

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

function grant(codes: readonly PermissionCode[], siteIds: string[] | null): Me["permissions"] {
  return codes.map((code) => ({ code, site_ids: PERMISSIONS[code].siteScoped ? siteIds : null }));
}

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
    permissions: grant(ALL_PERMISSION_CODES, null),
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
    permissions: grant(USER_TYPE_2, null),
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
    permissions: grant(USER_TYPE_3, [BLR.id]),
    licence: LICENCE,
    unread_notifications: 3,
  },
  // F50 draws an audit trail for the store, but the seeded User Type 3 has no audit.log.view
  // (LLD 5.1). This persona is the same person with a customer-made role that adds it, which is
  // how a customer would give a store that screen.
  type3_audit: {
    principal: {
      id: "018f6f2a-1000-7000-8000-00000000a003",
      type: "user",
      display_name: "Suresh Patil",
      email: "suresh.patil@zongovita.in",
    },
    user_type_no: 3,
    is_super_admin: false,
    role_label: "Type 3 · Store audit",
    sites: [BLR],
    home_site_id: BLR.id,
    permissions: grant([...USER_TYPE_3, "audit.log.view"], [BLR.id]),
    licence: LICENCE,
    unread_notifications: 3,
  },
};

export function isPersonaId(value: unknown): value is PersonaId {
  return value === "type1" || value === "type2" || value === "type3" || value === "type3_audit";
}
