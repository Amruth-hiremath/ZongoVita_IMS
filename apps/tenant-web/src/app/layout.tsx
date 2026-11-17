import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { connection } from "next/server";
import type { ReactNode } from "react";

import "./globals.css";

// Self-hosted at build time: the Content Security Policy allows fonts from this origin only.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "IMS", template: "%s · IMS" },
  description: "ZongoVita Inventory Management",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The Content Security Policy carries a per-request nonce (src/proxy.ts), which Next.js can only
  // apply to pages rendered per request. A prerendered page would have its scripts blocked.
  await connection();
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
