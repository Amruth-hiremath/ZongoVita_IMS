import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";

export const metadata: Metadata = { title: "Audit Trail" };

/** Sidebar entry of the Platform Console without a frame (F51 and F53 link to it as "F54"). */
export default function PlatformAuditPage() {
  return (
    <NoScreen title="Audit Trail">
      The wireframes contain no Platform Console audit trail screen. F51 and F53 refer to it as F54, but no F54 frame
      exists.
    </NoScreen>
  );
}
