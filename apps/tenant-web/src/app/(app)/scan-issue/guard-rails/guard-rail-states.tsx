"use client";

import { Button, ButtonLink, Callout, Card, Input, PageHeader, SectionLabel, TBody, TD, TH, THead, TR, Table, cn } from "@ims/ui";
import { AlertTriangle, Check, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { ActionButton } from "@/components/action-button";
import type { IssueGuardRails } from "@/data/issues";
import { formatQty } from "@/lib/format";

const QTY_INPUT_ID = "guard-rail-issue-qty";

/**
 * F12. State A is drawn as it appears on F11 after "Post issue": the form dimmed behind the
 * "Cannot issue" dialog. The dialog sits in place (not as a page overlay) so the State B and C
 * panels stay visible; it can be closed and raised again by posting.
 */
export function GuardRailStates({ states }: { states: IssueGuardRails }) {
  const [open, setOpen] = useState(true);
  const [qty, setQty] = useState(states.blocked.requested);
  const b = states.blocked;

  const adjust = () => {
    setOpen(false);
    const input = document.getElementById(QTY_INPUT_ID);
    if (input instanceof HTMLInputElement) {
      input.focus();
      input.select();
    }
  };

  return (
    <div className="grid grid-cols-1 max-w-[1136px] gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
      <div className="min-w-0">
        <PageHeader
          title="Issue — Guard-rail States"
          subtitle="Two failure states of F11 that the wireframes must specify (Q7, Q20)"
        />

        <div className="relative">
          <Card className="px-4 pb-3 pt-2.5">
            <p className="text-[11px] text-gray-500">
              Post issue pressed with qty {formatQty(b.requested)} against {formatQty(b.free)} free…
            </p>
            <div className="mt-1.5 max-w-[600px]">
              <Table>
                <THead>
                  <TR>
                    <TH>SKU</TH>
                    <TH>Item</TH>
                    <TH align="right">Free</TH>
                    <TH align="center">Issue qty</TH>
                  </TR>
                </THead>
                <TBody>
                  <TR className="h-[52px]">
                    <TD>{b.item_code}</TD>
                    <TD>{b.name}</TD>
                    <TD align="right" numeric>
                      {formatQty(b.free)}
                    </TD>
                    <TD align="center">
                      <Input
                        id={QTY_INPUT_ID}
                        compact
                        inputMode="decimal"
                        aria-label={`Issue qty for ${b.item_code}`}
                        className="tabular mx-auto w-[72px]"
                        value={qty}
                        onChange={(event) => setQty(event.target.value)}
                      />
                    </TD>
                  </TR>
                </TBody>
              </Table>
            </div>
            {open ? null : (
              <div className="mt-3 flex justify-end">
                <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
                  Post issue
                </Button>
              </div>
            )}
          </Card>

          {open ? (
            <>
              {/* Dims the form behind the dialog, as the frame draws it. */}
              <div aria-hidden className="absolute inset-0 rounded-lg bg-gray-900/20" />
              <BlockedDialog states={states} onClose={() => setOpen(false)} onAdjust={adjust} />
            </>
          ) : null}
        </div>
      </div>

      <div className="min-w-0 space-y-6 lg:pt-0">
        <Card className="border-dashed px-4 pb-10 pt-5">
          <SectionLabel>State B · concurrent write (Q20)</SectionLabel>
          <StateBox tone="red" className="mt-3">
            <AlertTriangle aria-hidden className="size-4 shrink-0 text-red-700" strokeWidth={1.8} />
            <div>
              <p className="text-[12.5px] font-semibold text-gray-900">First write wins</p>
              <p className="text-[11.5px] text-gray-500">Rejected — stock changed while you were editing.</p>
            </div>
          </StateBox>
          <p className="mt-3 text-[11px] leading-[17px] text-gray-500">
            Another user issued {formatQty(states.concurrent.other_qty)} {states.concurrent.uom} at{" "}
            {states.concurrent.at_label}; this form&apos;s
            <br className="max-md:hidden" /> snapshot ({formatQty(states.concurrent.snapshot_free)} free) is stale.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <ActionButton variant="primary" className="w-[150px]" endpoint="POST /ui/v1/fulfilment-queue/{id}/complete">
              Refresh &amp; retry
            </ActionButton>
            <ButtonLink variant="danger" href="/fulfilment" className="w-[102px]">
              Discard
            </ButtonLink>
          </div>
          <p className="mt-4 text-[10.5px] leading-[15px] text-gray-400">
            The system serializes writes per SKU + location;
            <br className="max-md:hidden" /> the loser is always told explicitly — never silently.
          </p>
          <p className="mt-3 text-[10.5px] text-gray-400">No partial line posts: the whole issue is atomic.</p>
        </Card>

        <Card className="px-4 pb-5 pt-5 lg:mt-[104px]">
          <SectionLabel>State C · success (for contrast)</SectionLabel>
          <StateBox tone="green" className="mt-3">
            <Check aria-hidden className="size-4 shrink-0 text-green-700" strokeWidth={2} />
            <p className="text-[12.5px] text-gray-700">
              {states.success.issue_no} posted · stock deducted · webhooks fired.
            </p>
          </StateBox>
          <p className="mt-3 text-[11px] leading-[17px] text-gray-500">
            Receipt confirmation shows the new on-hand figure and
            <br className="max-md:hidden" /> the audit link — trust is built on visible math.
          </p>
          <p className="mt-7 text-[10.5px] leading-[15px] text-gray-400">
            The requester gets the acknowledgement prompt (F30);
            <br className="max-md:hidden" /> if stock fell below minimum, an alert + reorder suggestion fire.
          </p>
        </Card>
      </div>
    </div>
  );
}

function StateBox({ tone, className, children }: { tone: "red" | "green"; className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "flex min-h-16 items-center gap-3 rounded-md border-[1.4px] border-l-[5px] border-gray-300 bg-white px-4 py-2.5",
        tone === "red" ? "border-l-red-700" : "border-l-green-700",
        className,
      )}
    >
      {children}
    </div>
  );
}

