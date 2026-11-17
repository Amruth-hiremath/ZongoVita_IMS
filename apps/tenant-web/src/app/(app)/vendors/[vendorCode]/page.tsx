import { hasPermission } from "@ims/api-client";
import {
  Card,
  CardBody,
  CardHeader,
  KeyValue,
  NoteBox,
  PageHeader,
  Pill,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Tabs,
} from "@ims/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { getVendor, type VendorDetail } from "@/data/vendors";
import { formatMoney, formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { formatDay, formatMonth } from "@/lib/dates";
import { vendorStatusLabel, vendorStatusTone } from "../vendor-status";

type Params = Promise<{ vendorCode: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { vendorCode } = await params;
  return { title: `Vendor ${vendorCode}` };
}

/** F38 Vendor detail. */
export default async function VendorDetailPage({ params }: { params: Params }) {
  const { vendorCode } = await params;
  const [{ me }, vendor] = await Promise.all([requireSession(), getVendor(vendorCode)]);
  if (vendor === null) notFound();

  const canManage = hasPermission(me, "purchasing.vendor.manage");
  const canPurchase = hasPermission(me, "purchasing.record.manage");

  const catalogue = <CatalogueTable vendor={vendor} canEdit={canManage} />;
  const profile = <ProfileCard vendor={vendor} />;
  const rates = <RateRevisionsCard vendor={vendor} />;
  const leadTimes = <LeadTimesCard vendor={vendor} />;

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "Vendors", href: "/vendors" }, { label: vendor.vendor_code }]}
        title={vendor.legal_name}
        subtitle={`${vendor.city} · vendor since ${formatMonth(vendor.vendor_since)} · ${formatQty(vendor.purchase_record_count)} purchase records · ${formatQty(vendor.units_supplied)} units supplied`}
        badges={
          <>
            <Pill tone={vendorStatusTone[vendor.status]}>{vendorStatusLabel[vendor.status]}</Pill>
            <Pill tone="blue">
              Rate list {vendor.current_rate_list.revision} · {formatDay(vendor.current_rate_list.effective_date)}
            </Pill>
            <Pill tone="gray">Quality {vendor.poor_month} poor this month</Pill>
          </>
        }
        actions={
          <>
            {canManage ? (
              <ActionButton endpoint="POST /ui/v1/vendors/{id}/status-requests">Suspend</ActionButton>
            ) : null}
            {canPurchase ? (
              <ActionButton variant="soft" endpoint="POST /ui/v1/purchase-records">
                New purchase record
              </ActionButton>
            ) : null}
            {canManage ? (
              <ActionButton variant="primary" endpoint="PATCH /ui/v1/vendors/{id}">
                Edit vendor
              </ActionButton>
            ) : null}
          </>
        }
      />

      <div className="max-w-[1136px]">
        <Tabs
          className="max-lg:gap-6 max-lg:overflow-x-auto"
          panelClassName="mt-7"
          items={[
            {
              id: "catalogue",
              label: "Catalogue & MOQ",
              content: (
                <div className="grid grid-cols-[minmax(0,1fr)_412px] gap-x-4 gap-y-5 max-lg:grid-cols-1">
                  {catalogue}
                  {profile}
                  {rates}
                  {leadTimes}
                </div>
              ),
            },
            { id: "rates", label: "Rate list", content: <div className="max-w-[708px]">{rates}</div> },
            { id: "lead-times", label: "Lead times", content: <div className="max-w-[412px]">{leadTimes}</div> },
            { id: "profile", label: "Profile & registration", content: <div className="max-w-[412px]">{profile}</div> },
            { id: "quality", label: "Quality history", content: <QualityTable vendor={vendor} /> },
          ]}
        />
      </div>
    </>
  );
}

