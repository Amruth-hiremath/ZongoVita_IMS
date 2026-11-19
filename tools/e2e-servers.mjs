// Serves one production build of a web app twice, for the browser tests:
//
//   node tools/e2e-servers.mjs tenant-web
//     :3200  IMS_SESSION_SOURCE=fixtures          the wireframe screens on sample data and personas
//     :3201  IMS_SESSION_SOURCE=core              signed in to IMS Core (tools/e2e_backend.py, :8180)
//
//   node tools/e2e-servers.mjs platform-console
//     :3300  IMS_CONSOLE_SESSION_SOURCE=fixtures  the wireframe screens on sample data
//     :3301  IMS_CONSOLE_SESSION_SOURCE=platform  signed in to the Platform Service (:8181)
//
// The session source is read at request time, so both servers share the build. Run after
// `npm run build -w @ims/<app>`; Playwright starts it (playwright.config.ts).
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
// Plain HTTP on localhost in the tests; production cookies are always Secure.
const insecure = { IMS_COOKIE_INSECURE: "1" };
const apps = {
  "tenant-web": [
    { port: 3200, env: { IMS_SESSION_SOURCE: "fixtures" } },
    {
      port: 3201,
      env: { IMS_SESSION_SOURCE: "core", IMS_CORE_URL: process.env.IMS_E2E_CORE_URL ?? "http://127.0.0.1:8180", ...insecure },
    },
  ],
  "platform-console": [
    { port: 3300, env: { IMS_CONSOLE_SESSION_SOURCE: "fixtures" } },
    {
      port: 3301,
      env: {
        IMS_CONSOLE_SESSION_SOURCE: "platform",
        IMS_PLATFORM_URL: process.env.IMS_E2E_PLATFORM_URL ?? "http://127.0.0.1:8181",
        ...insecure,
      },
    },
  ],
};

const name = process.argv[2];
const servers = apps[name];
if (!servers) throw new Error(`usage: node tools/e2e-servers.mjs ${Object.keys(apps).join("|")}`);
const app = join(root, "apps", name);
const next = createRequire(join(app, "package.json")).resolve("next/dist/bin/next");

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
