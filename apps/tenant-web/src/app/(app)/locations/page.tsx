import { hasPermission } from "@ims/api-client";
import { Callout, Card, PageHeader, Pill, SectionLabel, TBody, TD, TH, THead, TR, Table, cn } from "@ims/ui";
import { Building2, Pencil } from "lucide-react";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NotPermitted } from "@/components/not-permitted";
import { listLocations, type LocationRow } from "@/data/locations";
import { formatMoney, formatQty } from "@/lib/format";
import { canOpen } from "@/session/access";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Locations" };

const NONE = "—";

function StatusPill({ status }: { status: LocationRow["status"] }) {
  if (status === "live") return <Pill tone="green">Live</Pill>;
  return <Pill tone="gray">{status === "staged" ? "Staged" : "Inactive"}</Pill>;
}

function usersLine(users: NonNullable<LocationRow["users"]>): string {
  return [`Users: ${users.total}`, ...users.by_type.map((group) => `${group.type_label} ×${group.count}`)].join(" · ");
}

function footLine(location: LocationRow): string {
  if (location.users) return usersLine(location.users);
  if (location.status === "staged") return "Provisioned · awaiting go-live";
  if (location.status === "inactive") return "Inactive";
  return NONE;
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
                waitingFor="design"
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
          <span>{location.type_label ?? NONE}</span>
          <span>{location.item_count === null ? NONE : formatQty(location.item_count)} items</span>
          <span>Value {location.stock_value === null ? NONE : formatMoney(location.stock_value)}</span>
        </div>
        <p className="mt-2 text-[10.5px] text-gray-400">{footLine(location)}</p>
      </div>
    </Card>
  );
}

/**
 * F21 Locations: the customer's sites (the frame calls them locations). Signed in to Core the
 * sites, their status and the users assigned at each are live (GET /ui/v1/sites, GET
 * /ui/v1/users). Type and city are not part of the LLD's site record, stock figures need
 * Inventory Core and the SKU rule needs numbering schemes, so those show "—". Adding and editing
 * sites have endpoints but no drawn form yet (U-06).
 */
export default async function LocationsPage() {
  const { me, workspace } = await requireSession();
  if (!canOpen(me, workspace, "/locations")) return <NotPermitted />;
  const list = await listLocations({ withUsers: hasPermission(me, "access.user.manage") });
  const canManage = hasPermission(me, "org.site.manage");
  const subtitle =
    list.source === "core"
      ? `Multi-location from day one (Q9) — ${list.live} live, ${list.staged} staged`
      : "Multi-location from day one (Q9) — initial deployment: one warehouse live, three staged";

  return (
    <>
      <PageHeader
        title="Locations"
        subtitle={subtitle}
        actions={
          canManage ? (
            <ActionButton endpoint="POST /ui/v1/sites" waitingFor="design" variant="primary">
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

      {list.source === "fixtures" ? (
        <Callout tone="info" dismissible className="mt-6 min-h-[42px]">
          Remaining locations go live within 6 months (Assumptions) — data model is multi-location from the start.
        </Callout>
      ) : null}

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
                <TD>{location.type_label ?? NONE}</TD>
                <TD>{location.city ?? NONE}</TD>
                <TD align="right" numeric>
                  {location.item_count === null ? NONE : formatQty(location.item_count)}
                </TD>
                <TD align="right" numeric>
                  {location.stock_value === null ? NONE : formatMoney(location.stock_value, "")}
                </TD>
                <TD muted>{location.sku_rule ?? NONE}</TD>
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