function CatalogueTable({ vendor, canEdit }: { vendor: VendorDetail; canEdit: boolean }) {
  return (
    <div className="min-w-0">
      <Table>
        <THead>
          <TR>
            <TH>Vendor code</TH>
            <TH>Our SKU</TH>
            <TH>Item</TH>
            <TH align="center">MOQ</TH>
            <TH align="right">Rate (₹)</TH>
            <TH align="center">Lead</TH>
            <TH align="center">Poor · M/Q/Y</TH>
            <TH>
              <span className="sr-only">Actions</span>
            </TH>
          </TR>
        </THead>
        <TBody zebra>
          {vendor.catalogue.map((line) => (
            <TR key={line.vendor_item_code}>
              <TD>{line.vendor_item_code}</TD>
              <TD>{line.item_code}</TD>
              <TD>{line.item_name}</TD>
              <TD align="center" numeric>
                {formatQty(line.moq)}
              </TD>
              <TD align="right" numeric>
                {formatMoney(line.rate)}
              </TD>
              <TD align="center" muted>
                {line.lead_time_days} d
              </TD>
              <TD align="center" muted numeric>
                {line.poor.month} / {line.poor.quarter} / {line.poor.year}
              </TD>
              <TD align="right">
                {canEdit ? (
                  <ActionButton
                    variant="link"
                    endpoint="POST /ui/v1/vendors/{id}/rates"
                    className="text-[11.5px] font-normal text-gray-500"
                  >
                    Edit
                  </ActionButton>
                ) : null}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function ProfileCard({ vendor }: { vendor: VendorDetail }) {
  const { profile } = vendor;
  return (
    <Card>
      <CardHeader title="Profile & registration" />
      <CardBody className="pt-3">
        <dl>
          <KeyValue label="Legal name">{profile.legal_name}</KeyValue>
          <KeyValue label="GSTIN">{profile.gstin}</KeyValue>
          <KeyValue label="Udyam / MSME">{profile.udyam_msme}</KeyValue>
          <KeyValue label="City">
            {profile.city} · {profile.state}
          </KeyValue>
          <KeyValue label="Payment terms">{profile.payment_terms}</KeyValue>
          <KeyValue label="Contact">
            {profile.contact_name} · {profile.contact_phone}
          </KeyValue>
        </dl>
      </CardBody>
    </Card>
  );
}

function RateRevisionsCard({ vendor }: { vendor: VendorDetail }) {
  return (
    <Card className="min-w-0">
      <CardHeader title="Rate list — revisions" />
      <CardBody className="pt-5">
        <Table>
          <THead>
            <TR>
              <TH>Rev</TH>
              <TH>Effective</TH>
              <TH>Item</TH>
              <TH>Rate change</TH>
              <TH align="right">Δ</TH>
              <TH>Approval</TH>
            </TR>
          </THead>
          <TBody zebra>
            {vendor.rate_revisions.map((revision) => (
              <TR key={`${revision.revision}-${revision.item_code}`}>
                <TD className="h-10">{revision.revision}</TD>
                <TD muted className="h-10">
                  {formatDay(revision.effective_date)}
                </TD>
                <TD className="h-10">{revision.item_code}</TD>
                <TD numeric className="h-10">
                  {formatMoney(revision.previous_rate)} → {formatMoney(revision.new_rate)}
                </TD>
                <TD align="right" numeric strong className="h-10">
                  +{revision.change_percent}%
                </TD>
                <TD className="h-10">
                  {revision.approval === "approved" ? (
                    <Pill tone="green">Approved</Pill>
                  ) : (
                    <Pill tone="amber">Pending</Pill>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </CardBody>
    </Card>
  );
}

function LeadTimesCard({ vendor }: { vendor: VendorDetail }) {
  return (
    <Card>
      <CardHeader title="Lead times — per item" />
      <CardBody className="pt-3">
        {vendor.lead_times.map((lead) => (
          <dl key={lead.item_code}>
            <KeyValue label={`${lead.item_code} supply`}>{lead.vendor_supply_days} days · vendor-stated</KeyValue>
            <KeyValue label="Internal PO time">{lead.internal_po_days} days · entered manually</KeyValue>
            <KeyValue label="Total lead time">{lead.total_days} days → reorder formula</KeyValue>
          </dl>
        ))}
        <NoteBox tone="blue" className="mt-4 px-4 py-2">
          <p className="text-[11px] font-semibold text-blue-600">Lead time = vendor supply + internal PO time</p>
          <p className="text-[10.5px] text-gray-500">— both sources feed F19 explicitly (FB-19).</p>
        </NoteBox>
      </CardBody>
    </Card>
  );
}

/** Quality history tab: the per-item poor-quality counts the catalogue table carries (F38). */
function QualityTable({ vendor }: { vendor: VendorDetail }) {
  return (
    <div className="max-w-[708px]">
      <Table>
        <THead>
          <TR>
            <TH>Our SKU</TH>
            <TH>Item</TH>
            <TH align="center">Poor · M/Q/Y</TH>
          </TR>
        </THead>
        <TBody zebra>
          {vendor.catalogue.map((line) => (
            <TR key={line.vendor_item_code}>
              <TD>{line.item_code}</TD>
              <TD>{line.item_name}</TD>
              <TD align="center" muted numeric>
                {line.poor.month} / {line.poor.quarter} / {line.poor.year}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
