import type { LicenceState } from "./licence";
import type { PermissionCode } from "./permissions";

/**
 * GET /ui/v1/me (LLD section 7: "returns effective permissions per site and the licence state";
 * section 15: licence banners and permission-aware UI). Mirrors Core's MeResponse
 * (services/core/ims_core/modules/access/schemas.py); replace with the OpenAPI-generated type
 * when Core publishes it.
 *
 * Until the organisation module (unit 4) exists, Core returns no sites and no home site; until
 * notifications exist (unit 10), unread_notifications is null.
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
  /** null until Core has notifications (unit 10). */
  unread_notifications: number | null;
}

export function hasPermission(me: Me, code: PermissionCode, siteId?: string): boolean {
  return me.permissions.some(
    (granted) =>
      granted.code === code && (granted.site_ids === null || siteId === undefined || granted.site_ids.includes(siteId)),
  );
}
