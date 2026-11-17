import { expect, test } from "@playwright/test";

import { platformScreens } from "./screens";
import { captureForReview, expectNoHorizontalOverflow, label, watchConsole } from "./support";

const menu = ["Overview", "Enterprises", "Licenses", "Platform Config", "Audit Trail"];

test.describe("every Platform Console wireframe screen renders", () => {
  for (const screen of platformScreens) {
    test(label(screen), async ({ page }) => {
      const problems = watchConsole(page);
      const response = await page.goto(screen.route);
      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(screen.title);
      await expectNoHorizontalOverflow(page);
      await captureForReview(page, screen);
      expect(problems, "console errors or Content Security Policy violations").toEqual([]);
    });
  }
});

test("menu and identity match the wireframes; every entry opens a screen", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/overview$/);
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link")).toHaveText(menu);
  await expect(page.getByRole("banner").getByText("Kiran Desai")).toBeVisible();
  await expect(page.getByRole("banner").getByText("ZongoVita Super Admin")).toBeVisible();
  await expect(page.getByText("Platform · Kiran Desai")).toBeVisible();
  for (const entry of menu) {
    await nav.getByRole("link", { name: entry, exact: true }).click();
    await expect(nav.getByRole("link", { name: entry, exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});

test("the console has no route into customer screens", async ({ request }) => {
  for (const route of ["/items", "/dashboard", "/login", "/vendors"]) {
    expect((await request.get(route)).status(), route).toBe(404);
  }
});

test("security headers: strict CSP with a nonce, no framing", async ({ request }) => {
  const csp = (await request.get("/overview")).headers()["content-security-policy"] ?? "";
  expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(csp).not.toContain("unsafe-inline");
  expect(csp).toContain("frame-ancestors 'none'");
});
