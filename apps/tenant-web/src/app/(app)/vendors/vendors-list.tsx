"use client";

import { Chip, Input, Pagination, Pill, Select, TBody, TD, TH, THead, TR, Table, type Tone } from "@ims/ui";
import { Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { VendorListPage, VendorStatus } from "@/data/vendors";
import { formatQty } from "@/lib/format";

import { vendorStatusLabel, vendorStatusTone } from "./vendor-status";

type Quick = "all" | "active" | "under_review" | "retired";

const quickFilters: { id: Quick; label: string; tone: Tone }[] = [
  { id: "all", label: "All", tone: "gray" },
  { id: "active", label: "Active", tone: "green" },
  { id: "under_review", label: "Under review", tone: "red" },
  { id: "retired", label: "Retired", tone: "gray" },
];

const statusOptions: VendorStatus[] = ["active", "under_review", "retired"];

/**
 * Filter bar, table and pager of F37. Search, status and the chips narrow the rows on the page;
 * "Supplies item" needs the vendor catalogue behind each row, so it becomes a query parameter
 * once GET /ui/v1/vendors is connected.
 */
export function VendorsList({ page }: { page: VendorListPage }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<VendorStatus | "">("");
  const [quick, setQuick] = useState<Quick>("all");

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return page.rows.filter(
      (row) =>
        (needle === "" ||
          row.company.toLowerCase().includes(needle) ||
          row.gstin.toLowerCase().includes(needle) ||
          row.vendor_code.toLowerCase().includes(needle)) &&
        (status === "" || row.status === status) &&
        (quick === "all" || row.status === quick),
    );
  }, [page.rows, query, status, quick]);

  return (
    <>
      <div className="mt-5 flex max-w-[1136px] flex-wrap items-center gap-x-4 gap-y-3">
        <div className="w-[300px] max-sm:w-full">
          <Input
            type="search"
            aria-label="Search vendors"
            placeholder="Search company, GSTIN, item…"
            leading={<Search className="size-3.5" strokeWidth={1.6} />}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="w-[150px]">
          <Select
            aria-label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value as VendorStatus | "")}
          >
            <option value="">Status · All</option>
            {statusOptions.map((value) => (
              <option key={value} value={value}>
                {vendorStatusLabel[value]}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[170px]">
          <Select aria-label="Supplies item" defaultValue="">
            <option value="">Supplies item · All</option>
            {page.filters.supplied_items.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2 max-lg:ml-0">
          {quickFilters.map((filter) => (
            <Chip key={filter.id} tone={filter.tone} selected={quick === filter.id} onClick={() => setQuick(filter.id)}>
              {filter.label}
            </Chip>
          ))}
        </div>
      </div>

      <div className="mt-6 max-w-[1036px]">
        <Table>
          <THead>
            <TR>
              <TH>Vendor</TH>
              <TH>Company</TH>
              <TH>City</TH>
              <TH>GSTIN</TH>
              <TH align="center">Items</TH>
              <TH align="right">MOQ from</TH>
              <TH>Lead</TH>
              <TH align="right">Poor · M</TH>
              <TH>Status</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {rows.map((row) => {
              const href = `/vendors/${row.vendor_code}`;
              return (
                <TR key={row.vendor_code}>
                  <TD>
                    <Link href={href} className="hover:text-blue-600">
                      {row.vendor_code}
                    </Link>
                  </TD>
                  <TD>
                    <Link href={href} className="hover:text-blue-600">
                      {row.company}
                    </Link>
                  </TD>
                  <TD muted>{row.city}</TD>
                  <TD>{row.gstin}</TD>
                  <TD align="center" numeric>
                    {row.item_count}
                  </TD>
                  <TD align="right" numeric>
                    {formatQty(row.moq_from)}
                  </TD>
                  <TD muted>
                    {row.lead_days_min}–{row.lead_days_max} d
                  </TD>
                  <TD
                    align="right"
                    numeric
                    className={row.poor_month > 0 ? "font-bold text-red-700" : "text-gray-500"}
                  >
                    {row.poor_month}
                  </TD>
                  <TD>
                    <Pill tone={vendorStatusTone[row.status]}>{vendorStatusLabel[row.status]}</Pill>
                  </TD>
                  <TD align="right" muted>
                    <Link href={href} className="whitespace-nowrap hover:text-gray-700">
                      Open · ▾
                    </Link>
                  </TD>
                </TR>
              );
            })}
            {rows.length === 0 ? (
              <TR>
                <TD colSpan={10} muted align="center">
                  No vendors match these filters.
                </TD>
              </TR>
            ) : null}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex max-w-[1136px] flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing 1–{rows.length} of {formatQty(page.total)} vendors · sorted by {page.sorted_by}
        </p>
        <Pagination pages={page.pages} current={page.page} />
      </div>
    </>
  );
}
