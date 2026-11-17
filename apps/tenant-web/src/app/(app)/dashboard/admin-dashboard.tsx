import { hasPermission, type Me } from "@ims/api-client";
import {
  ButtonLink,
  Card,
  CardHeader,
  KeyValue,
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
import { Building2, Check, MapPin, Shield, Tag, Users, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { ActionButton } from "@/components/action-button";
import { getAdminDashboard, type ApprovalTaskKind } from "@/data/dashboard";
import { formatMoney, formatQty } from "@/lib/format";

/** "Waiting on" pill tone per task kind, as drawn (the category proposal is amber). */
const waitingTone: Record<ApprovalTaskKind, Tone> = {
  issuance_request: "blue",
  transfer: "blue",
  taxonomy_proposal: "amber",
};

const quickLinks: { label: string; href: string; frame: string; icon: LucideIcon }[] = [
  { label: "Users & types", href: "/users", frame: "F22", icon: Users },
  { label: "Locations", href: "/locations", frame: "F21", icon: MapPin },
  { label: "Approval workflow", href: "/approvals/configuration", frame: "F23", icon: Check },
  { label: "Categories", href: "/categories", frame: "F25", icon: Tag },
  { label: "Vendors & purchases", href: "/vendors", frame: "F37", icon: Building2 },
  { label: "Audit trail", href: "/audit", frame: "F24", icon: Shield },
];

/** F04 Dashboard — Type 1: system health, access control and integrations. */
export async function AdminDashboard({ me }: { me: Me }) {
  const { summary, health, integration, approvals, audit } = await getAdminDashboard();
  const canSync = hasPermission(me, "integration.connector.manage");

  return (
    <>
      <PageHeader
        title="Dashboard — Type 1"
        subtitle={`System health, access control and integrations across ${summary.locations.total} locations`}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Locations"
          value={formatQty(summary.locations.total)}
          hint={`${summary.locations.live} live · ${summary.locations.staged} staged`}
        />
        <StatCard
          label="Items in catalog"
          value={formatQty(summary.items.total)}
          hint={`${summary.items.category_count} categories`}
        />
        <StatCard
          label="Active users"
          value={formatQty(summary.active_users.total)}
          hint={summary.active_users.by_user_type.map((group) => `T${group.user_type_no} ${group.count}`).join(" · ")}
        />
        <StatCard
          label="Pending approvals"
          value={formatQty(summary.pending_approvals.total)}
          badge={<Pill tone="amber">{summary.pending_approvals.request_count} requests</Pill>}
        />
        <StatCard label="Stock value" value={formatMoney(summary.stock_value)} hint="All locations" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card>
          <CardHeader
            title="System health (NFR)"
            action={
              health.state === "healthy" ? (
                <Pill tone="green" className="mt-5">
                  Healthy
                </Pill>
              ) : (
                <Pill tone="amber" className="mt-5">
                  Degraded
                </Pill>
              )
            }
            className="items-start"
          />
          <dl className="px-4 pb-4 pr-9 max-sm:pr-4">
            {health.rows.map((row) => (
              <KeyValue key={row.label} label={row.label} className="py-2">
                {row.value}
              </KeyValue>
            ))}
          </dl>
        </Card>

        <Card>
          <CardHeader title="Integrations" action={<ButtonLink variant="link" href="/settings">Open →</ButtonLink>} />
          <div className="px-4 pb-4 pt-5">
            <p className="text-[13px] font-semibold text-gray-900">{integration.name}</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              <Pill tone={integration.connected ? "green" : "red"}>
                {integration.connected ? "Connected" : "Disconnected"}
              </Pill>
              <Pill tone="blue">API {integration.api_version}</Pill>
            </div>
            <p className="mt-2 text-[11px] leading-[18px] text-gray-500">
              Last sync {integration.last_sync} · {integration.events_today} events today · {integration.failures_today}{" "}
              failures ({integration.failure_handling})
              <br />
              {integration.free_connector_slots} connector slots available — {integration.connector_kinds.join(", ")}
            </p>
            {canSync ? (
              <ActionButton variant="soft" className="mt-2" endpoint="POST /ui/v1/connectors/{id}/sync">
                Sync now
              </ActionButton>
            ) : null}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Approvals queue (configurable — Q3)"
            action={
              <ButtonLink variant="link" href="/approvals/configuration">
                Configure workflow →
              </ButtonLink>
            }
          />
          <div className="px-4 pb-2.5 pt-2">
            <Table>
              <THead>
                <TR>
                  <TH>Ref</TH>
                  <TH>Activity</TH>
                  <TH>Location</TH>
                  <TH>Raised by</TH>
                  <TH>Waiting on</TH>
                </TR>
              </THead>
              <TBody zebra>
                {approvals.map((row) => (
                  <TR key={row.ref}>
                    <TD className="text-gray-700">{row.ref}</TD>
                    <TD>{row.activity}</TD>
                    <TD>{row.location}</TD>
                    <TD>{row.raised_by}</TD>
                    <TD>
                      <Pill tone={waitingTone[row.kind]}>{row.waiting_on}</Pill>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </Card>

        <Card>
          <CardHeader title="Recent audit" action={<ButtonLink variant="link" href="/audit">Full trail →</ButtonLink>} />
          <div className="px-4 pb-4 pt-6">
            <Timeline entries={audit} />
          </div>
        </Card>
      </div>

      <Card className="mt-6 px-4 pb-3.5 pt-3">
        <h2 className="text-[13.5px] font-semibold text-gray-900">Quick links</h2>
        <div className="mt-1.5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="relative flex h-[76px] flex-col justify-end rounded-lg border-[1.4px] border-gray-200 bg-gray-50 px-4 pb-3 hover:border-blue-200"
            >
              <span className="absolute right-3 top-2 text-[10px] text-gray-400">{link.frame}</span>
              <link.icon aria-hidden className="mb-2.5 size-4 text-blue-600" strokeWidth={1.8} />
              <span className="text-[12.5px] font-semibold text-gray-900">{link.label}</span>
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}
