import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";

export const metadata: Metadata = { title: "Enterprises" };

/** Sidebar entry of the Platform Console without a frame. */
export default function EnterprisesPage() {
  return (
    <NoScreen title="Enterprises">
      The wireframes contain no Enterprises screen: the Platform Console is drawn only as F51 Overview, F52 Licenses
      and F53 Platform Config.
    </NoScreen>
  );
}
