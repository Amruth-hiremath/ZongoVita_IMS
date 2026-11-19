import { request, test as setup } from "@playwright/test";

import { signInThroughBff } from "./core-support";
import { staff, staffStateOf, STAFF_ROLES } from "./console-support";

/**
 * Signs each staff member in to the real Platform Service through the console's BFF (password,
 * then authenticator code) and keeps their session cookies for the console-platform tests. The
 * browser cannot do this itself: the console has no sign-in wireframe (U-06).
 */
async function waitFor(url: string): Promise<void> {
  for (let i = 0; i < 120; i += 1) {
    if (await fetch(url).then((r) => r.ok).catch(() => false)) return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${url} did not start`);
}

for (const role of STAFF_ROLES) {
  setup(`sign in the ${role} through the console BFF`, async ({ baseURL }) => {
    await waitFor(`${baseURL}/sign-in`);
    await waitFor(process.env.IMS_E2E_PLATFORM_URL ? `${process.env.IMS_E2E_PLATFORM_URL}/healthz` : "http://127.0.0.1:8181/healthz");
    const context = await request.newContext({
      baseURL,
      extraHTTPHeaders: { origin: baseURL!, "x-ims-csrf": "1" },
    });
    await signInThroughBff(context, staff()[role]);
    await context.storageState({ path: staffStateOf(role) });
    await context.dispose();
  });
}
