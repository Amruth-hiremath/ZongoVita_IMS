import "server-only";

import { privilegeMatrix } from "@/fixtures/privileges";

import { fromFixture } from "./source";

export interface MatrixRole {
  role_id: string;
  /** "Type 1". */
  name: string;
  /** Short description under the name ("super admin", "request · issue"). */
  summary: string;
}

export interface MatrixCapability {
  capability_id: string;
  label: string;
}

export interface PrivilegeMatrix {
  roles: MatrixRole[];
  capabilities: MatrixCapability[];
  /** Capability ids granted to each role, keyed by role_id. */
  grants: Record<string, string[]>;
  /** The seeded user-type defaults the "Reset" control restores, keyed by role_id. */
  seeded_defaults: Record<string, string[]>;
}

/** F36 Privilege Matrix. */
export function getPrivilegeMatrix(): Promise<PrivilegeMatrix> {
  return fromFixture(
    {
      endpoint: "GET /ui/v1/privilege-matrix",
      note:
        "The frame groups permissions into twelve capabilities; Core's catalogue is per permission code " +
        "(LLD section 7), so the response must either carry this grouping or the screen lists codes. " +
        "Seeded defaults per user type are needed for 'Reset to seeded defaults'.",
    },
    privilegeMatrix,
  );
}
