import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const FIXTURE_MESSAGE =
  "Sample data lives in src/fixtures and is reached only through the data layer (src/data) or the " +
  "session module. A screen that imports a fixture directly cannot be switched to the real API in one place.";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    rules: {
      // The app runs under a strict Content Security Policy without 'unsafe-inline' for styles
      // (LD-49), so a style attribute would simply be dropped by the browser.
      "react/forbid-dom-props": ["error", { forbid: ["style"] }],
      "react/forbid-component-props": ["error", { forbid: ["style"] }],
      "no-restricted-imports": ["error", { patterns: [{ group: ["@/fixtures", "@/fixtures/*"], message: FIXTURE_MESSAGE }] }],
    },
  },
  {
    // The only places allowed to read fixtures.
    files: ["src/data/**/*.ts", "src/session/server.ts", "src/fixtures/**/*.ts"],
    rules: { "no-restricted-imports": "off" },
  },
]);
