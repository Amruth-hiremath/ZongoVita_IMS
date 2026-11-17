"use client";

import { Pill, SectionLabel, StatCard, TBody, TD, TH, THead, TR, Table, Tabs, cn, type Tone } from "@ims/ui";
import { useState } from "react";

import type { QualityPeriod, SupplierQualityRegister, SupplierReviewStatus } from "@/data/quality-register";
import { formatQty } from "@/lib/format";

import { formatDayShort } from "@/lib/dates";

const periodLabel: Record<QualityPeriod, string> = { month: "Month", quarter: "Quarter", year: "Year" };
const periodColumn: Record<QualityPeriod, string> = { month: "Poor · M", quarter: "Poor · Q", year: "Poor · Y" };
const periods: QualityPeriod[] = ["month", "quarter", "year"];

const reviewLabel: Record<SupplierReviewStatus, string> = {
  active: "Active",
  under_review: "Under review",
  retired: "Retired",
};
const reviewTone: Record<SupplierReviewStatus, Tone> = { active: "green", under_review: "red", retired: "gray" };

/**
 * Period control, KPI row and supplier table of F33. The Month / Quarter / Year control changes
 * the period line, the poor-items tile and which Poor column is the current one (drawn red);
 * the counts for every period are already on each row.
 */
export function QualityRegisterView({ register }: { register: SupplierQualityRegister }) {
  const [period, setPeriod] = useState<QualityPeriod>("month");

  const poorItems = register.rows.reduce((total, row) => total + row.poor[period], 0);
  const poorVendors = register.rows.filter((row) => row.poor[period] > 0).length;
  const { summary } = register;

  return (
    <>
      <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
        <Tabs
          variant="segmented"
          value={period}
          onChange={(id) => setPeriod(id as QualityPeriod)}
          className="w-[252px] [&>button]:flex-1"
          items={periods.map((id) => ({ id, label: periodLabel[id] }))}
        />
        <p className="pt-0.5 text-[11px] text-gray-500">
          {register.periods[period].label} · counts roll up automatically from quality-hold lines
        </p>
      </div>

      <div className="mt-5 grid max-w-[1136px] grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <StatCard
          label={`Poor items · ${periodLabel[period]}`}
          value={formatQty(poorItems)}
          badge={
            <Pill tone="amber">
              {poorVendors} {poorVendors === 1 ? "vendor" : "vendors"}
            </Pill>
          }
        />
        <StatCard
          label="Events published"
          value={formatQty(summary.events_published)}
          hint="consumed by purchasing product"
        />
        <StatCard
          label="Vendors under review"
          value={formatQty(summary.vendors_under_review.length)}
          badge={
            summary.vendors_under_review.length > 0 ? (
              <Pill tone="red">{summary.vendors_under_review.join(" · ")}</Pill>
            ) : null
          }
        />
        <StatCard
          label="Corrective actions"
          value={`${summary.open_capa_count} open`}
          hint={
            summary.open_capa
              ? `${summary.open_capa.capa_id} · due ${formatDayShort(summary.open_capa.due_date)}`
              : undefined
          }
        />
      </div>

      <SectionLabel className="mt-4">Supplier-wise quality — current period with quarter and year rollups</SectionLabel>
      <div className="mt-1.5 max-w-[1136px]">
        <Table>
          <THead>
            <TR>
              <TH>Supplier</TH>
              <TH>City</TH>
              <TH align="center">POs recvd</TH>
              {periods.map((id) => (
                <TH key={id} align="center" className={cn(id === period && "text-gray-900")}>
                  {periodColumn[id]}
                </TH>
              ))}
              <TH align="center">Poor rate</TH>
              <TH align="right">Claims ₹</TH>
              <TH>Last event</TH>
              <TH>CAPA</TH>
              <TH>Review status</TH>
            </TR>
          </THead>
          <TBody zebra>
            {register.rows.map((row) => (
              <TR key={row.vendor_code}>
                <TD strong className="whitespace-nowrap">
                  {row.supplier}
                </TD>
                <TD muted>{row.city}</TD>
                <TD align="center" numeric>
                  {row.pos_received}
                </TD>
                {periods.map((id) => {
                  const value = row.poor[id];
                  return (
                    <TD
                      key={id}
                      align="center"
                      numeric
                      className={cn(
                        id === period
                          ? value > 0
                            ? "font-bold text-red-700"
                            : "text-gray-500"
                          : "font-bold text-gray-700",
                      )}
                    >
                      {value}
                    </TD>
                  );
                })}
                <TD align="center" numeric>
                  {row.poor_rate}%
                </TD>
                <TD align="right" numeric className={row.claims ? "whitespace-nowrap font-bold text-red-700" : "text-gray-500"}>
                  {row.claims ? `₹ ${formatQty(row.claims)}` : "—"}
                </TD>
                <TD muted className="whitespace-nowrap">
                  {row.last_event ? `${row.last_event.event_id} · ${formatDayShort(row.last_event.date)}` : "—"}
                </TD>
                <TD muted>{row.capa_id ?? "—"}</TD>
                <TD>
                  <Pill small tone={reviewTone[row.review_status]}>
                    {reviewLabel[row.review_status]}
                  </Pill>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </>
  );
}
