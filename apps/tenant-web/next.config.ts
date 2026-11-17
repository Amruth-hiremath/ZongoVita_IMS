import type { NextConfig } from "next";

const config: NextConfig = {
  // Shared packages ship TypeScript source; Next compiles them with the app.
  transpilePackages: ["@ims/ui", "@ims/api-client"],
  reactStrictMode: true,
  poweredByHeader: false,
  // Static security headers. The Content-Security-Policy carries a per-request nonce and is set
  // in src/proxy.ts (LD-49: strict CSP with nonces, frame-ancestors none, HSTS).
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
