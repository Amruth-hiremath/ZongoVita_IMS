import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getManagerReturns, getStoreReturns } from "@/data/returns";
import { requireSession } from "@/session/server";

import { ManagerReturnsBoard } from "./manager-returns";
import { KpiRow } from "./parts";
import { StoreReturnsBoard } from "./store-returns";

export const metadata: Metadata = { title: "Returns" };

/** Returns: F43 Lifecycle & Dispositions (manager) or F49 Store Processing (store). */
export default async function ReturnsPage() {
  const { me, workspace } = await requireSession();

  if (workspace === "manager") {
    const data = await getManagerReturns();
    const open = data.verdicts.find((entry) => entry.return_ref === data.selected_ref);
    return (
      <>
        <PageHeader
          title="Returns — Lifecycle & Dispositions"
          subtitle="Every return in flight · quarantine verdicts sit with the approving user type (FB-13 → FB-16)"
          actions={
            <>
              <ActionButton endpoint="POST /ui/v1/exports">Export returns log</ActionButton>
              {open ? (
                <ButtonLink href="#verdict-panel" variant="primary">
                  Open {open.quarantine_ref}
                </ButtonLink>
              ) : null}
            </>
          }
        />
        <KpiRow kpis={data.kpis} />
        <ManagerReturnsBoard data={data} canDecide={hasPermission(me, "returns.verdict.decide")} />
      </>
    );
  }

  if (workspace === "store") {
    const data = await getStoreReturns();
    return (
      <>
        <PageHeader
          title="Returns — Store Processing"
          className="items-center"
          actions={
            <>
              {hasPermission(me, "reporting.export.run") ? (
              <ActionButton endpoint="POST /ui/v1/exports">Returns log</ActionButton>
            ) : null}
              <ButtonLink href="#validation-panel" variant="primary">
                Validate {data.selected_ref}
              </ButtonLink>
            </>
          }
        />
        <KpiRow kpis={data.kpis} />
        <StoreReturnsBoard data={data} canValidate={hasPermission(me, "returns.return.validate")} />
      </>
    );
  }

  return (
    <NoScreen title="Returns">
      The wireframes draw returns for the approving user type (F43) and the store desk (F49) only. There is no returns
      screen for this user type.
    </NoScreen>
  );
}
