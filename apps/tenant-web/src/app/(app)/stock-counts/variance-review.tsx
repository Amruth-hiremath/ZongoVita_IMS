import { hasPermission, type Me } from "@ims/api-client";
import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Input,
  PageHeader,
  Pill,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from "@ims/ui";

import { ActionButton } from "@/components/action-button";
import type { VarianceReview } from "@/data/stock-counts";
import { formatMoney, formatQty, formatSigned } from "@/lib/format";

/** "-1065" -> "−₹1,065" (true minus sign, as in the frame). */
function signedMoney(value: string): string {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) return formatMoney(value);
  return `${number < 0 ? "−" : "+"}${formatMoney(Math.abs(number))}`;
}

function varianceClass(value: string): string {
  const number = Number(value);
  if (number < 0) return "font-semibold text-red-700";
  if (number > 0) return "font-semibold text-green-700";
  return "text-[11.5px] text-gray-500";
}

/**
 * F17 Variance Review. Shared by /stock-counts (manager) and /stock-counts/[countNo]/variance.
 * Approving posts the adjustments shown in the preview; rejecting leaves stock as it is.
 */
export function VarianceReviewScreen({ me, review }: { me: Me; review: VarianceReview }) {
  const canApprove = hasPermission(me, "counts.adjustment.approve");
  const canExport = hasPermission(me, "reporting.export.run");

  return (
    <>
      <PageHeader
        className="mb-5"
        title={`Variance Review — ${review.count_no}`}
        subtitle={`${review.lines.length} variances from ${review.sku_count} SKUs · net impact ${signedMoney(review.net_impact)} · approval required to adjust`}
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export variance CSV</ActionButton> : null}
            {canApprove ? (
              <ActionButton
                variant="primary"
                endpoint={`POST /ui/v1/approval-tasks/{id}/approve (count adjustments, ${review.count_no})`}
              >
                Approve adjustments
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="max-w-[1100px]">
        <Table>
          <THead>
            <TR>
              <TH>SKU</TH>
              <TH>Item</TH>
              <TH align="center">Bin</TH>
              <TH align="right">System</TH>
              <TH align="right">Counted</TH>
              <TH align="center">Variance</TH>
              <TH align="right">Impact (₹)</TH>
              <TH>Reason</TH>
              <TH>Decision</TH>
            </TR>
          </THead>
          <TBody zebra>
            {review.lines.map((line) => (
              <TR key={line.item_code}>
                <TD>{line.item_code}</TD>
                <TD>{line.name}</TD>
                <TD align="center">{line.bin}</TD>
                <TD align="right" numeric>
                  {formatQty(line.system_qty)}
                </TD>
                <TD align="right" numeric>
                  {formatQty(line.counted_qty)}
                </TD>
                <TD align="center" numeric className={varianceClass(line.variance)}>
                  {formatSigned(line.variance)}
                </TD>
                <TD align="right" numeric strong>
                  {formatSigned(line.impact)}
                </TD>
                <TD>
                  {line.reason === null ? (
                    <span className="text-gray-500">—</span>
                  ) : (
                    <Input
                      compact
                      aria-label={`Reason for ${line.item_code}`}
                      defaultValue={line.reason}
                      className="w-[162px]"
                    />
                  )}
                </TD>
                <TD>
                  <Pill small tone={line.decision.kind === "match" ? "green" : "amber"}>
                    {line.decision.label}
                  </Pill>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
        <Card>
          <CardHeader title="Adjustment preview — what approval will do" className="pt-5" />
          <CardBody className="space-y-3 pt-3">
            {review.adjustments.map((adjustment) => (
              <div
                key={adjustment.item_code}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border-[1.4px] border-gray-200 bg-gray-50 px-4 py-3.5"
              >
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-gray-900">
                    {adjustment.item_code} @ {adjustment.location_code}
                  </p>
                  <p className="mt-1.5 text-[11px] text-gray-500">{adjustment.movement_note}</p>
                </div>
                <p className="tabular mr-1 text-[15px] font-semibold text-green-700">
                  {formatQty(adjustment.from_qty)} → {formatQty(adjustment.to_qty)} {adjustment.uom}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Approval policy (Q3)" />
          <CardBody className="pt-5">
            <div className="flex flex-col gap-2.5">
              {review.policy.rules.map((rule) => (
                <Checkbox key={rule.id} label={rule.label} defaultChecked={rule.enabled} className="text-[13px]" />
              ))}
            </div>
            <p className="mt-4 text-[11.5px] text-gray-500">Approvers:</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {review.policy.approvers.map((approver) => (
                <Pill key={approver} tone="blue">
                  {approver}
                </Pill>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      <Callout dismissible className="mt-6">
        Rejected adjustments do nothing — stock stays as-is and the count remains on record with its rejection reason.
      </Callout>
    </>
  );
}
