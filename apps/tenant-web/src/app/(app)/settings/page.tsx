import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";

export const metadata: Metadata = { title: "Settings" };

/** Sidebar entry "Settings" (admin menu). The wireframes draw no Settings screen. */
export default function SettingsPage() {
  return (
    <NoScreen title="Settings">
      The admin menu has a Settings entry, but the wireframes contain no Settings screen. Customer settings (GET and
      PATCH /ui/v1/settings) will get a screen once one is designed.
    </NoScreen>
  );
}
