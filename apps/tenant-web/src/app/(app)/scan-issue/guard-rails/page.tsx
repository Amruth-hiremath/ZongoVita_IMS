import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";
import { getIssueGuardRails } from "@/data/issues";
import { requireSession } from "@/session/server";

import { GuardRailStates } from "./guard-rail-states";

export const metadata: Metadata = { title: "Issue — Guard-rail States" };

/** F12 Issue — guard-rail states: the failure outcomes of posting F11 (Q7, Q20), with success for contrast. */
export default async function IssueGuardRailsPage() {
  const { workspace } = await requireSession();
  if (workspace !== "store") {
    return (
      <NoScreen title="Issue — Guard-rail States">
        The wireframes draw the issue guard-rail states for store staff only; there is no such screen for this user
        type.
      </NoScreen>
    );
  }

  const states = await getIssueGuardRails();
  return <GuardRailStates states={states} />;
}
