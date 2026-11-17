import {
  Card,
  CardBody,
  CardHeader,
  KeyValue,
  NoteBox,
  PageHeader,
  Pill,
  SectionLabel,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  cn,
} from "@ims/ui";
import { AlertTriangle } from "lucide-react";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getLicencesPage } from "@/data/licences";

export const metadata: Metadata = { title: "Licenses & Plans" };

const money = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** The three steps of "How the license check works", as drawn. */
const checkSteps = [
  { title: "Identify the customer", detail: "login and every API call carry the enterprise" },
  { title: "Check the registry row", detail: "validity · sites · users · modules" },
  { title: "Route to that customer's database", detail: "never a shared one — by construction" },
];

/** F52 Licenses & Plans. */
export default async function LicensesPage() {
  const page = await getLicencesPage();

  return (
    <>
      <PageHeader
        title="Licenses & Plans"
        subtitle="The license registry — one row per customer: validity · sites · users · modules, mapped to that customer's database (FB-20)"
        actions={
          <>
            <ActionButton endpoint="GET /platform/v1/licences (billing export)" className="w-[119px] bg-none bg-white">
              Billing export
            </ActionButton>
            <ActionButton endpoint="POST /platform/v1/licences" variant="primary" className="w-[124px]">
              Assign license
            </ActionButton>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {page.plans.map((plan) => (
          <Card key={plan.plan_id} className="px-5 pb-4 pt-3.5">
            <div className="flex items-start justify-between gap-3">
              <h2 className="pt-0.5 text-[15px] font-semibold text-gray-900">{plan.name}</h2>
              <Pill tone={plan.badge.tone} className={cn(plan.badge.tone === "gray" && "text-gray-500")}>
                {plan.badge.label}
              </Pill>
            </div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-10 gap-y-1">
              <span className="tabular whitespace-nowrap text-[22px] font-bold text-gray-900">₹ {money.format(Number(plan.price_per_seat_month))}</span>
              <span className="text-[11px] text-gray-500">per seat / month</span>
            </div>
            <ul className="mt-3 text-[11.5px] leading-[14px] text-gray-700">
              {plan.entitlements.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      <SectionLabel className="mb-2 mt-5">License registry — one row per customer, one database per customer</SectionLabel>
      <Table>
        <THead>
          <TR>
            <TH>Ent</TH>
            <TH>Company</TH>
            <TH>Plan</TH>
            <TH>Valid till</TH>
            <TH align="center">Sites</TH>
            <TH align="center">Users</TH>
            <TH>Modules</TH>
            <TH>Database</TH>
            <TH>Status</TH>
          </TR>
        </THead>
        <TBody zebra>
          {page.registry.map((row) => (
            <TR key={row.enterprise_code} className="h-12">
              <TD className="whitespace-nowrap text-[12.5px] text-gray-700">{row.enterprise_code}</TD>
              <TD className="whitespace-nowrap text-gray-700">{row.company}</TD>
              <TD muted>{row.plan}</TD>
              <TD muted className="whitespace-nowrap">
                {row.valid_till_label}
              </TD>
              <TD muted align="center" numeric className="whitespace-nowrap">
                {row.sites_used} / {row.sites_licensed ?? "unlimited"}
              </TD>
              <TD muted align="center" numeric className="whitespace-nowrap">
                {row.users_used} / {row.users_licensed}
              </TD>
              <TD muted className="whitespace-nowrap">
                {row.modules.join(" · ")}
              </TD>
              <TD className="whitespace-nowrap text-[12.5px] text-gray-700">{row.database}</TD>
              <TD>
                <Pill tone={row.status.tone}>{row.status.label}</Pill>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <div className="mt-7 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card>
          <CardHeader title="How the license check works" />
          <CardBody>
            <ol>
              {checkSteps.map((step, index) => (
                <li key={step.title} className="relative flex gap-3 pb-2 last:pb-0">
                  {index < checkSteps.length - 1 ? (
                    <span aria-hidden className="absolute bottom-0 left-[11px] top-6 w-px bg-gray-300" />
                  ) : null}
                  <span
                    className={cn(
                      "relative flex size-6 shrink-0 items-center justify-center rounded-full text-[10.5px] font-semibold",
                      index === 0 ? "bg-blue-600 text-white" : "border-[1.4px] border-gray-300 bg-white text-gray-600",
                    )}
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12.5px] font-semibold leading-4 text-gray-900">{step.title}</p>
                    <p className="text-[10.5px] leading-[14px] text-gray-500">{step.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
            <NoteBox tone="red" className="mt-1.5 flex items-center gap-2.5 py-2">
              <AlertTriangle aria-hidden className="size-4 shrink-0 text-red-700" strokeWidth={1.6} />
              <p className="text-[11px] text-gray-700">
                EXPIRED → every site of that customer is blocked — logins and API alike; data intact; renewal lifts the block.
              </p>
            </NoteBox>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title={`Renewal & dunning — ${page.renewal.enterprise_code}`} />
          <CardBody className="pt-5">
            <p className="text-[13px] font-semibold text-gray-900">{page.renewal.company}</p>
            <Pill tone="amber" className="mt-1">
              {page.renewal.status_label}
            </Pill>
            <dl className="mt-1 [&_dd]:text-gray-700">
              <KeyValue label="Reminder" className="py-1">
                {page.renewal.reminder}
              </KeyValue>
              <KeyValue label="Grace period" className="py-1">
                {page.renewal.grace_period}
              </KeyValue>
              <KeyValue label="Auto-suspend" className="py-1">
                {page.renewal.auto_suspend}
              </KeyValue>
            </dl>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
