import { expect, test } from "@playwright/test";

import { PERSONA_COOKIE, signInAs } from "./support";

const menus = {
  type1: [
    "Dashboard",
    "Items & Catalog",
    "Categories",
    "Vendors & Purchases",
    "Quality Register",
    "Locations",
    "Users & Types",
    "Privileges",
    "Approvals",
    "Audit Trail",
    "Settings",
  ],
  type2: [
    "Dashboard",
    "Items",
    "Receive",
    "Issuance",
    "Approvals",
    "Returns",
    "Transfers",
    "Stock Counts",
    "Alerts & Reorder",
    "Reports",
    "Audit Trail",
  ],
  type3: [
    "Dashboard",
    "Fulfilment Queue",
    "Scan & Issue",
    "Receive",
    "Quarantine",
    "Returns",
    "Counts",
    "Transfers",
    // The frame also draws "Audit Trail"; the seeded User Type 3 has no audit.log.view (LLD 5.1).
  ],
} as const;

const people = {
  type1: { name: "Arjun Mehta", role: "Super Admin · Type 1", footer: "Type 1 · Arjun Mehta" },
  type2: { name: "Priya Sharma", role: "User Type 2", footer: "Type 2 · Priya Sharma" },
  type3: { name: "Suresh Patil", role: "User Type 3 · Store", footer: "Type 3 · Suresh Patil" },
} as const;

test("signed-out visitors are sent to the sign-in screen", async ({ page }) => {
  for (const route of ["/", "/dashboard", "/items", "/audit"]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login$/);
  }
});

for (const persona of ["type1", "type2", "type3"] as const) {
  test(`${persona}: menu, identity and current entry match the wireframes`, async ({ page, baseURL }) => {
    await signInAs(page, persona, baseURL!);
    await page.goto("/dashboard");

    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link")).toHaveText([...menus[persona]]);
    await expect(nav.getByRole("link", { name: "Dashboard", exact: true })).toHaveAttribute("aria-current", "page");

    const banner = page.getByRole("banner");
    await expect(banner.getByText(people[persona].name)).toBeVisible();
    await expect(banner.getByText(people[persona].role)).toBeVisible();
    await expect(page.getByText(people[persona].footer)).toBeVisible();
    await expect(banner.getByRole("button", { name: /Notifications: 3 unread/ })).toBeVisible();
  });

  test(`${persona}: every menu entry opens a screen`, async ({ page, baseURL }) => {
    await signInAs(page, persona, baseURL!);
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const entry of menus[persona]) {
      await nav.getByRole("link", { name: entry, exact: true }).click();
      await expect(nav.getByRole("link", { name: entry, exact: true })).toHaveAttribute("aria-current", "page");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
  });
}

test("a screen outside the persona's permissions is not rendered (LLD 15)", async ({ page, baseURL }) => {
  await signInAs(page, "type3", baseURL!);
  for (const route of ["/audit", "/users", "/privileges", "/vendors"]) {
    await page.goto(route);
    await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("You do not have permission to open this screen");
  }
});

test("the sign-in card offers the sample personas and explains what is not available", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Continue with Company SSO" })).toBeVisible();
  await expect(page.getByLabel("Work email")).toHaveAttribute("placeholder", "name@zongovita.in");
  await expect(page.getByText("Need an account? Ask your Type 1 admin (F22).")).toBeVisible();

  await page.getByRole("button", { name: "Continue with Company SSO" }).click();
  await expect(page.getByText("Company SSO is not available yet")).toBeVisible();

  await page.getByRole("button", { name: "Sign in as Type 3" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Namaste, Suresh");
  const cookies = await page.context().cookies();
  const session = cookies.find((cookie) => cookie.name === PERSONA_COOKIE);
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Lax");
});

test("actions that need the backend say so instead of pretending", async ({ page, baseURL }) => {
  await signInAs(page, "type2", baseURL!);
  await page.goto("/items");
  await page.getByRole("button", { name: "Export" }).click();
  await expect(page.getByText("Not connected yet")).toBeVisible();
  await expect(page.getByText(/POST \/ui\/v1\/exports/)).toBeVisible();
});

test("the items list filters narrow the rows on the page", async ({ page, baseURL }) => {
  await signInAs(page, "type2", baseURL!);
  await page.goto("/items");
  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(10);
  await page.getByRole("button", { name: "Below min" }).click();
  await expect(rows).toHaveCount(2);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.getByLabel("Search items").fill("bearing");
  await expect(rows).toHaveCount(2);
  await page.getByLabel("Search items").fill("no such thing");
  await expect(page.getByText("No items match these filters.")).toBeVisible();
});

test("security headers: strict CSP with a nonce, no framing, HSTS (LD-49)", async ({ request }) => {
  const response = await request.get("/login");
  const headers = response.headers();
  const csp = headers["content-security-policy"] ?? "";
  expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(csp).toMatch(/style-src 'self' 'nonce-[A-Za-z0-9+/=]+'/);
  expect(csp).not.toContain("unsafe-inline");
  expect(csp).not.toContain("unsafe-eval");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("form-action 'self'");
  expect(headers["strict-transport-security"]).toContain("max-age=");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-powered-by"]).toBeUndefined();

  const second = await request.get("/login");
  expect(second.headers()["content-security-policy"]).not.toBe(csp);
});
