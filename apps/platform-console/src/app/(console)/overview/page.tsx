import {
  ButtonLink,
  Card,
  CardBody,
  CardHeader,
  KeyValue,
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
} from "@ims/ui";
import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { Fragment } from "react";

import { ActionButton } from "@/components/action-button";
import { getPlatformOverview } from "@/data/overview";

export const metadata: Metadata = { title: "Platform Overview" };

/** The four steps of the request pipeline card, as drawn. */
const pipeline = [
  { title: "Login", detail: "credentials + the enterprise's own sign-in" },
  { title: "Identify customer", detail: "the registry resolves which customer calls" },
  { title: "Check license", detail: "validity · sites · users · modules" },
  { title: "Use that DB only", detail: "every query hits one customer database" },
];

/** F51 Platform Overview. */
export default async function OverviewPage() {
  const page = await getPlatformOverview();
  const { enterprises, seats, uptime, api_today: api } = page.kpis;

  return (
    <>
      <PageHeader
        title="Platform Overview"
        subtitle="ZongoVita cloud — every enterprise, license, seat, database and API call at a glance (FB-20 · FB-22)"
        actions={
          <>
            <ActionButton endpoint="GET /platform/v1/customers (usage report export)" className="w-[116px] bg-none bg-white">
              Usage report
            </ActionButton>
            <ActionButton endpoint="POST /platform/v1/customers" variant="primary" className="w-[167px]">
              + Onboard enterprise
            </ActionButton>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Enterprises"
          value={enterprises.total}
          hint={`${enterprises.active} active · ${enterprises.onboarding} onboarding · ${enterprises.trial} trial`}
        />
        <StatCard
          label="Seats in use"
          value={`${seats.used} / ${seats.licensed}`}
          badge={<Pill tone="blue">{seats.utilisation_percent}% utilisation</Pill>}
        />
        <StatCard
          label="Platform uptime"
          value={`${uptime.percent}%`}
          hint={`${uptime.window} · SLA ${uptime.sla_percent}%`}
        />
        <StatCard label="API calls · today" value={api.calls} hint={`p95 ${api.p95_ms} ms · ${api.failures} failures`} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <div className="min-w-0">
          <SectionLabel className="mb-2">Tenant pulse — every row is an isolated customer database</SectionLabel>
          <Table className="[&_td]:px-2.5 [&_th]:px-2.5">
            <THead>
              <TR>
                <TH>Ent</TH>
                <TH>Company</TH>
                <TH>Plan</TH>
                <TH>Database</TH>
                <TH align="center">Seats</TH>
                <TH align="right">API · 7 d</TH>
                <TH>Last activity</TH>
              </TR>
            </THead>
            <TBody zebra>
              {page.tenants.map((row) => (
                <TR key={row.enterprise_code}>
                  <TD className="whitespace-nowrap text-[12.5px] text-gray-700">{row.enterprise_code}</TD>
                  <TD className="whitespace-nowrap text-gray-700">{row.company}</TD>
                  <TD muted>{row.plan ?? "—"}</TD>
                  <TD className="whitespace-nowrap text-[12.5px] text-gray-700">{row.database}</TD>
                  <TD muted align="center" numeric className="whitespace-nowrap">
                    {row.seats_used} / {row.seats_licensed}
                  </TD>
                  <TD muted align="right" numeric className="whitespace-nowrap">
                    {row.api_calls_7d ?? "—"}
                  </TD>
                  <TD muted className="whitespace-nowrap">
                    {row.last_activity_label}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>

          <Card className="mt-6">
            <CardHeader title="Request pipeline — every call, the same four steps" />
            <CardBody className="pb-8 pt-5">
              <ol className="flex items-stretch gap-1.5 max-lg:flex-col">
                {pipeline.map((step, index) => (
                  <Fragment key={step.title}>
                    {index > 0 ? (
                      <li aria-hidden className="flex items-center justify-center text-gray-400 max-lg:hidden">
                        <ArrowRight className="size-3" strokeWidth={1.6} />
                      </li>
                    ) : null}
                    <li className="min-w-0 flex-1 rounded-md border-[1.1px] border-gray-200 bg-gray-50 px-2.5 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-gray-300 bg-linear-to-b from-blue-600 to-brand-deep text-[10px] font-semibold text-white">
                          {index + 1}
                        </span>
                        <span className="text-[12.5px] font-semibold text-gray-900">{step.title}</span>
                      </div>
                      <p className="mt-1.5 pl-1 text-[10px] leading-[13px] text-gray-500">{step.detail}</p>
                    </li>
                  </Fragment>
                ))}
              </ol>
            </CardBody>
          </Card>

          <Card className="mt-4">
            <CardHeader title="Platform health (NFR)" />
            <CardBody className="pb-1.5 pr-12 pt-3">
              <dl className="[&_dd]:text-gray-700 [&_dt]:text-gray-500">
                {page.health.map((row) => (
                  <KeyValue key={row.label} label={row.label} className="py-0.5">
                    {row.value}
                  </KeyValue>
                ))}
              </dl>
            </CardBody>
          </Card>
        </div>

        <Card className="self-start lg:mt-[22px] lg:min-h-[282px]">
          <CardHeader
            title="Platform activity"
            action={
              <ButtonLink href="/audit" variant="link" className="text-[12px]">
                Full trail → F54
              </ButtonLink>
            }
          />
          <CardBody className="pl-6 pt-5">
            <Timeline
              entries={page.activity.map((entry) => ({ title: entry.title, meta: entry.meta }))}
              className="[&_p:first-child]:text-[12.5px]"
            />
          </CardBody>
        </Card>
      </div>
    </>
  );
}
