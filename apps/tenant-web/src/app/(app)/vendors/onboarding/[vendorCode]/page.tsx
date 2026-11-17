import { hasPermission } from "@ims/api-client";
import { Card, CardBody, CardHeader, NoteBox, PageHeader, Pill, Stepper } from "@ims/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getOnboardingDraft } from "@/data/vendors";
import { requireSession } from "@/session/server";

import { CatalogueStep } from "./catalogue-step";

type Params = Promise<{ vendorCode: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { vendorCode } = await params;
  return { title: `Vendor Onboarding — ${vendorCode}` };
}

const stepNotes = [
  { title: "1 · Company & registration", text: "legal name · GSTIN · Udyam / MSME · city · payment terms · contact" },
  { title: "2 · Catalogue & MOQ", text: "vendor item codes linked to our SKUs · MOQ per item" },
  { title: "3 · Rate list", text: "rates per item · dated revisions · approval trail" },
  { title: "4 · Lead times", text: "vendor-stated supply time per item — feeds the reorder formula (FB-19)" },
  { title: "5 · Review & activate", text: "summary · checks · vendor becomes selectable as a purchase source" },
];

/** F39 Vendor Onboarding, step 2 (Catalogue & MOQ). */
export default async function VendorOnboardingPage({ params }: { params: Params }) {
  const { vendorCode } = await params;
  const [{ me }, draft] = await Promise.all([requireSession(), getOnboardingDraft(vendorCode)]);
  if (draft === null) notFound();

  const canManage = hasPermission(me, "purchasing.vendor.manage");

  return (
    <>
      <PageHeader
        title={`Vendor Onboarding — ${draft.vendor_code}`}
        subtitle="Step-wise capture ends in an active vendor, selectable as a purchase source (FB-25)"
        actions={
          canManage ? (
            <>
              <ActionButton endpoint="PATCH /ui/v1/vendors/{id}">Save draft</ActionButton>
              <ActionButton variant="primary" endpoint="PATCH /ui/v1/vendors/{id}">
                Continue to rate list
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="max-w-[1136px]">
        <Stepper steps={draft.steps} />

        <div className="mt-9 grid grid-cols-[minmax(0,1fr)_412px] gap-4 max-lg:grid-cols-1">
          <div className="min-w-0">
            <h2 className="px-4 text-[13.5px] font-semibold text-gray-900">
              Step 2 · Catalogue — one vendor, many items
            </h2>
            <CatalogueStep lines={draft.catalogue} />
            <NoteBox tone="gray" className="mt-7 flex flex-wrap items-start justify-between gap-3 bg-surface-alt px-4 py-3">
              <div className="min-w-0">
                <p className="text-[12.5px] font-semibold text-gray-900">
                  {draft.company} · {draft.city}
                </p>
                <p className="mt-0.5 text-[11px] text-gray-500">
                  GSTIN {draft.gstin} · Udyam {draft.udyam_msme} · captured in step 1
                </p>
              </div>
              <Pill tone="gray" className="mr-12 text-gray-500 max-sm:mr-0">
                DRAFT · {draft.vendor_code}
              </Pill>
            </NoteBox>
          </div>

          <Card className="self-start">
            <CardHeader title="What each step captures" />
            <CardBody className="pt-4">
              <ol className="space-y-4">
                {stepNotes.map((step) => (
                  <li key={step.title}>
                    <p className="text-[12px] font-semibold text-gray-900">{step.title}</p>
                    <p className="mt-0.5 max-w-[290px] text-[10.5px] leading-[14px] text-gray-500">{step.text}</p>
                  </li>
                ))}
              </ol>
              <p className="mt-6 max-w-[290px] border-t border-gray-300 pt-4 text-[11px] leading-4 text-gray-700">
                The wizard ends in an ACTIVE vendor — no separate activation step elsewhere (FB-25).
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
