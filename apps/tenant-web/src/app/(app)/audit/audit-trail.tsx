"use client";

import { Callout, Input, Pagination, Select, TBody, TD, TH, THead, TR, Table } from "@ims/ui";
import { CalendarDays } from "lucide-react";
import { useMemo, useState } from "react";

import type { AuditTrailPage } from "@/data/audit";
import { formatQty } from "@/lib/format";

import { ChangeText } from "./change-text";

/**
 * F24 Audit Trail. One screen drawn twice: for Type 1 (v1) the first filter is the user and the
 * note names "Admin"; for Type 2 it is the user type, the note names "Type 1" and a sources
 * footnote follows the table. Filters narrow the rows already on the page; with the real
 * endpoint they become query parameters.
 */
export function AuditTrail({ page, variant }: { page: AuditTrailPage; variant: "admin" | "manager" }) {
  const [person, setPerson] = useState("");
  const [module, setModule] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState("");

  const rows = useMemo(
    () =>
      page.rows.filter(
        (row) =>
          (person === "" || (variant === "admin" ? row.actor_name : row.actor_user_type) === person) &&
          (module === "" || row.module === module) &&
          (location === "" || row.location_code === location) &&
          (source === "" || row.source === source),
      ),
    [page.rows, variant, person, module, location, source],
  );

  return (
    <>
      <Callout tone="warning" dismissible>
        Entries can never be edited or deleted — including by {variant === "admin" ? "Admin" : "Type 1"}. Retention: lifetime
        (Q22, NFR-5).
      </Callout>

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="w-[180px] max-sm:w-full">
          {variant === "admin" ? (
            <Select aria-label="User" value={person} onChange={(event) => setPerson(event.target.value)}>
              <option value="">User · All</option>
              {page.filters.users.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          ) : (
            <Select aria-label="User type" value={person} onChange={(event) => setPerson(event.target.value)}>
              <option value="">User type · All</option>
              {page.filters.user_types.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          )}
        </div>
        <div className="w-[180px] max-sm:w-full">
          <Select aria-label="Module" value={module} onChange={(event) => setModule(event.target.value)}>
            <option value="">Module · All</option>
            {page.filters.modules.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[170px] max-sm:w-full">
          <Select aria-label="Location" value={location} onChange={(event) => setLocation(event.target.value)}>
            <option value="">Location · All</option>
            {page.filters.locations.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[150px] max-sm:w-full">
          <Select aria-label="Source" value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">Source · All</option>
            {page.filters.sources.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-[196px] max-sm:w-full">
          <Input
            readOnly
            aria-label="Date range"
            className="text-[12.5px]"
            placeholder={`${page.from_label} → today`}
            trailing={<CalendarDays className="size-3.5" strokeWidth={1.6} />}
          />
        </div>
      </div>

      <div className="mt-8 max-w-[1060px]">
        <Table>
          <THead>
            <TR>
              <TH>Timestamp</TH>
              <TH>User</TH>
              <TH>Action</TH>
              <TH>Entity</TH>
              <TH>Change</TH>
              <TH>Source</TH>
            </TR>
          </THead>
          <TBody zebra>
            {rows.map((row) => (
              <TR key={row.id}>
                <TD muted className="tabular">
                  <time dateTime={row.occurred_at}>{row.occurred_at_label}</time>
                </TD>
                <TD className="text-gray-700">
                  {row.actor_name} · {row.actor_tag}
                </TD>
                <TD className="text-gray-700">{row.action}</TD>
                <TD className="text-[12px] text-gray-700">{row.entity}</TD>
                <TD>
                  <ChangeText change={row.change} />
                </TD>
                <TD muted>{row.source}</TD>
              </TR>
            ))}
            {rows.length === 0 ? (
              <TR>
                <TD colSpan={6} muted align="center">
                  No entries match these filters.
                </TD>
              </TR>
            ) : null}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing {rows.length} of {formatQty(page.total)} entries · {page.sorted_by}
        </p>
        <Pagination pages={page.pages} current={page.page} />
      </div>

      {variant === "manager" ? (
        <div className="mt-6 rounded-lg border-[1.4px] border-gray-200 bg-gray-50 px-4 py-4 text-[12px] leading-[22px] text-gray-700">
          <p>
            Sources: Web · Mobile · API · Connector — external system actions are traced exactly like human ones (FR-15/16,
            Q26).
          </p>
          <p>Even rejected and failed attempts are recorded, marked as rejected — the trail stays honest (see F12).</p>
        </div>
      ) : null}
    </>
  );
}
