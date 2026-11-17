import { hasPermission, type Me } from "@ims/api-client";
import {
  Field,
  Input,
  Meter,
  NoteBox,
  PageHeader,
  Pagination,
  Pill,
  SectionLabel,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  Toggle,
  TR,
} from "@ims/ui";
import { ScanLine } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import type { CountSession } from "@/data/stock-counts";
import { formatQty } from "@/lib/format";


/**
 * F16 Stock Count sheet. Shared by /stock-counts (store) and /stock-counts/[countNo]. Counted
 * quantities are plain inputs; saving them needs the count-session endpoints. In a blind count
 * Core withholds the system quantity, so the column shows a mask.
 */
export function CountSheet({ me, session }: { me: Me; session: CountSession }) {
  const canCount = hasPermission(me, "counts.session.count");
  const id = session.count_no;
  const percent = session.total_lines === 0 ? 0 : (session.counted_lines / session.total_lines) * 100;

  return (
    <>
      <PageHeader
        className="mb-3"
        title={`Stock Count — ${session.count_no}`}
        actions={
          canCount ? (
            <>
              <ActionButton endpoint={`PUT /ui/v1/count-sessions/${id}/lines`}>Pause &amp; resume</ActionButton>
              <ActionButton variant="primary" endpoint={`POST /ui/v1/count-sessions/${id}/submit`}>
                Submit for review
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="flex flex-wrap items-end gap-x-5 gap-y-4">
        <Field label="Count type" htmlFor="count-type" className="w-[200px]">
          <Select id="count-type" defaultValue={session.count_type}>
            {session.count_types.map((type) => (
              <option key={type}>{type}</option>
            ))}
          </Select>
        </Field>
        <Field label="Location" htmlFor="count-location" className="w-[200px]">
          <Select id="count-location" defaultValue={session.location_id}>
            {session.locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Scope" htmlFor="count-scope" className="w-[180px]">
          <Input id="count-scope" defaultValue={session.scope} />
        </Field>
        <Toggle label="Blind count" defaultChecked={session.blind} className="mb-2 ml-2" />
        <Pill tone="amber" className="mb-3 ml-14 max-sm:ml-0">
          {session.counted_lines} of {session.total_lines} counted
        </Pill>
      </div>

      <div className="mt-5 flex max-w-[600px] flex-wrap items-center justify-between gap-3">
        <SectionLabel>Count sheet — enter physical qty only</SectionLabel>
        <ActionButton
          variant="link"
          endpoint="GET /ui/v1/scan/{code}"
          icon={<ScanLine aria-hidden className="size-3.5" strokeWidth={1.6} />}
          className="text-[11px] font-normal"
        >
          Scan shelf barcode → SKU row auto-opens
        </ActionButton>
      </div>

      <div className="mt-2 max-w-[1010px]">
        <Table>
          <THead>
            <TR>
              <TH>SKU</TH>
              <TH>Item</TH>
              <TH align="center">Bin</TH>
              <TH align="center">UoM</TH>
              <TH align="center">System qty</TH>
              <TH align="center">Counted qty</TH>
              <TH align="center">Variance</TH>
              <TH>Status</TH>
            </TR>
          </THead>
          <TBody zebra>
            {session.lines.map((line) => (
              <TR key={line.item_code}>
                <TD>{line.item_code}</TD>
                <TD>{line.name}</TD>
                <TD align="center">{line.bin}</TD>
                <TD align="center">{line.uom}</TD>
                <TD align="center" numeric className="text-gray-500">
                  {line.system_qty === null ? (
                    <span aria-label="Hidden in a blind count" className="tracking-[0.2em]">
                      •••
                    </span>
                  ) : (
                    formatQty(line.system_qty)
                  )}
                </TD>
                <TD align="center">
                  <Input
                    compact
                    inputMode="decimal"
                    aria-label={`Counted quantity of ${line.item_code}`}
                    defaultValue={line.counted_qty ?? ""}
                    className="mx-auto w-[84px] tabular"
                  />
                </TD>
                <TD align="center" muted>
                  auto
                </TD>
                <TD>
                  <Pill small tone={line.status.kind === "counted" ? "green" : "gray"} className={line.status.kind === "counted" ? undefined : "text-gray-500"}>
                    {line.status.label}
                  </Pill>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-gray-500">
          Showing {session.lines.length} of {formatQty(session.total_lines)} SKUs · filter: {session.filter_label}
        </p>
        <Pagination pages={session.pages} current={session.page} />
      </div>

      <NoteBox tone="gray" className="mt-5 px-4 py-4">
        <SectionLabel>Count progress</SectionLabel>
        <Meter
          percent={percent}
          label="Count progress"
          className="mt-2.5 h-3 max-w-[1064px] rounded-full border border-gray-300"
        />
        <p className="mt-3 text-[11.5px] text-gray-700">
          {session.counted_lines} of {session.total_lines} SKUs counted · pause &amp; resume keeps partial counts · submit
          requires 100%
        </p>
      </NoteBox>
    </>
  );
}
