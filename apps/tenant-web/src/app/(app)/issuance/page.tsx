import {
  Card,
  CardHeader,
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
  Timeline,
  type Tone,
} from "@ims/ui";
import type { Metadata } from "next";

import { NoScreen } from "@/components/no-screen";
import { getLockLedger, getLocksOverview, type LockLedgerStateKind, type StockLockStateKind } from "@/data/issuance";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Locks & Reservations" };

const stockTone: Record<StockLockStateKind, Tone> = {
  locked_awaiting_pick: "blue",
  quarantined_validation_pending: "amber",
  lock_released_on_issue: "gray",
};

const ledgerTone: Record<LockLedgerStateKind, Tone> = {
  awaiting_pick: "blue",
  released: "gray",
};

/** Issuance. Manager workspace: F28 Locks & Reservations. No frame exists for the other workspaces. */
export default async function IssuancePage() {
  const { workspace } = await requireSession();
  if (workspace !== "manager") {
    return (
      <NoScreen title="Issuance">
        The wireframes draw the locks and reservations view for approvers only; there is no issuance screen for this
        user type.
      </NoScreen>
    );
  }

  const [overview, ledger] = await Promise.all([getLocksOverview(), getLockLedger()]);

  return (
    <div className="max-w-[1136px]">
      <PageHeader
        title="Locks & Reservations"
        subtitle="Locked units across inventory — created at first approval, released on issue (FB-09)"
      />

      <div className="-mt-1.5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active locks"
          value={overview.active_locks}
          hint={`${overview.awaiting_pick} awaiting pick · ${overview.released_today} released today`}
        />
        <StatCard
          label="Units locked"
          value={formatQty(overview.units_locked)}
          badge={
            <Pill tone="blue">
              {overview.units_locked_by_uom.map((part) => `${formatQty(part.qty)} ${part.uom}`).join(" + ")}
            </Pill>
          }
        />
        <StatCard label="Lock timeout" value={`${overview.lock_timeout_hours} h`} hint="auto-release on expiry" />
        <StatCard
          label="Over-issue attempts"
          value={overview.over_issue_attempts}
          badge={<Pill tone="green">blocked at scan (Q7)</Pill>}
        />
      </div>

      <SectionLabel className="mt-3.5">Stock by item &amp; location — locked and quarantined split out</SectionLabel>
      <div className="mt-2">
        <Table>
          <THead>
            <TR>
              <TH>Item</TH>
              <TH>Location</TH>
              <TH align="right">On hand</TH>
              <TH align="right">Locked</TH>
              <TH align="right">Quarantined</TH>
              <TH align="right">Free</TH>
              <TH>Lock ref</TH>
              <TH>State</TH>
            </TR>
          </THead>
          <TBody zebra>
            {overview.rows.map((row) => (
              <TR key={`${row.item_code}-${row.location_code}`} className="h-12">
                <TD strong>
                  {row.item_code} · {row.name}
                </TD>
                <TD>{row.location_code}</TD>
                <TD align="right" numeric>
                  {formatQty(row.on_hand)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(row.locked)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(row.quarantined)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(row.free)}
                </TD>
                <TD>{row.lock_ref}</TD>
                <TD>
                  <Pill tone={stockTone[row.state.kind]}>{row.state.label}</Pill>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <div className="mt-10 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card className="min-w-0">
          <CardHeader title="Active lock ledger" />
          <div className="px-4 pb-2 pt-6">
            <Table>
              <THead>
                <TR>
                  <TH>Ref</TH>
                  <TH>Item</TH>
                  <TH>Loc</TH>
                  <TH>Qty</TH>
                  <TH>Locked at / by</TH>
                  <TH>State</TH>
                </TR>
              </THead>
              <TBody zebra>
                {ledger.rows.map((row) => (
                  <TR key={row.request_ref}>
                    <TD className="whitespace-nowrap">{row.request_ref}</TD>
                    <TD muted>{row.item_code}</TD>
                    <TD className="whitespace-nowrap">{row.location_code}</TD>
                    <TD numeric className="whitespace-nowrap">
                      {formatQty(row.qty)} {row.uom}
                    </TD>
                    <TD muted className="whitespace-nowrap">
                      {row.locked_at_label} · {row.locked_by}
                    </TD>
                    <TD>
                      <Pill tone={ledgerTone[row.state.kind]}>{row.state.label}</Pill>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <p className="mt-1.5 text-[11px] text-gray-500">
              Every lock transition — create, release, expiry — is written to the immutable audit trail.
            </p>
          </div>
        </Card>

        <Card className="min-w-0">
          <CardHeader title="Lock lifecycle" />
          <div className="px-4 pb-5 pt-7">
            <Timeline
              entries={[
                {
                  title: "Created at first approval",
                  meta: `${ledger.lifecycle.created_by} · ${ledger.lifecycle.created_at_label}`,
                },
                { title: "Held against the request", meta: "counted · visible · not issuable" },
                { title: "Released on issue / reject / cancel / timeout", meta: "whichever happens first" },
              ]}
            />
          </div>
        </Card>
      </div>
      <p className="mt-1 text-[11px] text-gray-500">
        Quarantined units sit beside locked units on this view — both are counted, neither is issuable (FB-14).
      </p>
    </div>
  );
}
