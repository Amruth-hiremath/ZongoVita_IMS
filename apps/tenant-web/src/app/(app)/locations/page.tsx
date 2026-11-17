import { hasPermission } from "@ims/api-client";
import { Callout, Card, PageHeader, Pill, SectionLabel, TBody, TD, TH, THead, TR, Table, cn } from "@ims/ui";
import { Building2, Pencil } from "lucide-react";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { listLocations, type LocationRow } from "@/data/locations";
import { formatMoney, formatQty } from "@/lib/format";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Locations" };

function StatusPill({ status }: { status: LocationRow["status"] }) {
  return status === "live" ? <Pill tone="green">Live</Pill> : <Pill tone="gray">Staged</Pill>;
}

function usersLine(users: NonNullable<LocationRow["users"]>): string {
  return [`Users: ${users.total}`, ...users.by_type.map((group) => `${group.type_label} ×${group.count}`)].join(" · ");
}

function LocationCard({ location, canEdit }: { location: LocationRow; canEdit: boolean }) {
  return (
    <Card
      className={cn("flex min-h-[120px] gap-4 px-4 pb-3 pt-4", location.status === "live" && "border-blue-200")}
    >
      <Building2 aria-hidden className="mt-1 size-[18px] shrink-0 text-gray-500" strokeWidth={1.6} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-[14px] font-bold leading-5 text-gray-900">{location.location_code}</h2>
            <p className="mt-0.5 text-[12.5px] text-gray-700">{location.name}</p>
          </div>
          <div className="flex shrink-0 items-center gap-12 max-sm:gap-4">
            <StatusPill status={location.status} />
            {canEdit ? (
              <ActionButton
                endpoint="PATCH /ui/v1/sites/{id}"
                variant="link"
                aria-label={`Edit ${location.location_code}`}
                className="text-gray-500"
              >
                <Pencil aria-hidden className="size-3.5" strokeWidth={1.6} />
              </ActionButton>
            ) : null}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-[152px_120px_minmax(0,1fr)] gap-2 text-[11.5px] text-gray-500 max-sm:grid-cols-1">
          <span>{location.type_label}</span>
          <span>{formatQty(location.item_count)} items</span>
          <span>Value {formatMoney(location.stock_value)}</span>
        </div>
        <p className="mt-2 text-[10.5px] text-gray-400">
          {location.users ? usersLine(location.users) : "Provisioned · awaiting go-live"}
        </p>
      </div>
    </Card>
  );
}

/** F21 Locations. */
export default async function LocationsPage() {
  const [{ me }, list] = await Promise.all([requireSession(), listLocations()]);
  const canManage = hasPermission(me, "org.site.manage");

  return (
    <>
      <PageHeader
        title="Locations"
        subtitle="Multi-location from day one (Q9) — initial deployment: one warehouse live, three staged"
        actions={
          canManage ? (
            <ActionButton endpoint="POST /ui/v1/sites" variant="primary">
              + Add location
            </ActionButton>
          ) : null
        }
      />

      <div className="grid grid-cols-2 gap-x-10 gap-y-4 max-lg:grid-cols-1">
        {list.rows.map((location) => (
          <LocationCard key={location.location_code} location={location} canEdit={canManage} />
        ))}
      </div>

      <Callout tone="info" dismissible className="mt-6 min-h-[42px]">
        Remaining locations go live within 6 months (Assumptions) — data model is multi-location from the start.
      </Callout>

      <SectionLabel className="mt-4">All locations</SectionLabel>
      <div className="mt-2 max-w-[1100px]">
        <Table>
          <THead>
            <TR>
              <TH>Code</TH>
              <TH>Name</TH>
              <TH>Type</TH>
              <TH>City</TH>
              <TH align="right">Items</TH>
              <TH align="right">Stock value (₹)</TH>
              <TH>SKU rule</TH>
              <TH>Status</TH>
            </TR>
          </THead>
          <TBody zebra>
            {list.rows.map((location) => (
              <TR key={location.location_code}>
                <TD>{location.location_code}</TD>
                <TD>{location.name}</TD>
                <TD>{location.type_label}</TD>
                <TD>{location.city}</TD>
                <TD align="right" numeric>
                  {formatQty(location.item_count)}
                </TD>
                <TD align="right" numeric>
                  {formatMoney(location.stock_value, "")}
                </TD>
                <TD muted>{location.sku_rule}</TD>
                <TD>
                  <StatusPill status={location.status} />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </>
  );
}
