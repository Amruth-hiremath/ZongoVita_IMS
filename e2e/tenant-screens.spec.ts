import { expect, test } from "@playwright/test";

import { tenantDeepLinks, tenantScreens, tenantUnknownRecords } from "./screens";
import { captureForReview, expectNoHorizontalOverflow, label, signInAs, watchConsole } from "./support";

test.describe("every wireframe screen renders", () => {
  for (const screen of tenantScreens) {
    test(label(screen), async ({ page, baseURL }) => {
      const problems = watchConsole(page);
      if (screen.persona) await signInAs(page, screen.persona, baseURL!);

      const response = await page.goto(screen.route);
      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(screen.title);
      if (screen.persona) {
        // The signed-in frame: menu, and the marker that the data is sample data.
        await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
        await expect(page.getByText("Sample data from the wireframes")).toBeVisible();
      }
      await expectNoHorizontalOverflow(page);
      await captureForReview(page, screen);
      expect(problems, "console errors or Content Security Policy violations").toEqual([]);
    });
  }
});

test.describe("deep links show the same screens", () => {
  for (const screen of tenantDeepLinks) {
    test(label(screen), async ({ page, baseURL }) => {
      await signInAs(page, screen.persona!, baseURL!);
      const response = await page.goto(screen.route);
      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(screen.title);
    });
  }
});

test.describe("screens stay usable on a phone (390 px, LLD section 15)", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  for (const screen of tenantScreens) {
    test(label(screen), async ({ page, baseURL }) => {
      if (screen.persona) await signInAs(page, screen.persona, baseURL!);
      await page.goto(screen.route);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(screen.title);
      await expectNoHorizontalOverflow(page);
    });
  }
});

test("a detail route knows only the record drawn in the wireframe", async ({ page, baseURL }) => {
  for (const unknown of tenantUnknownRecords) {
    await signInAs(page, unknown.persona, baseURL!);
    const response = await page.goto(unknown.route);
    expect(response?.status(), unknown.route).toBe(404);
  }
});
