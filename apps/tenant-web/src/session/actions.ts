"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { sessionSource } from "./config";
import { FIXTURE_PERSONA_COOKIE, fixturePersonaIds } from "./server";

/**
 * FIXTURE sign-in, available only when IMS_SESSION_SOURCE=fixtures: remembers which wireframe
 * persona to show. It checks no credential and issues no token. In `core` mode sign-in goes
 * through the BFF (/bff/auth/login, then the MFA step, LLD 6.2) and this action refuses.
 */
export async function signInAsFixturePersona(formData: FormData): Promise<void> {
  if (sessionSource() !== "fixtures") redirect("/login");
  const persona = String(formData.get("persona") ?? "");
  if (!(fixturePersonaIds() as string[]).includes(persona)) redirect("/login");
  (await cookies()).set(FIXTURE_PERSONA_COOKIE, persona, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" && process.env.IMS_COOKIE_INSECURE !== "1",
    path: "/",
  });
  redirect("/dashboard");
}
