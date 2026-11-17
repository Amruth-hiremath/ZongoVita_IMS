// Serves one production build of the Tenant Web App twice, for the browser tests:
//
//   :3200  IMS_SESSION_SOURCE=fixtures  the wireframe screens on sample data and sample personas
//   :3201  IMS_SESSION_SOURCE=core      signed in to IMS Core (tools/e2e_backend.py on :8180)
//
// The session source is read at request time, so both servers share the build. Run after
// `npm run build -w @ims/tenant-web`; Playwright starts it (playwright.config.ts).
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const app = join(root, "apps", "tenant-web");
const next = createRequire(join(app, "package.json")).resolve("next/dist/bin/next");

const servers = [
  { port: 3200, env: { IMS_SESSION_SOURCE: "fixtures" } },
  {
    port: 3201,
    env: {
      IMS_SESSION_SOURCE: "core",
      IMS_CORE_URL: process.env.IMS_E2E_CORE_URL ?? "http://127.0.0.1:8180",
      // Plain HTTP on localhost in the tests; production cookies are always Secure.
      IMS_COOKIE_INSECURE: "1",
    },
  },
];

const children = servers.map(({ port, env }) =>
  spawn(process.execPath, [next, "start", "--port", String(port)], {
    cwd: app,
    env: { ...process.env, ...env },
    stdio: "inherit",
  }),
);

const stop = () => {
  for (const child of children) child.kill();
  process.exit(0);
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
for (const child of children) {
  child.on("exit", (code) => {
    if (code !== 0 && code !== null) {
      console.error(`next start exited with ${code}`);
      stop();
    }
  });
}
