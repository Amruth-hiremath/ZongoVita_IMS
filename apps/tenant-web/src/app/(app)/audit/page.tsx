import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getAdminAuditTrail, getManagerAuditTrail, getStoreAuditTrail } from "@/data/audit";
import { requireSession } from "@/session/server";

import { AuditTrail } from "./audit-trail";
import { StoreAudit } from "./store-audit";

export const metadata: Metadata = { title: "Audit Trail" };

/** F24 Audit Trail (admin: v1, manager) and F50 Audit Trail — site (store). */
export default async function AuditPage() {
  const { me, workspace } = await requireSession();
  const canExport = hasPermission(me, "reporting.export.run");
  const exportButton = canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export CSV</ActionButton> : null;

  if (workspace === "admin" || workspace === "manager") {
    const page = workspace === "admin" ? await getAdminAuditTrail() : await getManagerAuditTrail();
    return (
      <>
        <PageHeader
          title="Audit Trail"
          subtitle="Every stock adjustment — who, what, when · immutable · lifetime retention (Q22)"
          actions={exportButton}
        />
        <AuditTrail page={page} variant={workspace} />
      </>
    );
  }

  if (workspace === "store") {
    const page = await getStoreAuditTrail();
    return (
      <>
        <PageHeader
          title={`Audit Trail — ${page.site_code}`}
          actions={
            <>
              {exportButton}
              <ButtonLink href="#filter-the-trail" variant="primary">
                Filter
              </ButtonLink>
            </>
          }
          className="items-center"
        />
        <StoreAudit page={page} />
      </>
    );
  }

  return (
    <NoScreen title="Audit Trail">
      The wireframes draw the audit trail for User Types 1, 2 and 3 only (F24, F50). There is no frame for this user type.
    </NoScreen>
  );
}
