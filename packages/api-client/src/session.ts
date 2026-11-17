import type { LicenceState } from "./licence";
import type { PermissionCode } from "./permissions";

/**
 * Shape the web app expects from GET /ui/v1/me (LLD section 7: "returns effective permissions
 * per site and the licence state"; section 15: licence banners and permission-aware UI).
 *
 * PROVISIONAL: the endpoint arrives with the access module. Field names follow the API
 * conventions of LLD section 12 (snake_case, ISO 8601 UTC). Replace with the OpenAPI-generated
 * type when Core publishes it.
 */
export interface Me {
  principal: {
    id: string;
    type: "user" | "api_client" | "support";
    display_name: string;
    email: string | null;
  };
  /** Seeded user type 1 to 4 if the principal holds one; custom roles have none. */
  user_type_no: 1 | 2 | 3 | 4 | null;
  is_super_admin: boolean;
  /** Short role label shown under the name in the top bar. */
  role_label: string;
  sites: { id: string; code: string; name: string }[];
  home_site_id: string | null;
  /** Effective permissions; site_ids null means every site. */
  permissions: { code: PermissionCode; site_ids: string[] | null }[];
  licence: {
    state: LicenceState;
    /** End of the grace period, when state is grace. */
    grace_ends_at: string | null;
    gxp_mode: boolean;
    modules: string[];
  };
  unread_notifications: number;
}

export function hasPermission(me: Me, code: PermissionCode, siteId?: string): boolean {
  return me.permissions.some(
    (granted) =>
      granted.code === code && (granted.site_ids === null || siteId === undefined || granted.site_ids.includes(siteId)),
  );
}
