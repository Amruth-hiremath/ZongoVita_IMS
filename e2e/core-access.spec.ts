import { expect, test, type Browser, type Page } from "@playwright/test";

import { people, storageStateOf, type CorePersona } from "./core-support";

/**
 * The Tenant Web App signed in to the real IMS Core (LLD 6.2, 7, 15; LD-49). The session, the
 * menu, the screen guard, F22 and F36 are live; Core enforces every permission again on its side.
 *
 * Serial: the last test changes a role in Core and checks that the change reaches another
 * person's menu at once.
 */
test.describe.configure({ mode: "serial" });

async function as(browser: Browser, persona: CorePersona): Promise<Page> {
  const context = await browser.newContext({ storageState: storageStateOf(persona) });
  return context.newPage();
}

const menus: Record<"type1" | "type2" | "type3", string[]> = {
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
  // LLD 5.1: User Type 3 has no audit.log.view, so the frame's "Audit Trail" entry is not shown.
  type3: ["Dashboard", "Fulfilment Queue", "Scan & Issue", "Receive", "Quarantine", "Returns", "Counts", "Transfers"],
};

const who = {
  type1: { name: "Arjun Mehta", role: "Super Admin · Type 1", footer: "Type 1 · Arjun Mehta" },
  type2: { name: "Priya Sharma", role: "User Type 2", footer: "Type 2 · Priya Sharma" },
  type3: { name: "Suresh Patil", role: "User Type 3", footer: "Type 3 · Suresh Patil" },
} as const;

test("F03 checks the password with Core and states that the MFA screen is not designed", async ({ page }) => {
  const meera = people().type4;
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Sign in as Type/ })).toHaveCount(0);

  await page.getByLabel("Work email").fill(meera.identifier);
  await page.getByLabel("Password").fill("not the password at all");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("Sign-in failed. Check your work email and password.");

  await page.getByLabel("Password").fill(meera.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const status = page.getByRole("status");
  await expect(status).toContainText("Password accepted");
  await expect(status).toContainText("no approved design yet");
  await expect(page).toHaveURL(/\/login$/);
});

test("signed-out visitors are sent to the sign-in screen", async ({ page }) => {
  for (const route of ["/dashboard", "/users", "/privileges"]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login$/);
  }
});

for (const persona of ["type1", "type2", "type3"] as const) {
  test(`${persona}: the shell comes from /ui/v1/me and the menu from effective permissions`, async ({ browser }) => {
    const page = await as(browser, persona);
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link")).toHaveText(menus[persona]);
    const banner = page.getByRole("banner");
    await expect(banner.getByText(who[persona].name)).toBeVisible();
    await expect(banner.getByText(who[persona].role, { exact: true })).toBeVisible();
    await expect(page.getByText(who[persona].footer)).toBeVisible();
    // Core has no notifications yet (unit 10): no invented count.
    await expect(banner.getByRole("button", { name: "Notifications", exact: true })).toBeVisible();
    await expect(page.getByText("Signed in to IMS Core")).toBeVisible();
    await page.context().close();
  });
}

test("a screen outside the person's permissions is refused, and Core refuses its endpoint", async ({ browser }) => {
  const page = await as(browser, "type3");
  for (const route of ["/users", "/privileges", "/audit"]) {
    await page.goto(route);
    await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("You do not have permission to open this screen");
  }
  const answer = await page.request.get("/bff/users");
  expect(answer.status()).toBe(403);
  expect((await answer.json()).code).toBe("PERMISSION_DENIED");
  await page.context().close();
});

