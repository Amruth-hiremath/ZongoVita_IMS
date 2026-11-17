import { hasPermission, type Me } from "@ims/api-client";
import {
  ButtonLink,
  Card,
  CardHeader,
  PageHeader,
  Pill,
  SectionLabel,
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

import { ActionButton } from "@/components/action-button";
import { getStoreDashboard, type InboundState, type QuarantineAgingKind, type QueueState } from "@/data/dashboard";
import { formatQty } from "@/lib/format";

const queueTone: Record<QueueState, Tone> = { ready_to_pick: "blue", picking: "amber" };
const inboundTone: Record<InboundState, Tone> = { in_transit: "blue", awaiting_grn: "amber", posted: "green" };
const quarantineTone: Record<QuarantineAgingKind, Tone> = { overdue: "red", due_today: "amber", spec_check: "blue" };

/** F48 Store dashboard (User Type 3): "Namaste, <first name>". */
export async function StoreDashboard({ me }: { me: Me }) {
  const { summary, queue, inbound, actions, quarantine, count } = await getStoreDashboard();
  const firstName = me.principal.display_name.split(/\s+/)[0] ?? me.principal.display_name;
  const canFulfil = hasPermission(me, "issuance.issue.fulfil");

  return (
    <>
      <PageHeader
        title={`Namaste, ${firstName}`}
        subtitle={`${summary.date_label} · ${summary.site_code} · your queue, inbound and validations today`}
        actions={
          canFulfil ? (
            <>
              <ActionButton endpoint="POST /ui/v1/exports (pick lists)" className="w-32">
                Print pick lists
              </ActionButton>
              <ButtonLink variant="primary" href="/scan-issue">
                Start picking {summary.next_pick_ref}
              </ButtonLink>
            </>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Fulfilment queue"
          value={formatQty(summary.queue_count)}
          badge={<Pill tone="blue">SLA {summary.queue_sla}</Pill>}
        />
        <StatCard
          label="Inbound due"
          value={`${summary.inbound_due.length} POs`}
          hint={summary.inbound_due.map((po) => `${po.po_number} ${po.due}`).join(" · ")}
        />
        <StatCard
          label="Quarantine open"
          value={`${summary.quarantine_open_lines} lines`}
          badge={<Pill tone="red">{summary.quarantine_overdue} overdue</Pill>}
        />
        <StatCard
          label="Count in progress"
          value={formatQty(summary.counts_in_progress)}
          badge={summary.count_blind ? <Pill tone="amber">blind mode</Pill> : undefined}
        />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <div className="min-w-0">
          <SectionLabel className="mb-2.5">Fulfilment queue — approved &amp; locked, waiting for you</SectionLabel>
          <Table>
            <THead>
              <TR>
                <TH>Ref</TH>
                <TH>Requester</TH>
                <TH>Site</TH>
                <TH align="center">Lines</TH>
                <TH>Locked ago</TH>
                <TH>SLA</TH>
                <TH>State</TH>
              </TR>
            </THead>
            <TBody zebra>
              {queue.map((row) => (
                <TR key={row.ref}>
                  <TD className="text-gray-700">{row.ref}</TD>
                  <TD>{row.requester}</TD>
                  <TD muted>{row.site}</TD>
                  <TD muted align="center">
                    {row.lines}
                  </TD>
                  <TD muted>{row.locked_ago}</TD>
                  <TD muted>{row.sla}</TD>
                  <TD>
                    <Pill tone={queueTone[row.state.kind]}>{row.state.label}</Pill>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>

          <SectionLabel className="mb-2.5 mt-9">Inbound — expected POs &amp; today&apos;s GRN</SectionLabel>
          <div className="max-w-[660px]">
            <Table>
              <THead>
                <TR>
                  <TH>PO / GRN</TH>
                  <TH>Vendor · posted</TH>
                  <TH>Items · value</TH>
                  <TH>When</TH>
                  <TH>State</TH>
                </TR>
              </THead>
              <TBody zebra>
                {inbound.map((row) => (
                  <TR key={row.ref}>
                    <TD className="text-gray-700">{row.ref}</TD>
                    <TD muted>{row.vendor_or_posted}</TD>
                    <TD muted>{row.items_value}</TD>
                    <TD muted>{row.when}</TD>
                    <TD>
                      <Pill tone={inboundTone[row.state.kind]}>{row.state.label}</Pill>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-4 lg:mt-3">
          <Card>
            <CardHeader title="Today so far — your actions" />
            <div className="px-4 pb-4 pt-5">
              <Timeline entries={actions} />
            </div>
          </Card>

          <Card>
            <CardHeader title="Quarantine aging — your validations" className="pt-8" />
            <ul className="flex flex-col gap-2 px-4 pb-6 pt-3">
              {quarantine.map((row) => (
                <li key={row.ref} className="flex items-center justify-between gap-3 text-[12px] text-gray-700">
                  <span>
                    {row.ref} · {row.summary}
                  </span>
                  <Pill tone={quarantineTone[row.status.kind]}>{row.status.label}</Pill>
                </li>
              ))}
            </ul>
          </Card>

          {count ? (
            <Card>
              <CardHeader
                title={`Count in progress — ${count.count_no}`}
                action={
                  <ButtonLink variant="link" href={`/stock-counts/${count.count_no}`}>
                    Resume →
                  </ButtonLink>
                }
              />
              <p className="px-4 pb-4 pt-7 text-[11px] text-gray-500">{count.summary}</p>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
