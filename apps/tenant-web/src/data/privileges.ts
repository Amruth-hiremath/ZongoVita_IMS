import "server-only";

import type { PermissionCode } from "@ims/api-client";

import { privilegeMatrix } from "@/fixtures/privileges";
import { sessionSource } from "@/session/config";

import { fromCore } from "./source";

/** One row of the matrix: a permission of the LLD section 7 catalogue. */
export interface MatrixPermission {
  code: PermissionCode;
  module: string;
  site_scoped: boolean;
  reserved_to_super_admin: boolean;
}

/** One column: a role, as GET /ui/v1/privilege-matrix returns it. */
export interface MatrixRole {
  id: string;
  code: string;
  name: string;
  kind: "user_type" | "super_admin" | "custom";
  user_type_no: number | null;
  is_super_admin: boolean;
  editable: boolean;
  permissions: PermissionCode[];
  assigned_principals: number;
  version: number;
}

export interface PrivilegeMatrix {
  permissions: MatrixPermission[];
  roles: MatrixRole[];
  /** Live from Core, or the sample matrix (seeded defaults) in `fixtures` mode. */
  source: "core" | "fixtures";
}

/** F36 Privilege Matrix: permissions x roles (LLD 7). */
export function getPrivilegeMatrix(): Promise<PrivilegeMatrix> {
  return fromCore<Omit<PrivilegeMatrix, "source">, PrivilegeMatrix>(
    {
      endpoint: "GET /ui/v1/privilege-matrix",
      note: "Rows are the permission catalogue grouped by the LLD's module groups; F36's twelve capability rows are not in the LLD.",
    },
    "/privilege-matrix",
    (matrix) => ({ ...matrix, source: "core" }),
    () => ({ ...privilegeMatrix, source: sessionSource() }),
  );
}