test("F22 lists the customer's real users", async ({ browser }) => {
  const page = await as(browser, "type1");
  await page.goto("/users");
  await expect(page.getByRole("heading", { name: "Users & User Types" })).toBeVisible();
  const table = page.getByRole("table").first();
  for (const name of ["Arjun Mehta", "Priya Sharma", "Suresh Patil", "Meera Joshi"]) {
    await expect(table.getByRole("row", { name: new RegExp(name) })).toBeVisible();
  }
  await expect(table.getByRole("row", { name: /Suresh Patil/ })).toContainText("1 site");
  await expect(table.getByRole("row", { name: /Priya Sharma/ })).toContainText("All locations");
  await expect(table.getByRole("row", { name: /Arjun Mehta/ })).toContainText("today");
  // The capability summary is read from the live matrix.
  await expect(page.getByRole("row", { name: /Manage users & privileges/ })).toContainText("Yes");
  await page.getByRole("button", { name: "+ Add user" }).click();
  await expect(page.getByText("has no approved design yet")).toBeVisible();
  await page.context().close();
});

test("the BFF refuses writes without the CSRF header or from another origin", async ({ browser }) => {
  const page = await as(browser, "type1");
  const roles = (await (await page.request.get("/bff/roles")).json()) as { id: string; code: string; version: number }[];
  const type4 = roles.find((role) => role.code === "user_type_4")!;
  const url = `/bff/roles/${type4.id}/permissions`;
  const body = { permissions: ["issuance.request.create", "returns.return.create"] };
  const noHeader = await page.request.put(url, { data: body, headers: { "if-match": `"${type4.version}"` } });
  expect(noHeader.status()).toBe(403);
  const foreign = await page.request.put(url, {
    data: body,
    headers: { "if-match": `"${type4.version}"`, "x-ims-csrf": "1", origin: "https://evil.example" },
  });
  expect(foreign.status()).toBe(403);
  // Credential routes are never forwarded by the catch-all: they would hand tokens to the page.
  const credential = await page.request.post("/bff/auth/refresh", { headers: { "x-ims-csrf": "1" } });
  expect(credential.status()).toBe(404);
  await page.context().close();
});

test("an expired access token is renewed with the refresh token before the page renders", async ({ browser }) => {
  const page = await as(browser, "type2");
  const context = page.context();
  const before = (await context.cookies()).find((cookie) => cookie.name === "ims_at")!;
  await context.clearCookies({ name: "ims_at" });
  await page.goto("/dashboard");
  await expect(page.getByRole("banner").getByText("Priya Sharma")).toBeVisible();
  const after = (await context.cookies()).find((cookie) => cookie.name === "ims_at");
  expect(after?.value).toBeTruthy();
  expect(after?.value).not.toBe(before.value);
  expect(after?.httpOnly).toBe(true);
  await context.close();
});

test("F36 saves a role's permissions in Core and the change reaches the holder's menu at once", async ({ browser }) => {
  const admin = await as(browser, "type1");
  await admin.goto("/privileges");
  const superAdminCell = admin.getByRole("checkbox", { name: "catalog.item.view — Super Admin" });
  await expect(superAdminCell).toBeChecked();
  await expect(superAdminCell).toBeDisabled();
  await expect(admin.getByRole("checkbox", { name: "access.support.grant — User Type 1" })).toBeDisabled();

  const store = await as(browser, "type3");
  await store.goto("/dashboard");
  await expect(store.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Audit Trail" })).toHaveCount(0);

  const audit = admin.getByRole("checkbox", { name: "audit.log.view — User Type 3" });
  await expect(audit).not.toBeChecked();
  await audit.check();
  await admin.getByRole("button", { name: "Save type configuration" }).click();
  const saved = admin.getByRole("status");
  await expect(saved).toContainText("User Type 3");
  await expect(saved).toContainText("Added: audit.log.view");
  await expect(saved).toContainText("Suresh Patil");

  // Same session, no sign-in: Core's access version moved, so /me already has the permission.
  await store.reload();
  await expect(store.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Audit Trail" })).toBeVisible();

  // Put the seeded default back.
  await admin.getByRole("checkbox", { name: "audit.log.view — User Type 3" }).uncheck();
  await admin.getByRole("button", { name: "Save type configuration" }).click();
  await expect(admin.getByRole("status")).toContainText("Removed: audit.log.view");
  await store.reload();
  await expect(store.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Audit Trail" })).toHaveCount(0);

  await admin.context().close();
  await store.context().close();
});
