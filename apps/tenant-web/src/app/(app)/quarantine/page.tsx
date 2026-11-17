import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader, Pill, StatCard } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getQuarantineQueue } from "@/data/quarantine";
import { requireSession } from "@/session/server";

import { QuarantineBoard } from "./quarantine-board";

export const metadata: Metadata = { title: "Quarantine Validation Queue" };

/** F32 Quarantine Validation Queue (store desk). */
export default async function QuarantinePage() {
  const { me, workspace } = await requireSession();

  if (workspace !== "store") {
    return (
      <NoScreen title="Quarantine Validation Queue">
        The wireframes draw the quarantine validation queue for the store desk (F32) only. Verdicts for the approving
        user type are on Returns (F43).
      </NoScreen>
    );
  }

  const data = await getQuarantineQueue();

  return (
    <>
      <PageHeader
        title="Quarantine Validation Queue"
        className="items-center"
        actions={
          <>
            <ActionButton endpoint="POST /ui/v1/exports">Export hold report</ActionButton>
            <ButtonLink href="#validation-checklist" variant="primary">
              Open {data.selected_ref}
            </ButtonLink>
          </>
        }
      />
      <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        {data.kpis.map((kpi) => (
          <StatCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            hint={kpi.hint}
            badge={kpi.badge ? <Pill tone={kpi.badge.tone}>{kpi.badge.label}</Pill> : undefined}
          />
        ))}
      </div>
      <QuarantineBoard data={data} canValidate={hasPermission(me, "returns.return.validate")} />
    </>
  );
}
