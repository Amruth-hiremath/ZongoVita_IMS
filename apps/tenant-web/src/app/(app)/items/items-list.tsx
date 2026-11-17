"use client";

import { Chip, Input, Pagination, Pill, Select, TBody, TD, TH, THead, TR, Table, type Tone } from "@ims/ui";
import { Image as ImageIcon, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { ItemListPage, ItemListRow, StockStatusKind } from "@/data/items";
import { formatMoney, formatQty } from "@/lib/format";

const statusTone: Record<StockStatusKind, Tone> = {
  in_stock: "green",
  below_min: "red",
  batch_expiring: "amber",
  expiry_window: "amber",
  dead: "dark",
};

type Quick = "all" | "below_min" | "expiring" | "dead";

const quickFilters: { id: Quick; label: string; tone: Tone }[] = [
  { id: "all", label: "All", tone: "gray" },
  { id: "below_min", label: "Below min", tone: "red" },
  { id: "expiring", label: "Expiring", tone: "amber" },
  { id: "dead", label: "Dead", tone: "gray" },
];

function matchesQuick(row: ItemListRow, quick: Quick): boolean {
  switch (quick) {
    case "all":
      return true;
    case "below_min":
      return row.stock_status.kind === "below_min";
    case "expiring":
      return row.stock_status.kind === "batch_expiring" || row.stock_status.kind === "expiry_window";
    case "dead":
      return row.stock_status.kind === "dead";
  }
}

/**
 * Filter bar, table and pager of F07. Filters narrow the rows already on the page; with the
 * real endpoint they become query parameters and the server returns the matching page.
 */
export function ItemsList({ page }: { page: ItemListPage }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [quick, setQuick] = useState<Quick>("all");

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return page.rows.filter(
      (row) =>
        (needle === "" || row.item_code.toLowerCase().includes(needle) || row.name.toLowerCase().includes(needle)) &&
        (category === "" || row.category === category) &&
        matchesQuick(row, quick),
    );
  }, [page.rows, query, category, quick]);

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="w-[300px] max-sm:w-full">
          <Input
            type="search"
            aria-label="Search items"
            placeholder="Search SKU, name, barcode…"
            leading={<Search className="size-3.5" strokeWidth={1.6} />}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="w-[150px]">
          <Select aria-label="Category" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">Category · All</option>
            {page.filters.categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[170px]">
          <Select aria-label="Location" defaultValue="">
            <option value="">Location · All</option>
            {page.filters.locations.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[140px]">
          <Select aria-label="Status" defaultValue="">
            <option value="">Status · All</option>
            {page.filters.statuses.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-5 flex items-center gap-2 max-lg:ml-0">
          {quickFilters.map((filter) => (
            <Chip key={filter.id} tone={filter.tone} selected={quick === filter.id} onClick={() => setQuick(filter.id)}>
              {filter.label}
            </Chip>
          ))}
        </div>
      </div>

      <div className="mt-6 max-w-[1096px]">
        <Table className="table-fixed">
          <colgroup>
            <col className="w-[108px]" />
            <col />
            <col className="w-[100px]" />
            <col className="w-[52px]" />
            <col className="w-[84px]" />
            <col className="w-[76px]" />
            <col className="w-[68px]" />
            <col className="w-[60px]" />
            <col className="w-[48px]" />
            <col className="w-[132px]" />
            <col className="w-[80px]" />
          </colgroup>
          <THead>
            <TR>
              <TH>SKU</TH>
              <TH>Item</TH>
              <TH>Category</TH>
              <TH align="center">UoM</TH>
              <TH align="right">Cost (₹)</TH>
              <TH align="right">On hand</TH>
              <TH align="right">Locked</TH>
              <TH align="right">Quar.</TH>
              <TH align="center">Locs</TH>
              <TH>Status</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {rows.map((row) => (
              <TR key={row.item_code}>
                <TD>{row.item_code}</TD>
                <TD>
                  <Link href={`/items/${row.item_code}`} className="flex items-center gap-2.5 hover:text-blue-600">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded border-[1.1px] border-gray-300 bg-gray-50 text-gray-500">
                      <ImageIcon aria-hidden className="size-3" strokeWidth={1.5} />
                    </span>
                    {row.name}
                  </Link>
                </TD>
                <TD muted>{row.category}</TD>
                <TD align="center">{row.uom}</TD>
                <TD align="right" numeric>
                  {formatMoney(row.cost)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(row.on_hand)}
                </TD>
                <TD align="right" numeric muted>
                  {formatQty(row.locked)}
                </TD>
                <TD align="right" numeric muted>
                  {formatQty(row.quarantined)}
                </TD>
                <TD align="center" numeric>
                  {row.location_count}
                </TD>
                <TD>
                  <Pill tone={statusTone[row.stock_status.kind]}>{row.stock_status.label}</Pill>
                </TD>
                <TD align="right" muted>
                  <Link href={`/items/${row.item_code}`} className="hover:text-gray-700">
                    Edit · ▾
                  </Link>
                </TD>
              </TR>
            ))}
            {rows.length === 0 ? (
              <TR>
                <TD colSpan={11} muted align="center">
                  No items match these filters.
                </TD>
              </TR>
            ) : null}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex max-w-[1136px] flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing 1–{rows.length} of {formatQty(page.total)} items · sorted by {page.sorted_by}
        </p>
        <Pagination pages={page.pages} current={page.page} />
      </div>
    </>
  );
}
