import { request, test as setup } from "@playwright/test";

import { people, signInThroughBff, storageStateOf, type CorePersona } from "./core-support";

/**
 * Signs each demo person in to the real IMS Core through the BFF and keeps their session
 * cookies for the tenant-core tests. The browser cannot do this itself yet: the authenticator
 * step has no approved screen (U-06).
 */
async function waitForApp(baseURL: string): Promise<void> {
  for (let i = 0; i < 120; i += 1) {
    const ready = await fetch(`${baseURL}/login`).then((r) => r.ok).catch(() => false);
    if (ready) return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${baseURL} did not start`);
}

for (const persona of ["type1", "type2", "type3", "type4"] as CorePersona[]) {
  setup(`sign in ${persona} through the BFF`, async ({ baseURL }) => {
    await waitForApp(baseURL!);
    const context = await request.newContext({
      baseURL,
      extraHTTPHeaders: { origin: baseURL!, "x-ims-csrf": "1" },
    });
    await signInThroughBff(context, people()[persona]);
    await context.storageState({ path: storageStateOf(persona) });
    await context.dispose();
  });
}
