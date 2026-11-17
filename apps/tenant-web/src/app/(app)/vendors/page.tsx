import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader, Pill, StatCard } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { listVendors } from "@/data/vendors";
import { formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

import { VendorLifecycle } from "./vendor-lifecycle";
import { VendorsList } from "./vendors-list";

export const metadata: Metadata = { title: "Vendors" };

/** F37 Vendors. */
export default async function VendorsPage() {
  const [{ me }, page] = await Promise.all([requireSession(), listVendors()]);
  const canManage = hasPermission(me, "purchasing.vendor.manage");
  const canExport = hasPermission(me, "reporting.export.run");
  const { summary } = page;

  return (
    <>
      <PageHeader
        title="Vendors"
        subtitle="Vendor master — registration, catalogue & MOQ, rate list, per-item lead times, quality history (FB-25)"
        actions={
          <>
            {canExport ? <ActionButton endpoint="POST /ui/v1/exports">Export vendors</ActionButton> : null}
            {canManage ? (
              <ButtonLink href="/vendors/onboarding/VD-0043" variant="primary">
                + Onboard vendor
              </ButtonLink>
            ) : null}
          </>
        }
      />

      <div className="grid max-w-[1136px] grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <StatCard
          label="Vendors"
          value={formatQty(summary.vendor_count)}
          hint={`${summary.active_count} active · ${summary.retired_count} retired`}
        />
        <StatCard
          label="Supplied items"
          value={formatQty(summary.supplied_item_count)}
          badge={<Pill tone="blue">linked to SKUs</Pill>}
        />
        <StatCard
          label="Rate revisions"
          value={formatQty(summary.rate_revisions_pending)}
          badge={<Pill tone="amber">pending approval</Pill>}
        />
        <StatCard label="Quality · Month" value={formatQty(summary.poor_items_month)} hint="poor items · see F33" />
      </div>

      <VendorsList page={page} />
      <VendorLifecycle />
    </>
  );
}
