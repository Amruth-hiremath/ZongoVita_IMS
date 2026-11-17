import { expect, type ConsoleMessage, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import type { Persona, Screen } from "./screens";

export const PERSONA_COOKIE = "ims_fixture_persona";

export async function signInAs(page: Page, persona: Persona, baseURL: string): Promise<void> {
  await page.context().addCookies([{ name: PERSONA_COOKIE, value: persona, url: baseURL }]);
}

/** Collects what must never appear while a screen renders: errors and CSP violations. */
export function watchConsole(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(String(error)));
  return problems;
}

/** The page itself must not scroll sideways; wide tables scroll inside their own container. */
export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page is wider than the viewport").toBeLessThanOrEqual(1);
}

/** With IMS_SCREENS_DIR set, save a screenshot named after the wireframe frame for review. */
export async function captureForReview(page: Page, screen: Screen): Promise<void> {
  const directory = process.env.IMS_SCREENS_DIR;
  if (!directory) return;
  mkdirSync(directory, { recursive: true });
  await page.screenshot({ path: join(directory, `${screen.frame}.png`), fullPage: false });
}

export function label(screen: Screen): string {
  return `${screen.frame} ${screen.route}${screen.persona ? ` as ${screen.persona}` : ""}`;
}
