import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, type APIRequestContext } from "@playwright/test";

/**
 * Helpers for the tests that run against the real IMS Core (project tenant-core).
 * tools/e2e_backend.py creates the people and writes their sign-in details to e2e/.auth.
 */
export type CorePersona = "type1" | "type2" | "type3" | "type4";

export interface CorePerson {
  identifier: string;
  password: string;
  /** Base32 TOTP secret from the person's enrolment. */
  secret: string;
  /** The TOTP step used at enrolment: a step is accepted only once (LD-79). */
  last_step: number;
}

export const AUTH_DIR = join(__dirname, ".auth");

export function storageStateOf(persona: CorePersona): string {
  return join(AUTH_DIR, `${persona}.json`);
}

export function people(): Record<CorePersona, CorePerson> {
  const file = JSON.parse(readFileSync(join(AUTH_DIR, "people.json"), "utf8")) as {
    people: Record<CorePersona, CorePerson>;
  };
  return file.people;
}

function base32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    const value = alphabet.indexOf(char);
    if (value < 0) throw new Error("not base32");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((byte) => parseInt(byte, 2)));
}

export function currentStep(now = Date.now()): number {
  return Math.floor(now / 1000 / 30);
}

/** RFC 6238 with HMAC-SHA1, 30-second steps, six digits: what an authenticator app shows. */
export function totp(secret: string, step = currentStep()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

async function nextStep(after: number): Promise<void> {
  while (currentStep() <= after) await new Promise((resolve) => setTimeout(resolve, 500));
}

/**
 * Signs in through the BFF exactly as the browser will once the MFA screen is designed:
 * password, then the authenticator code. The session cookies end up in ``request``.
 */
export async function signInThroughBff(request: APIRequestContext, person: CorePerson): Promise<void> {
  let lastStep = person.last_step;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await nextStep(lastStep);
    const login = await request.post("/bff/auth/login", {
      data: { login_identifier: person.identifier, password: person.password },
    });
    expect(login.status(), await login.text()).toBe(200);
    expect((await login.json()).status).toBe("mfa_required");
    const step = currentStep();
    const mfa = await request.post("/bff/auth/mfa", { data: { code: totp(person.secret, step) } });
    if (mfa.status() === 200) return;
    // The step was already spent (another sign-in in the same 30 s): wait for the next one.
    lastStep = step;
  }
  throw new Error(`could not sign in ${person.identifier}`);
}
