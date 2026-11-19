import "server-only";

import type { StaffMe, StaffRole } from "@ims/api-client";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { staff as sampleStaff } from "@/fixtures/staff";

import { canOpen } from "./access";
import { sessionSource, type ConsoleSource } from "./config";
import { PlatformProblem, readPlatform } from "./platform";
import { CONSOLE_COOKIES } from "./tokens";

/**
 * The signed-in ZongoVita staff member for the current request.
 *
 * In `platform` mode this is GET /platform/v1/me with the access token the console's BFF keeps
 * in an HttpOnly cookie; the token exists only after the password and the authenticator code
 * (MFA is required for all staff, LLD 15). In `fixtures` mode it is the wireframes' sample
 * administrator. Nothing else in the app knows which.
 */
export interface StaffSession {
  name: string;
  /** As shown under the name in the top bar. */
  role_label: string;
  /** What the person may do (HLD section 3); the sample administrator acts as a system admin. */
  role: StaffRole;
  initials: string;
  unread_notifications: number;
  source: ConsoleSource;
}

const ROLE_LABELS: Record<StaffRole, string> = {
  system_admin: "ZongoVita System Admin",
  support_engineer: "ZongoVita Support Engineer",
};

export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? [words[0]![0], words[words.length - 1]![0]] : [words[0]?.[0], words[0]?.[1]];
  return letters.filter(Boolean).join("").toUpperCase();
}

async function platformSession(): Promise<StaffSession | null> {
  const token = (await cookies()).get(CONSOLE_COOKIES.access)?.value;
  if (!token) return null;
  try {
    const me = await readPlatform<StaffMe>("/me", token);
    return {
      name: me.display_name,
      role_label: ROLE_LABELS[me.role],
      role: me.role,
      initials: initialsOf(me.display_name),
      // The Platform Service has no notifications for staff (LLD 6.8).
      unread_notifications: 0,
      source: "platform",
    };
  } catch (error) {
    // Expired, revoked or deactivated: the visitor signs in again. Anything else is a fault.
    if (error instanceof PlatformProblem && error.status === 401) return null;
    throw error;
  }
}

/** One /me per request, however many components ask. */
export const getStaffSession = cache(async (): Promise<StaffSession | null> => {
  if (sessionSource() === "fixtures") {
    return {
      name: sampleStaff.name,
      role_label: sampleStaff.role,
      role: "system_admin",
      initials: sampleStaff.initials,
      unread_notifications: sampleStaff.unread_notifications,
      source: "fixtures",
    };
  }
  return platformSession();
});

/** Session for a page that needs one; sends the visitor to the sign-in page otherwise. */
export async function requireStaff(): Promise<StaffSession> {
  const session = await getStaffSession();
  if (session === null) redirect("/sign-in");
  return session;
}

/**
 * For a page, before it reads anything: whether the signed-in person may open it. The layout
 * shows the "not available" notice in its place; the page must not fetch what it may not read,
 * since the layout and the page render at the same time.
 */
export async function mayOpen(path: string): Promise<boolean> {
  const staff = await requireStaff();
  return canOpen(staff.role, path);
}
