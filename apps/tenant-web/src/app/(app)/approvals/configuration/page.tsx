import { hasPermission } from "@ims/api-client";
import { ButtonLink, Callout, PageHeader } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getApprovalConfiguration } from "@/data/approval-config";
import { requireSession } from "@/session/server";

import { ConfigurationEditor } from "./configuration-editor";

export const metadata: Metadata = { title: "Approval Workflow Configuration" };

/** F23 Approval Workflow Configuration. */
export default async function ApprovalConfigurationPage() {
  const [{ me }, config] = await Promise.all([requireSession(), getApprovalConfiguration()]);
  const canEdit = hasPermission(me, "workflow.policy.manage");

  return (
    <>
      <PageHeader
        title="Approval Workflow Configuration"
        actions={
          <>
            {hasPermission(me, "audit.log.view") ? <ButtonLink href="/audit">View change history</ButtonLink> : null}
            {canEdit ? (
              <ActionButton endpoint="PUT /ui/v1/approval-policies/{id}" variant="primary">
                Save configuration
              </ActionButton>
            ) : null}
          </>
        }
      />
      <ConfigurationEditor config={config} canEdit={canEdit} />
      <Callout tone="info" dismissible className="mt-4 min-h-[42px]">
        Everything on this screen is live configuration — changes apply across F05 / F14 / F15 / F17 / F27 immediately,
        with zero code deploys (NFR-8).
      </Callout>
    </>
  );
}
