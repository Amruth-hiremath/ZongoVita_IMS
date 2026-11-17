import { hasPermission, type Me } from "@ims/api-client";
import {
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
  ButtonLink,
  type Tone,
} from "@ims/ui";

import { ActionButton } from "@/components/action-button";
import type { GrnState, InwardPipeline, PipelineStatus } from "@/data/receiving";
import { formatMoney } from "@/lib/format";

import { formatDay as formatDate } from "@/lib/dates";

const statusTone: Record<PipelineStatus, Tone> = {
  awaiting_grn: "amber",
  in_transit: "blue",
  exception: "red",
};

const grnTone: Record<GrnState, Tone> = { posted: "green", held: "red" };

/** F42 Receiving — Inward Pipeline (approving user type). */
export function InwardPipelineView({ me, data }: { me: Me; data: InwardPipeline }) {
  const review = data.reviews.find((entry) => entry.po_number === data.review_po);
  const canInspect = hasPermission(me, "receiving.grn.inspect");

  return (
    <>
      <PageHeader
        title="Receiving — Inward Pipeline"
        subtitle="POs on their way in · GRN activity · inspection outcomes write back to purchase records (FB-26)"
        actions={
          <>
            <ActionButton endpoint="POST /ui/v1/exports">Export inward report</ActionButton>
            {review ? (
              <ButtonLink href="#inspection-review" variant="primary">
                Open {review.po_number} review
              </ButtonLink>
            ) : null}
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

      <div className="mt-3.5 grid grid-cols-[minmax(0,1fr)_412px] gap-6 max-lg:grid-cols-1">
        <div className="min-w-0">
          <SectionLabel>Inbound pipeline — purchase records awaiting inward</SectionLabel>
          <div className="mt-2">
            <Table className="[&_td]:whitespace-nowrap [&_td]:px-3 [&_th]:px-3">
              <THead>
                <TR>
                  <TH>PO</TH>
                  <TH>Vendor</TH>
                  <TH>Items</TH>
                  <TH align="center">Inward due</TH>
                  <TH>Expected use</TH>
                  <TH>Inspection</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody zebra>
                {data.pipeline.map((row) => (
                  <TR key={row.po_number}>
                    <TD>{row.po_number}</TD>
                    <TD muted>{row.vendor_name}</TD>
                    <TD muted>{row.items_summary}</TD>
                    <TD muted align="center">
                      {row.inward_due}
                    </TD>
                    <TD muted>{formatDate(row.expected_use_date)}</TD>
                    <TD muted align={row.inspection ? "left" : "center"}>
                      {row.inspection ?? "—"}
                    </TD>
                    <TD>
                      <Pill tone={statusTone[row.status.kind]}>{row.status.label}</Pill>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>

          <Callout tone="info" dismissible className="mt-5">
            {data.pipeline_notice}
          </Callout>

          <SectionLabel className="mt-4">Recent GRNs — inspection outcome per receipt</SectionLabel>
          <div className="mt-2">
            <Table className="[&_td]:whitespace-nowrap [&_td]:px-3 [&_th]:px-3">
              <THead>
                <TR>
                  <TH>GRN</TH>
                  <TH>Posted</TH>
                  <TH>Received by</TH>
                  <TH>Lines · value</TH>
                  <TH>PO</TH>
                  <TH>Inspection</TH>
                  <TH>State</TH>
                </TR>
              </THead>
              <TBody zebra>
                {data.recent_grns.map((grn) => (
                  <TR key={grn.grn_number}>
                    <TD>{grn.grn_number}</TD>
                    <TD muted>{grn.posted}</TD>
                    <TD muted>{grn.received_by}</TD>
                    <TD muted>
                      {grn.lines_summary} · {formatMoney(grn.value)}
                    </TD>
                    <TD>{grn.po_number}</TD>
                    <TD muted>{grn.inspection}</TD>
                    <TD>
                      <Pill tone={grnTone[grn.state.kind]}>{grn.state.label}</Pill>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>

          <p className="mt-[72px] text-[11px] text-gray-500 max-lg:mt-6">{data.footnote}</p>
        </div>

        <div className="flex min-w-0 flex-col gap-3 lg:mt-[22px]">
          {review ? (
            <Card id="inspection-review" className="scroll-mt-6">
              <CardHeader title={`Inspection review — ${review.po_number}`} />
              <CardBody className="pt-1.5">
                <dl>
                  {review.facts.map((fact) => (
                    <KeyValue key={fact.label} label={fact.label} className="py-[5px]">
                      {fact.value}
                    </KeyValue>
                  ))}
                </dl>
                <div className="mt-4 border-t border-gray-200 pt-4">
                  <SectionLabel>Findings</SectionLabel>
                  <p className="mt-1 max-w-[300px] text-[12px] leading-4 text-gray-900">{review.findings}</p>
                  <p className="mt-2 max-w-[300px] text-[12px] leading-4 text-gray-500">{review.store_note}</p>
                </div>
                {canInspect ? (
                  <div className="mt-4 flex flex-wrap justify-center gap-3">
                    <ActionButton endpoint="PUT /ui/v1/grns/{id}/records/{record_id}/inspection">
                      {review.accept_label}
                    </ActionButton>
                    <ActionButton
                      variant="primary"
                      endpoint="PUT /ui/v1/grns/{id}/records/{record_id}/inspection (fail lines → quality case)"
                    >
                      {review.raise_label}
                    </ActionButton>
                  </div>
                ) : null}
                <p className="mt-3 max-w-[260px] text-[11px] leading-4 text-gray-500">{review.raise_hint}</p>
              </CardBody>
            </Card>
          ) : null}

          <Card>
            <CardHeader title="How receiving closes" />
            <CardBody className="pb-10">
              <ul className="space-y-1.5">
                {data.closing_rules.map((rule) => (
                  <li key={rule} className="flex items-center gap-3 text-[12px] text-gray-700">
                    <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-brand-deep" />
                    {rule}
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
