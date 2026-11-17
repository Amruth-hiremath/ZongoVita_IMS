import { hasPermission } from "@ims/api-client";
import {
  ButtonLink,
  Callout,
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
} from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NoScreen } from "@/components/no-screen";
import { getReportsPage } from "@/data/reports";
import { formatMoney } from "@/lib/format";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Reports" };

/** F44 Reports — Catalog & Deliveries (manager workspace). */
export default async function ReportsPage() {
  const { me, workspace } = await requireSession();

  if (workspace !== "manager") {
    return (
      <NoScreen title="Reports">
        The wireframes draw the reports screen for User Type 2 only (F44). There is no frame for this user type.
      </NoScreen>
    );
  }

  const page = await getReportsPage();
  const canExport = hasPermission(me, "reporting.export.run");
  const { runs, approval_turnaround: turnaround, expiry, supplier_claims: claims } = page.kpis;

  return (
    <>
      <PageHeader
        title="Reports — Catalog & Deliveries"
        subtitle="Catalog scoped to your user type & site · outputs land in Recent outputs · exports CSV / Excel · API pull (FR-15)"
        actions={
          canExport ? (
            <>
              <ActionButton endpoint="POST /ui/v1/exports (format: pdf)" className="w-[142px]">
                Export as PDF
              </ActionButton>
              <ActionButton endpoint="POST /ui/v1/exports (format: xlsx)" variant="primary" className="w-[159px]">
                Export as Excel
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={`Report runs · ${runs.month_label}`}
          value={runs.total}
          hint={`${runs.scheduled} scheduled · ${runs.ad_hoc} ad-hoc`}
        />
        <StatCard
          label="Approval turnaround"
          value={`${turnaround.hours} h`}
          hint={`${turnaround.decisions} decisions · target ≤ ${turnaround.target_hours} h`}
        />
        <StatCard
          label="Expiry exposures"
          value={`${expiry.batches} batches`}
          badge={<Pill tone="amber">{expiry.inside_30_days} inside 30 d</Pill>}
        />
        <StatCard
          label="Supplier claims"
          value={formatMoney(claims.amount)}
          badge={<Pill tone="red">{claims.case_ref} live</Pill>}
        />
      </div>

      <div className="mt-3.5 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <div className="min-w-0">
          <SectionLabel className="mb-2">Report catalog — scoped to your user type & site (FB-23)</SectionLabel>
          <Table>
            <THead>
              <TR>
                <TH>Report</TH>
                <TH>Covers</TH>
                <TH align="center">Last run</TH>
                <TH align="center">Schedule</TH>
                <TH>State</TH>
              </TR>
            </THead>
            <TBody zebra>
              {page.catalog.map((row) => (
                <TR key={row.report_id}>
                  <TD strong className="whitespace-nowrap text-[13.5px]">
                    {row.name}
                  </TD>
                  <TD muted>{row.covers}</TD>
                  <TD muted align="center" className="whitespace-nowrap">
                    {row.last_run_label}
                  </TD>
                  <TD muted align="center">
                    {row.schedule}
                  </TD>
                  <TD>
                    <Pill tone={row.state.tone}>{row.state.label}</Pill>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>

          {page.alert ? (
            <Callout tone="warning" dismissible className="mt-4">
              {page.alert}
            </Callout>
          ) : null}

          <SectionLabel className="mb-2 mt-3">Recent outputs — generated & delivered</SectionLabel>
          <Table>
            <THead>
              <TR>
                <TH>Report</TH>
                <TH align="center">Generated</TH>
                <TH>By</TH>
                <TH>Format</TH>
                <TH>Sent to</TH>
                <TH align="center">State</TH>
              </TR>
            </THead>
            <TBody zebra>
              {page.outputs.map((row) => (
                <TR key={row.output_id}>
                  <TD strong className="whitespace-nowrap text-[13.5px]">
                    {row.report}
                  </TD>
                  <TD muted align="center" className="whitespace-nowrap">
                    {row.generated_label}
                  </TD>
                  <TD muted className="whitespace-nowrap">
                    {row.generated_by}
                  </TD>
                  <TD muted className="whitespace-nowrap">
                    {row.format}
                  </TD>
                  <TD muted>{row.sent_to}</TD>
                  <TD align="center">
                    <Pill tone={row.state.tone}>{row.state.label}</Pill>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>

        <div className="flex min-w-0 flex-col gap-3 lg:mt-3.5">
          <Card>
            <CardHeader title={`Preview — ${page.preview.title}`} />
            <CardBody className="pt-1">
              <dl className="border-b border-gray-300 pb-3 [&_dd]:text-gray-700">
                <KeyValue label="Period" className="py-1">
                  {page.preview.period}
                </KeyValue>
                <KeyValue label="Scope" className="py-1">
                  {page.preview.scope}
                </KeyValue>
                <KeyValue label="FAIL lines · Sep" className="py-1">
                  {page.preview.fail_lines}
                </KeyValue>
              </dl>
              <SectionLabel className="mb-1 mt-4">Per-supplier — {page.preview.month_label}</SectionLabel>
              <Table className="text-[11.5px]">
                <THead>
                  <TR>
                    <TH className="h-8">Vendor</TH>
                    <TH className="h-8" align="center">
                      Poor M
                    </TH>
                    <TH className="h-8" align="center">
                      Rate
                    </TH>
                    <TH className="h-8">Last event</TH>
                  </TR>
                </THead>
                <TBody zebra>
                  {page.preview.suppliers.map((row) => (
                    <TR key={row.vendor}>
                      <TD className="h-7 text-gray-600">{row.vendor}</TD>
                      <TD className="h-7 text-gray-600" align="center" numeric>
                        {row.poor_count}
                      </TD>
                      <TD
                        align="center"
                        numeric
                        className={row.breach ? "h-7 text-[13px] font-bold text-red-700" : "h-7 text-gray-600"}
                      >
                        {row.poor_rate}%
                      </TD>
                      <TD className="h-7 text-[12px] text-gray-700">{row.last_event ?? "—"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
                <ButtonLink href="/quality-register" className="w-[162px]">
                  Open register
                </ButtonLink>
                <ActionButton endpoint="POST /ui/v1/exports (deliver to purchasing)" variant="primary" className="w-[160px]">
                  Email to purchasing
                </ActionButton>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Scheduled deliveries"
              action={
                <ActionButton endpoint="PATCH /ui/v1/reports/{id}/schedule" variant="link" className="text-[12px]">
                  Manage →
                </ActionButton>
              }
            />
            <CardBody className="pb-10">
              <ul className="space-y-1.5 text-[11.5px] text-gray-700">
                {page.scheduled_deliveries.map((line) => (
                  <li key={line} className="flex items-center gap-3">
                    <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-blue-600" />
                    {line}
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
