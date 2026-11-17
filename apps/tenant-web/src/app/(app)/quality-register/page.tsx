import { hasPermission } from "@ims/api-client";
import { Card, CardBody, CardHeader, PageHeader, Pill } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getSupplierQualityRegister } from "@/data/quality-register";
import { formatMoney } from "@/lib/format";
import { requireSession } from "@/session/server";

import { formatDayTime } from "@/lib/dates";
import { QualityRegisterView } from "./quality-register-view";

export const metadata: Metadata = { title: "Supplier Quality Register" };

/** F33 Supplier Quality Register. */
export default async function QualityRegisterPage() {
  const [{ me }, register] = await Promise.all([requireSession(), getSupplierQualityRegister()]);
  const canExport = hasPermission(me, "reporting.export.run");
  const canDispose = hasPermission(me, "quality.case.dispose");
  const canDecideVendor = hasPermission(me, "purchasing.vendor.manage");

  return (
    <>
      <PageHeader
        title="Supplier Quality Register"
        subtitle="Poor-quality items per supplier, per period — attribution via purchase records to the vendor master (FB-16)"
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export for purchasing</ActionButton> : null}
            {canDispose ? (
              <ActionButton variant="primary" endpoint="POST /ui/v1/quality-cases/{id}/feedback-events">
                Publish feedback event
              </ActionButton>
            ) : null}
          </>
        }
      />

      <QualityRegisterView register={register} />

      <div className="mt-4 grid max-w-[1136px] grid-cols-[minmax(0,1fr)_412px] gap-4 max-lg:grid-cols-1">
        <Card className="min-w-0">
          <CardHeader title="External feedback events" />
          <CardBody className="pt-5">
            <ul className="space-y-3">
              {register.events.map((event) => (
                <li key={event.event_id} className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-baseline gap-x-6 text-[12px]">
                      <span className="font-bold text-gray-900">{event.event_id}</span>
                      <span className="text-[11px] text-gray-500">{formatDayTime(event.occurred_at)}</span>
                      <span className="text-[11px] text-gray-700 sm:ml-1">{event.supplier}</span>
                    </p>
                    <p className="mt-0.5 text-[10.5px] text-gray-500">{event.summary}</p>
                  </div>
                  {event.status === "published" ? (
                    <Pill small tone="red">
                      Published
                    </Pill>
                  ) : (
                    <Pill small tone="gray">
                      Acknowledged
                    </Pill>
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-gray-300 pt-3 text-[10.5px] text-gray-500">
              IMS records and reports supplier quality — procurement decisions stay in the external purchasing product.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Corrective actions & review" />
          <CardBody className="pt-5">
            <ul className="space-y-3">
              {register.corrective_actions.map((capa) => (
                <li key={capa.capa_id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[12px] font-bold text-gray-900">{capa.capa_id}</span>
                    {capa.status === "open" ? (
                      <Pill small tone="amber">
                        Open
                      </Pill>
                    ) : (
                      <Pill small tone="green">
                        Closed
                      </Pill>
                    )}
                  </div>
                  <p className="text-[10.5px] text-gray-500">{capa.summary}</p>
                </li>
              ))}
            </ul>
            {register.review ? (
              <div className="mt-4 border-t border-gray-300 pt-3">
                <p className="max-w-[250px] text-[11px] leading-4 text-gray-700">
                  {register.review.supplier_short} review — inputs: {register.review.poor_rate}% poor ·{" "}
                  {formatMoney(register.review.claims)} claims · CAPA open · feeds F37 / F38
                </p>
                {canDecideVendor ? (
                  <div className="mt-1 flex justify-end gap-3">
                    <ActionButton endpoint="POST /ui/v1/vendors/{id}/status-requests">Continue</ActionButton>
                    <ActionButton variant="danger" endpoint="POST /ui/v1/vendors/{id}/status-requests">
                      Suspend
                    </ActionButton>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