function BlockedDialog({
  states,
  onClose,
  onAdjust,
}: {
  states: IssueGuardRails;
  onClose: () => void;
  onAdjust: () => void;
}) {
  const b = states.blocked;
  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="cannot-issue-title"
      className="relative z-10 mx-auto mt-0.5 max-w-[560px] rounded-lg border-[1.4px] border-gray-300 bg-white shadow-xl"
    >
      <div className="flex items-center justify-between gap-4 border-b border-gray-200 px-6 py-4">
        <h2 id="cannot-issue-title" className="text-[15px] font-semibold text-gray-900">
          Cannot issue {formatQty(b.requested)} {b.uom}
        </h2>
        <button type="button" aria-label="Close" className="text-gray-500 hover:text-gray-900" onClick={onClose}>
          <X className="size-4" strokeWidth={1.6} />
        </button>
      </div>
      <div className="px-6 pb-6 pt-4">
        <p className="max-w-[400px] text-[12px] leading-[18px] text-gray-500">
          <span className="text-[13px] text-gray-900">
            Only {formatQty(b.free)} {b.uom} of {b.item_code} are free at {b.location_code} — {formatQty(b.locked)} more
            are
          </span>{" "}
          locked for {b.lock_ref} and {formatQty(b.on_hand)} remain on hand. Negative stock is blocked by policy (Q7) —
          this transaction cannot be submitted.
        </p>
        <Callout tone="info" dismissible className="mt-4 max-w-[464px]">
          {formatQty(b.free)} free · {formatQty(b.locked)} locked for {b.lock_ref} · {formatQty(b.on_hand)} on hand
        </Callout>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button variant="primary" className="w-40" onClick={onAdjust}>
            Adjust quantity
          </Button>
          <ButtonLink href="/transfers/new" className="w-[181px]">
            Check other locations
          </ButtonLink>
          <Button variant="danger" className="w-[101px]" onClick={onClose}>
            Cancel
          </Button>
        </div>
        <p className="mt-4 text-[10.5px] leading-[15px] text-gray-400">
          “Check other locations” opens a transfer request (F14) instead —
          <br className="max-md:hidden" /> stock is never borrowed silently from another location.
        </p>
      </div>
    </div>
  );
}
