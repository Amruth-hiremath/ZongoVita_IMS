"use client";

import { Card, CardBody, CardHeader, Chip, Pill, SectionLabel, Select, TBody, TD, TH, THead, TR, Table, Tabs } from "@ims/ui";
import { useMemo, useState } from "react";

import type { StoreActionKind, StoreAuditPage } from "@/data/audit";

import { ChangeText } from "./change-text";

type Kind = StoreActionKind | "all";

const segments: { id: Kind; label: string }[] = [
  { id: "all", label: "All actions" },
  { id: "issue", label: "Issues" },
  { id: "receipt", label: "Receipts" },
  { id: "count", label: "Counts" },
  { id: "transfer", label: "Transfers" },
];

const chips: { id: StoreActionKind; label: string }[] = [
  { id: "issue", label: "Issues" },
  { id: "receipt", label: "Receipts" },
  { id: "count", label: "Counts" },
  { id: "transfer", label: "Transfers" },
  { id: "approval", label: "Approvals" },
  { id: "quality", label: "Quality" },
];

/**
 * F50 Audit Trail for the store's own site. The segmented control and the chips in "Filter the
 * trail" share one selection, as the frame notes; the footer count follows it.
 */
export function StoreAudit({ page }: { page: StoreAuditPage }) {
  const [kind, setKind] = useState<Kind>("all");
  const [month, setMonth] = useState(page.months[0]?.value ?? "");

  const rows = useMemo(
    () =>
      page.rows.filter(
        (row) => (kind === "all" || row.action_kind === kind) && (month === "" || row.occurred_at.startsWith(month)),
      ),
    [page.rows, kind, month],
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs
            variant="segmented"
            items={segments.map((segment) => ({ id: segment.id, label: segment.label }))}
            value={kind}
            onChange={(id) => setKind(id as Kind)}
            className="max-w-full overflow-x-auto"
          />
          <div className="w-[120px]">
            <Select aria-label="Month" value={month} onChange={(event) => setMonth(event.target.value)}>
              {page.months.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <SectionLabel className="mt-3 mb-2">Lifetime log — every entry immutable (Q22)</SectionLabel>
        <Table>
          <THead>
            <TR>
              <TH>Time</TH>
              <TH>User · type</TH>
              <TH>Action</TH>
              <TH>Entity</TH>
              <TH>Change</TH>
              <TH>Source</TH>
            </TR>
          </THead>
          <TBody zebra className="[&_td]:text-[11.5px] [&_td]:text-gray-600">
            {rows.map((row) => (
              <TR key={row.id}>
                <TD className="tabular whitespace-nowrap">
                  <time dateTime={row.occurred_at}>{row.occurred_at_label}</time>
                </TD>
                <TD className="whitespace-nowrap">
                  {row.actor_name} · {row.actor_tag}
                </TD>
                <TD>{row.action}</TD>
                <TD className="whitespace-nowrap">{row.entity}</TD>
                <TD className="whitespace-nowrap">
                  <ChangeText change={row.change} />
                </TD>
                <TD>{row.source}</TD>
              </TR>
            ))}
            {rows.length === 0 ? (
              <TR>
                <TD colSpan={6} align="center">
                  No entries of this kind in the selected month.
                </TD>
              </TR>
            ) : null}
          </TBody>
        </Table>
        <p className="mt-2 text-[11px] text-gray-500">
          {rows.length} {rows.length === 1 ? "entry" : "entries"} · {page.period_label} · nothing here can be edited or
          deleted — not even by Type 1.
        </p>

        <Card className="mt-6">
          <CardHeader title="What writes here" />
          <CardBody className="pb-6">
            <ul className="space-y-2.5 text-[11.5px] text-gray-700">
              <li className="flex items-center gap-3">
                <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-blue-600" />
                Every scan-issue and every blocked over-issue attempt (Q7 · Q20)
              </li>
              <li className="flex items-center gap-3">
                <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-blue-600" />
                Every GRN posting with its inspection outcome (F10 · FB-26)
              </li>
              <li className="flex items-center gap-3">
                <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-blue-600" />
                Every count submitted and every quarantine routing (F16 · F32)
              </li>
            </ul>
          </CardBody>
        </Card>
      </div>

      <div className="flex min-w-0 flex-col gap-6 lg:mt-[68px]">
        <Card>
          <CardHeader title="Immutable by design" />
          <CardBody className="text-[11.5px] leading-4">
            <p className="max-w-[240px] text-gray-700">
              Entries can never be edited or deleted — the trail is the system of record for the item&apos;s whole life
              (Q22).
            </p>
            <p className="mt-4 text-gray-500">Exports carry a hash; gaps are impossible.</p>
            <Pill tone="dark" className="mt-3">
              WRITE ONCE · NO EDITS
            </Pill>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Scope — your location" />
          <CardBody className="pb-6 text-[11.5px] leading-4">
            <p className="max-w-[240px] text-gray-700">
              Type 3 sees the trail for {page.site_code} only (privilege matrix · FB-23). The tenant-wide trail belongs to
              Type 1 (F24).
            </p>
            <p className="mt-4 max-w-[240px] text-gray-500">
              Need wider scope? Ask Type 1 to extend your role in the privilege matrix (F36).
            </p>
          </CardBody>
        </Card>

        <Card id="filter-the-trail" className="scroll-mt-24">
          <CardHeader title="Filter the trail" />
          <CardBody>
            <div className="flex max-w-[240px] flex-wrap gap-x-2 gap-y-2.5 pt-2">
              {chips.map((chip) => (
                <Chip
                  key={chip.id}
                  selected={kind === chip.id}
                  onClick={() => setKind(kind === chip.id ? "all" : chip.id)}
                  className={kind === chip.id ? undefined : "text-gray-500"}
                >
                  {chip.label}
                </Chip>
              ))}
            </div>
            <p className="mt-3 max-w-[240px] text-[11px] leading-4 text-gray-500">
              Chips drive the segmented control above; the count updates live per action kind.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
