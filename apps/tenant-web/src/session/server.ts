import "server-only";

import type { Me } from "@ims/api-client";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { isPersonaId, personas, type PersonaId } from "@/fixtures/personas";

import { resolveWorkspace, type Workspace } from "./workspace";

/**
 * The signed-in principal for the current request.
 *
 * INTEGRATION SEAM. Today the session is a fixture persona named by a cookie, because Core has
 * no login or /ui/v1/me yet. When identity (unit 2) and access control (unit 3) exist, only
 * this module changes: getSession() reads /ui/v1/me through the BFF, which holds the access and
 * refresh tokens in HttpOnly cookies (LD-49). Nothing else in the app knows where the session
 * comes from.
 */
export interface Session {
  me: Me;
  workspace: Workspace;
  /** Where this session came from. "fixture" disappears with the integration above. */
  source: "fixture";
}

export const FIXTURE_PERSONA_COOKIE = "ims_fixture_persona";

export async function getSession(): Promise<Session | null> {
  const persona = (await cookies()).get(FIXTURE_PERSONA_COOKIE)?.value;
  if (!isPersonaId(persona)) return null;
  const me = personas[persona];
  return { me, workspace: resolveWorkspace(me), source: "fixture" };
}

/** Session for a page that needs one; sends the visitor to the sign-in screen otherwise. */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (session === null) redirect("/login");
  return session;
}

export function fixturePersonaIds(): PersonaId[] {
  return Object.keys(personas) as PersonaId[];
}
