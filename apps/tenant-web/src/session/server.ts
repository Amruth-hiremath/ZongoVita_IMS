import "server-only";

import type { Me } from "@ims/api-client";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { isPersonaId, personas, type PersonaId } from "@/fixtures/personas";

import { sessionSource, type SessionSource } from "./config";
import { CoreProblem, readCore } from "./core";
import { ACCESS_COOKIE } from "./tokens";
import { resolveWorkspace, type Workspace } from "./workspace";

/**
 * The signed-in principal for the current request.
 *
 * In `core` mode this is GET /ui/v1/me with the access token the BFF keeps in an HttpOnly cookie
 * (LLD 7, 15; LD-49): effective permissions per site and the licence state, straight from Core.
 * In `fixtures` mode it is a wireframe persona (src/session/config.ts). Nothing else in the app
 * knows which.
 */
export interface Session {
  me: Me;
  workspace: Workspace;
  source: SessionSource;
}

export const FIXTURE_PERSONA_COOKIE = "ims_fixture_persona";

async function coreSession(): Promise<Session | null> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return null;
  try {
    const me = await readCore<Me>("/me", token);
    return { me, workspace: resolveWorkspace(me), source: "core" };
  } catch (error) {
    // Expired, revoked or inactive: the visitor signs in again. Anything else is a fault.
    if (error instanceof CoreProblem && error.status === 401) return null;
    throw error;
  }
}

async function fixtureSession(): Promise<Session | null> {
  const persona = (await cookies()).get(FIXTURE_PERSONA_COOKIE)?.value;
  if (!isPersonaId(persona)) return null;
  const me = personas[persona];
  return { me, workspace: resolveWorkspace(me), source: "fixtures" };
}

/** One /me per request, however many components ask. */
export const getSession = cache(async (): Promise<Session | null> => {
  return sessionSource() === "core" ? coreSession() : fixtureSession();
});

/** Session for a page that needs one; sends the visitor to the sign-in screen otherwise. */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (session === null) redirect("/login");
  return session;
}

export function fixturePersonaIds(): PersonaId[] {
  return Object.keys(personas) as PersonaId[];
}
