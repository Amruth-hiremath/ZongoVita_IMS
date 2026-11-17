"use client";

import { Chip, Input, Pagination, Pill, Select, TBody, TD, TH, THead, TR, Table } from "@ims/ui";
import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { PurchaseRecordListPage, PurchaseRecordRow, PurchaseRecordStatus } from "@/data/purchase-records";
import { formatQty } from "@/lib/format";

import { formatDay, formatDayShort } from "@/lib/dates";
import { inspectionLabel, recordStatusLabel, recordStatusTone } from "./record-status";

const statusOptions: PurchaseRecordStatus[] = ["awaiting_inward", "inwarded", "exception"];

function inwardCell(row: PurchaseRecordRow): string {
  if (row.inward_date) return formatDay(row.inward_date);
  if (row.inward_due_date) return `due ${formatDayShort(row.inward_due_date)}`;
  return "—";
}

/**
 * Filter bar, table and pager of F40. Search, status, department and the "Awaiting inward" chip
 * narrow the rows on the page; "Vendor" needs the vendor on each row, so it becomes a query
 * parameter once GET /ui/v1/purchase-records is connected.
 */
export function PurchaseRecordsList({ page }: { page: PurchaseRecordListPage }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<PurchaseRecordStatus | "">("");
  const [department, setDepartment] = useState("");
  const [awaitingOnly, setAwaitingOnly] = useState(false);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return page.rows.filter(
      (row) =>
        (needle === "" ||
          row.po_number.toLowerCase().includes(needle) ||
          row.item_code.toLowerCase().includes(needle) ||
          row.department.toLowerCase().includes(needle)) &&
        (status === "" || row.status === status) &&
        (department === "" || row.department === department) &&
        (!awaitingOnly || row.status === "awaiting_inward"),
    );
  }, [page.rows, query, status, department, awaitingOnly]);

  return (
    <>
      <div className="mt-5 flex max-w-[1136px] flex-wrap items-center gap-x-4 gap-y-3">
        <div className="w-[300px] max-sm:w-full">
          <Input
            type="search"
            aria-label="Search purchase records"
            placeholder="Search PO no, item, department…"
            leading={<Search className="size-3.5" strokeWidth={1.6} />}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="w-[170px]">
          <Select
            aria-label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value as PurchaseRecordStatus | "")}
          >
            <option value="">Status · All</option>
            {statusOptions.map((value) => (
              <option key={value} value={value}>
                {recordStatusLabel[value]}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[170px]">
          <Select aria-label="Vendor" defaultValue="">
            <option value="">Vendor · All</option>
            {page.filters.vendors.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[180px]">
          <Select aria-label="Department" value={department} onChange={(event) => setDepartment(event.target.value)}>
            <option value="">Department · All</option>
            {page.filters.departments.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <Chip tone="amber" selected={awaitingOnly} onClick={() => setAwaitingOnly((value) => !value)}>
          Awaiting inward
        </Chip>
      </div>

      <div className="mt-6 max-w-[1036px]">
        <Table>
          <THead>
            <TR>
              <TH>PO no</TH>
              <TH>Items</TH>
              <TH>Dept</TH>
              <TH>Purchased by</TH>
              <TH>Approved by</TH>
              <TH>Inward</TH>
              <TH>Inspection</TH>
              <TH>Expected use</TH>
              <TH>Status</TH>
            </TR>
          </THead>
          <TBody zebra>
            {rows.map((row) => (
              <TR key={row.po_number}>
                <TD>
                  <Link href={`/purchase-records/${row.po_number}`} className="hover:text-blue-600">
                    {row.po_number}
                  </Link>
                </TD>
                <TD muted>
                  <Link href={`/purchase-records/${row.po_number}`} className="hover:text-blue-600">
                    {row.item_code} ×{formatQty(row.quantity)} {row.uom}
                  </Link>
                </TD>
                <TD muted>{row.department}</TD>
                <TD muted>{row.purchased_by}</TD>
                <TD muted>{row.approved_by}</TD>
                <TD muted>{inwardCell(row)}</TD>
                <TD muted>{row.inspection ? inspectionLabel[row.inspection] : "—"}</TD>
                <TD muted>{formatDay(row.expected_use_date)}</TD>
                <TD>
                  <Pill small tone={recordStatusTone[row.status]}>
                    {recordStatusLabel[row.status]}
                  </Pill>
                </TD>
              </TR>
            ))}
            {rows.length === 0 ? (
              <TR>
                <TD colSpan={9} muted align="center">
                  No purchase records match these filters.
                </TD>
              </TR>
            ) : null}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex max-w-[1136px] flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing 1–{rows.length} of {formatQty(page.total)} records this {page.summary.period_label} · sorted by{" "}
          {page.sorted_by}
        </p>
        <Pagination pages={page.pages} current={page.page} />
      </div>
    </>
  );
}
