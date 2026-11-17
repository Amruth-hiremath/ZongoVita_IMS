/**
 * FIXTURE: the privilege matrix as Core seeds it at provisioning (LLD 5.1): Super Admin and the
 * four user types with their default permissions. Temporary; see src/data/source.ts.
 */
import {
  ALL_PERMISSION_CODES,
  PERMISSIONS,
  RESERVED_TO_SUPER_ADMIN,
  USER_TYPE_1,
  USER_TYPE_2,
  USER_TYPE_3,
  USER_TYPE_4,
  type PermissionCode,
} from "@ims/api-client";

import type { MatrixRole, PrivilegeMatrix } from "@/data/privileges";

function seeded(n: 1 | 2 | 3 | 4, permissions: readonly PermissionCode[], assigned: number): MatrixRole {
  return {
    id: `018f6f2a-2000-7000-8000-00000000000${n}`,
    code: `user_type_${n}`,
    name: `User Type ${n}`,
    kind: "user_type",
    user_type_no: n,
    is_super_admin: false,
    editable: true,
    permissions: [...permissions],
    assigned_principals: assigned,
    version: 1,
  };
}

export const privilegeMatrix: Omit<PrivilegeMatrix, "source"> = {
  permissions: ALL_PERMISSION_CODES.map((code) => ({
    code,
    module: code.split(".")[0]!,
    site_scoped: PERMISSIONS[code].siteScoped,
    reserved_to_super_admin: RESERVED_TO_SUPER_ADMIN.includes(code),
  })),
  roles: [
    {
      id: "018f6f2a-2000-7000-8000-000000000000",
      code: "super_admin",
      name: "Super Admin",
      kind: "super_admin",
      user_type_no: null,
      is_super_admin: true,
      editable: false,
      permissions: [...ALL_PERMISSION_CODES],
      assigned_principals: 1,
      version: 1,
    },
    seeded(1, USER_TYPE_1, 1),
    seeded(2, USER_TYPE_2, 1),
    seeded(3, USER_TYPE_3, 4),
    seeded(4, USER_TYPE_4, 10),
  ],
};
