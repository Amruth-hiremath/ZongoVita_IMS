import { expect, request, test, type Browser, type Page } from "@playwright/test";

import { staffStateOf, writeHeaders, type StaffRole } from "./console-support";
import { watchConsole } from "./support";

/**
 * The Platform Console signed in to the real Platform Service (LLD 6.6, 6.8, 15; AD-04, AD-28).
 * Overview and Licenses read the registry; a customer is onboarded through the console's BFF and
 * the real provisioning run (database pipeline, IMS Core, handover); the BFF's CSRF and Origin
 * checks and the staff roles are enforced end to end.
 *
 * Serial: the onboarding test adds a customer that later tests look for.
 */
test.describe.configure({ mode: "serial" });

async function as(browser: Browser, role: StaffRole): Promise<Page> {
  const context = await browser.newContext({ storageState: staffStateOf(role) });
  return context.newPage();
}

const MODULES = "Core · Integration · Replenishment · Supplier register";
// A fresh code per run, so the test also passes against a backend that is reused (IMS_E2E_REUSE).
const ONBOARDED = { code: `sunrise_${Date.now().toString(36)}`, name: "Sunrise Auto Components" };

test("the system admin sees the live registry on F51", async ({ browser }) => {
  const page = await as(browser, "system_admin");
  const problems = watchConsole(page);
  await page.goto("/overview");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Platform Overview");
  await expect(page.getByText(/^Signed in to the Platform Service/)).toBeVisible();
  await expect(page.getByRole("banner").getByText("Kiran Desai")).toBeVisible();
  await expect(page.getByRole("banner").getByText("ZongoVita System Admin")).toBeVisible();
  await expect(page.getByText("Platform · Kiran Desai")).toBeVisible();

  const demo = page.getByRole("row", { name: /Demo Manufacturing Pvt Ltd/ });
  await expect(demo).toContainText("demo");
  await expect(demo).toContainText("ims_c_demo");
  await expect(demo).toContainText("— / 200");

  // Platform activity is the platform audit: the onboarding of "demo" ended with the handover.
  await expect(page.getByText("Activation code handed over · demo Demo Manufacturing Pvt Ltd")).toBeVisible();
  await expect(page.getByText(/^Kiran Desai · \d{2} \w{3} \d{2}:\d{2}$/).first()).toBeVisible();
  // Figures no /platform/v1 resource provides are shown as not reported, not invented.
  await expect(page.getByText("usage not reported")).toBeVisible();

  // The enterprise selector lists the registry's customers.
  await expect(page.getByRole("combobox", { name: "Enterprise" })).toContainText("demo · Demo Manufacturing Pvt Ltd");
  expect(problems).toEqual([]);
  await page.context().close();
});

test("F52 shows each customer's licence, database and derived state", async ({ browser }) => {
  const page = await as(browser, "system_admin");
  await page.goto("/licenses");
  const demo = page.getByRole("row", { name: /Demo Manufacturing Pvt Ltd/ });
  await expect(demo).toContainText("— / 5");
  await expect(demo).toContainText("— / 200");
  await expect(demo).toContainText(MODULES);
  await expect(demo).toContainText("ims_c_demo");
  await expect(demo).toContainText("Active");
  await expect(page.getByText("Licence expiry — demo")).toBeVisible();
  await expect(page.getByText(/^Active · ends in 36[45] d$/)).toBeVisible();
  await page.context().close();
});

