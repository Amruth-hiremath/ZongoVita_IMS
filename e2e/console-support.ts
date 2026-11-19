import { readFileSync } from "node:fs";
import { join } from "node:path";

import { AUTH_DIR, type CorePerson } from "./core-support";

/**
 * Helpers for the tests that run against the real Platform Service (project console-platform).
 * tools/e2e_backend.py creates the staff and writes their sign-in details to e2e/.auth.
 */
export type StaffRole = "system_admin" | "support_engineer";

export const STAFF_ROLES: StaffRole[] = ["system_admin", "support_engineer"];

export function staffStateOf(role: StaffRole): string {
  return join(AUTH_DIR, `staff-${role}.json`);
}

export function staff(): Record<StaffRole, CorePerson> {
  const file = JSON.parse(readFileSync(join(AUTH_DIR, "people.json"), "utf8")) as {
    staff: Record<StaffRole, CorePerson>;
  };
  return file.staff;
}

/** Headers of a change sent the way the console's own pages send it (LD-49). */
export function writeHeaders(baseURL: string): Record<string, string> {
  return { "x-ims-csrf": "1", origin: baseURL };
}
