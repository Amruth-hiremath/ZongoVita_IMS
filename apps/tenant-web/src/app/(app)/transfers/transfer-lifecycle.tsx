import { hasPermission, type Me } from "@ims/api-client";
import {
  ButtonLink,
  Callout,
  Card,
  CardHeader,
  CardBody,
  Input,
  KeyValue,
  PageHeader,
  Pill,
  Stepper,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Timeline,
  type Tone,
} from "@ims/ui";
import { ArrowRight } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import type { StageActionState, TransferDetail } from "@/data/transfers";
import { formatQty } from "@/lib/format";

const stageTone: Record<StageActionState, { tone: Tone; label: string }> = {
  done: { tone: "green", label: "Done" },
  current: { tone: "blue", label: "Current" },
  if_needed: { tone: "amber", label: "If needed" },
};

/**
 * F15 Transfer lifecycle. Shared by /transfers (manager) and /transfers/[transferNo].
 * Confirm receipt is shown only to people who may receive transfers (LLD section 15): in the
 * frame the receipt belongs to Type 3 at the destination.
 */
export function TransferLifecycle({ me, transfer }: { me: Me; transfer: TransferDetail }) {
  const canReceive = hasPermission(me, "transfers.transfer.receive");
  const route = `${transfer.from_location_code} → ${transfer.to_location_code}`;

  return (
    <>
      <PageHeader
        className="mb-0"
        title={`${transfer.transfer_no} — ${route}`}
        subtitle={`Requested by ${transfer.requested_by.name} · approved by ${transfer.approved_by.name} · dispatched ${transfer.dispatched_at_display}`}
        actions={
          <>
            <ActionButton endpoint={`GET /ui/v1/transfers/${transfer.transfer_no} (delivery challan)`}>
              Print challan
            </ActionButton>
            {canReceive ? (
              <ActionButton variant="primary" endpoint={`POST /ui/v1/transfers/${transfer.transfer_no}/receive-scans`}>
                Confirm receipt
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="mt-7 max-w-[1000px] lg:ml-10">
        <Stepper steps={transfer.steps.map((step) => ({ label: step.label, meta: step.meta, state: step.state }))} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Transfer details" />
          <CardBody className="pt-3">
            <dl>
              <KeyValue label="Ref">{transfer.transfer_no}</KeyValue>
              <KeyValue label="Route">{route}</KeyValue>
              <KeyValue label="Raised by">
                {transfer.requested_by.name} · {transfer.requested_by.type_label}
              </KeyValue>
              <KeyValue label="Approved by">
                {transfer.approved_by.name} · {transfer.approved_by.type_label}
              </KeyValue>
              <KeyValue label="Priority">
                {transfer.priority} · {transfer.reason}
              </KeyValue>
            </dl>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Items — sent vs received" />
          <CardBody className="pt-6">
            <Table>
              <THead>
                <TR>
                  <TH>SKU</TH>
                  <TH>Item</TH>
                  <TH align="right">Sent</TH>
                  <TH align="center">Received</TH>
                  <TH align="center">Shortage</TH>
                  <TH align="right">Value (₹)</TH>
                </TR>
              </THead>
              <TBody zebra>
                {transfer.lines.map((line) => (
                  <TR key={line.item_code}>
                    <TD>{line.item_code}</TD>
                    <TD>{line.name}</TD>
                    <TD align="right" numeric>
                      {formatQty(line.sent_qty)}
                    </TD>
                    <TD align="center">
                      <Input
                        compact
                        inputMode="decimal"
                        aria-label={`Received quantity of ${line.item_code}`}
                        defaultValue={line.received_qty ?? ""}
                        className="mx-auto w-[58px] tabular"
                      />
                    </TD>
                    <TD align="center" muted>
                      auto
                    </TD>
                    <TD align="right" numeric>
                      {formatQty(line.value)}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Audit trail"
            action={
              <ButtonLink href="/audit" variant="link" className="text-[12px]">
                Full trail <ArrowRight aria-hidden className="size-3" strokeWidth={1.8} />
              </ButtonLink>
            }
          />
          <CardBody className="pt-2">
            <Timeline entries={transfer.audit.map((entry) => ({ title: entry.title, meta: entry.meta }))} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Stage actions (type-aware)" />
          <CardBody className="space-y-2 pt-2">
            {transfer.stage_actions.map((action) => (
              <div
                key={action.label}
                className="grid min-h-11 grid-cols-[minmax(0,184px)_minmax(0,1fr)_auto] items-center gap-3 rounded-md border-[1.4px] border-gray-200 bg-gray-50 px-4 py-2 max-sm:grid-cols-[minmax(0,1fr)_auto]"
              >
                <span className="text-[13px] font-semibold text-gray-900">{action.label}</span>
                <span className="text-[11.5px] text-gray-500 max-sm:order-3 max-sm:col-span-2">{action.actor}</span>
                <Pill small tone={stageTone[action.state].tone} className="mr-6 max-sm:mr-0">
                  {stageTone[action.state].label}
                </Pill>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <Callout dismissible className="mt-8">
        Step chain is configurable per enterprise (Q10) — e.g. auto-approve below ₹5,000, or add a QA check step.
      </Callout>
    </>
  );
}
