import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  globalIgnores(["node_modules/**"]),
  {
    settings: { next: { rootDir: "../../apps/tenant-web" } },
    rules: {
      // Both apps run under a strict Content Security Policy: no inline styles (LD-49).
      "react/forbid-dom-props": ["error", { forbid: ["style"] }],
      "react/forbid-component-props": ["error", { forbid: ["style"] }],
      "@next/next/no-html-link-for-pages": "off",
    },
  },
]);
