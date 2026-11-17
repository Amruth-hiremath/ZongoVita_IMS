import "server-only";

import { staff } from "@/fixtures/staff";

import { fromFixture } from "./source";

export interface StaffSession {
  name: string;
  role: string;
  initials: string;
  unread_notifications: number;
  enterprises: { code: string; name: string }[];
}

/** The signed-in platform administrator. */
export function getStaffSession(): Promise<StaffSession> {
  return fromFixture(
    { endpoint: "Platform Console sign-in (Platform Service, MFA mandatory)", note: "No staff login or session endpoint exists yet." },
    staff,
  );
}
