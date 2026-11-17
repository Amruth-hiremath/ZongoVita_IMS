"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { FIXTURE_PERSONA_COOKIE, fixturePersonaIds } from "./server";

/**
 * FIXTURE sign-in: remembers which wireframe persona to show. It checks no credential and
 * issues no token; it exists only so the screens can be viewed before Core has a login.
 * Replaced by POST /ui/v1/auth/login followed by /ui/v1/auth/mfa through the BFF (LLD 6.2).
 */
export async function signInAsFixturePersona(formData: FormData): Promise<void> {
  const persona = String(formData.get("persona") ?? "");
  if (!(fixturePersonaIds() as string[]).includes(persona)) redirect("/login");
  (await cookies()).set(FIXTURE_PERSONA_COOKIE, persona, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  });
  redirect("/dashboard");
}

export async function signOut(): Promise<void> {
  (await cookies()).delete(FIXTURE_PERSONA_COOKIE);
  redirect("/login");
}