test("a customer is onboarded through the console BFF and the real provisioning run", async ({ browser, baseURL }) => {
  test.setTimeout(180_000);
  const page = await as(browser, "system_admin");
  const api = page.request;
  const now = Date.now();
  const body = {
    customer: { code: ONBOARDED.code, legal_name: ONBOARDED.name },
    licence: {
      licence_no: `LIC-${ONBOARDED.code}`,
      valid_from: new Date(now - 86_400_000).toISOString(),
      valid_until: new Date(now + 180 * 86_400_000).toISOString(),
      grace_days: 14,
      max_sites: 3,
      max_users: 10,
      modules: ["ims.core", "ims.integration"],
    },
    super_admin: { login_identifier: `admin@${ONBOARDED.code.replaceAll("_", "-")}.test`, display_name: "Neha Rao" },
  };

  // The BFF refuses a change without its CSRF header or from another origin, before forwarding.
  const noCsrf = await api.post("/bff/provisioning-runs", { headers: { origin: baseURL! }, data: body });
  expect(noCsrf.status()).toBe(403);
  const crossSite = await api.post("/bff/provisioning-runs", {
    headers: { "x-ims-csrf": "1", origin: "https://elsewhere.example" },
    data: body,
  });
  expect(crossSite.status()).toBe(403);

  const started = await api.post("/bff/provisioning-runs", { headers: writeHeaders(baseURL!), data: body });
  expect(started.status(), await started.text()).toBe(202);
  const run = (await started.json()) as { id: string; current_step: string; status: string };
  expect(run.status).toBe("running");

  await expect
    .poll(async () => ((await (await api.get(`/bff/provisioning-runs/${run.id}`)).json()) as { status: string }).status, {
      timeout: 150_000,
      intervals: [1_000],
    })
    .toBe("completed");

  // The super admin's activation code is shown once, never cached (#21).
  const handover = await api.post(`/bff/provisioning-runs/${run.id}/handover`, { headers: writeHeaders(baseURL!) });
  expect(handover.status(), await handover.text()).toBe(200);
  expect(handover.headers()["cache-control"]).toContain("no-store");
  expect(((await handover.json()) as { activation_code: string }).activation_code).toMatch(/\S{8,}/);
  const again = await api.post(`/bff/provisioning-runs/${run.id}/handover`, { headers: writeHeaders(baseURL!) });
  expect(again.status()).toBe(409);

  await page.goto("/licenses");
  const row = page.getByRole("row", { name: new RegExp(ONBOARDED.name) });
  await expect(row).toContainText(`ims_c_${ONBOARDED.code}`);
  await expect(row).toContainText("Core · Integration");
  await expect(row).toContainText("Active");
  await page.goto("/overview");
  await expect(page.getByRole("row", { name: new RegExp(ONBOARDED.name) })).toContainText("— / 10");
  await page.context().close();
});

test("tokens stay in HttpOnly cookies and the catch-all never forwards sign-in routes", async ({ browser, baseURL }) => {
  const page = await as(browser, "system_admin");
  await page.goto("/overview");
  expect(await page.evaluate(() => document.cookie)).not.toContain("ims_pc_");
  const refresh = await page.request.post("/bff/auth/refresh", { headers: writeHeaders(baseURL!), data: {} });
  expect(refresh.status()).toBe(404);
  await page.context().close();

  const anonymous = await request.newContext({ baseURL });
  expect((await anonymous.get("/bff/customers")).status()).toBe(401);
  await anonymous.dispose();
});

test("a support engineer has no administration screens", async ({ browser }) => {
  const page = await as(browser, "support_engineer");
  await page.goto("/overview");
  await expect(page.getByRole("banner").getByText("Rohan Kulkarni")).toBeVisible();
  await expect(page.getByRole("banner").getByText("ZongoVita Support Engineer")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Not available");
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link")).toHaveCount(0);
  for (const route of ["/licenses", "/config", "/enterprises", "/audit"]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1 }), route).toHaveText("Not available");
  }
  // The Platform Service refuses the data in any case.
  expect((await page.request.get("/bff/customers")).status()).toBe(403);
  await page.context().close();
});

test("without a session every screen leads to the sign-in notice", async ({ page }) => {
  await page.goto("/overview");
  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("IMS Platform Console");
  await expect(page.getByText("No wireframe for the sign-in screen")).toBeVisible();
});
