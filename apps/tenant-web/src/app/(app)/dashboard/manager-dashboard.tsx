import { hasPermission, type Me } from "@ims/api-client";
import {
  ButtonLink,
  Card,
  CardHeader,
  NoteBox,
  PageHeader,
  Pill,
  StatCard,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Timeline,
  type Tone,
} from "@ims/ui";
import Link from "next/link";

import { ActionButton } from "@/components/action-button";
import { getManagerDashboard, type AttentionKind } from "@/data/dashboard";
import { formatMoney, formatQty } from "@/lib/format";

const attentionTone: Record<AttentionKind, Tone> = {
  below_min: "red",
  batch_expiring: "amber",
  expiry_window: "amber",
  dead: "dark",
};

/** F05 Inventory Overview (User Type 2). */
export async function ManagerDashboard({ me }: { me: Me }) {
  const { summary, attention, waiting, reorder, movements } = await getManagerDashboard();
  const canApprove = hasPermission(me, "issuance.request.approve");

  return (
    <>
      <PageHeader
        title="Inventory Overview"
        subtitle={`${summary.date_label} · ${summary.scope_site_code} scope · live stock & locks visible at approval (FB-08)`}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Stock value"
          value={formatMoney(summary.stock_value)}
          hint={`${formatQty(summary.item_count)} items · ${summary.location_count} locations`}
        />
        <StatCard
          label="Low-stock alerts"
          value={formatQty(summary.low_stock_alerts)}
          badge={<Pill tone="red">{summary.critical_alerts} critical</Pill>}
        />
        <StatCard
          label="Requests to approve"
          value={formatQty(summary.requests_to_approve)}
          badge={<Pill tone="blue">FB-09</Pill>}
        />
        <StatCard
          label="Units locked"
          value={formatQty(summary.units_locked)}
          hint={`${summary.live_locks} live locks · F28`}
        />
        <StatCard
          label="Dead stock"
          value={formatMoney(summary.dead_stock_value)}
          badge={
            <Link href="/reports" className="inline-flex">
              <Pill tone="dark">Report</Pill>
            </Link>
          }
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card className="overflow-hidden pb-7">
          <CardHeader title="Needs attention" action={<ButtonLink variant="link" href="/alerts">View all alerts →</ButtonLink>} />
          <Table className="mt-4">
            <THead>
              <TR>
                <TH>Item</TH>
                <TH>Location</TH>
                <TH align="center">On hand / Min</TH>
                <TH>Status</TH>
              </TR>
            </THead>
            <TBody zebra>
              {attention.map((row) => (
                <TR key={`${row.item_code}-${row.location}`} className="[&>td]:h-[38px]">
                  <TD strong>{row.name}</TD>
                  <TD className="text-gray-700">{row.location}</TD>
                  <TD align="center" numeric className="text-gray-700">
                    {formatQty(row.on_hand)} / {row.min === null ? "—" : formatQty(row.min)}
                  </TD>
                  <TD>
                    <Pill tone={attentionTone[row.status.kind]}>{row.status.label}</Pill>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>

        <Card>
          <CardHeader title="Waiting on you" action={<ButtonLink variant="link" href="/approvals">Workspace →</ButtonLink>} />
          <div className="flex flex-col gap-4 p-4 pt-2.5">
            {waiting.map((task) => (
              <NoteBox key={task.task_id} tone="gray" className="px-4 pb-2.5 pt-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[13px] font-semibold text-gray-900">
                    {task.ref} · {task.requester}
                  </p>
                  <Pill tone="blue" small>
                    {task.state_label}
                  </Pill>
                </div>
                <p className="mt-0.5 text-[10.5px] text-gray-500">
                  {task.kind_label} · {task.requester}
                </p>
                <p className="mt-1 text-[11px] text-gray-700">{task.lines_summary}</p>
                <p className="mt-0.5 text-[10.5px] text-gray-500">First approval locks the requested units (FB-09)</p>
                {canApprove ? (
                  <div className="mt-2 flex gap-2">
                    <ActionButton
                      variant="primary"
                      size="sm"
                      className="w-[84px]"
                      endpoint="POST /ui/v1/approval-tasks/{id}/approve"
                    >
                      Approve
                    </ActionButton>
                    <ActionButton size="sm" className="w-[72px]" endpoint="POST /ui/v1/approval-tasks/{id}/reject">
                      Reject
                    </ActionButton>
                  </div>
                ) : null}
              </NoteBox>
            ))}
          </div>
        </Card>

        <Card className="overflow-hidden pb-7">
          <CardHeader
            title="Reorder suggestions (top 4)"
            action={
              <ButtonLink variant="link" href="/alerts">
                All suggestions →
              </ButtonLink>
            }
          />
          <Table className="mt-4">
            <THead>
              <TR>
                <TH>Item</TH>
                <TH>Location</TH>
                <TH align="right">On hand</TH>
                <TH align="right">Min</TH>
                <TH align="center">Lead PO+ven</TH>
                <TH align="right">Suggested</TH>
              </TR>
            </THead>
            <TBody zebra>
              {reorder.map((row) => (
                <TR key={`${row.item_code}-${row.location}`} className="[&>td]:h-[34px]">
                  <TD strong>{row.name}</TD>
                  <TD className="text-gray-700">{row.location}</TD>
                  <TD align="right" numeric className="text-gray-700">
                    {formatQty(row.on_hand)}
                  </TD>
                  <TD align="right" numeric className="text-gray-700">
                    {formatQty(row.min)}
                  </TD>
                  <TD align="center" numeric muted>
                    {row.lead_po_days}+{row.lead_vendor_days}
                  </TD>
                  <TD align="right" numeric strong>
                    {formatQty(row.suggested_qty)} {row.uom}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>

        <Card>
          <CardHeader title="Recent movements" action={<ButtonLink variant="link" href="/audit">Audit trail →</ButtonLink>} />
          <div className="px-4 pb-4 pt-5">
            <Timeline entries={movements} />
          </div>
        </Card>
      </div>
    </>
  );
}
