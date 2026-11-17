import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader, Pill, TBody, TD, TH, THead, TR, Table, type Tone } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getCapabilitySummary, listUsers, type RoleKind, type UserRow } from "@/data/users";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Users & User Types" };

const roleTone: Record<RoleKind, Tone> = {
  super_admin: "dark",
  approver: "blue",
  store_keeper: "blue",
  standard: "gray",
  custom: "violet",
};

function scopeLabel(user: UserRow): string {
  if (user.custom_scope) return "— custom —";
  if (user.site_codes === null) return "All locations";
  return user.site_codes.join(", ");
}

const TYPES = ["Type 1", "Type 2", "Type 3", "Type 4"] as const;

/** F22 Users & User Types. */
export default async function UsersPage() {
  const [{ me }, users, summary] = await Promise.all([requireSession(), listUsers(), getCapabilitySummary()]);
  const canManageUsers = hasPermission(me, "access.user.manage");
  const canManageRoles = hasPermission(me, "access.role.manage");

  return (
    <>
      <PageHeader
        title="Users & User Types"
        actions={
          canManageUsers ? (
            <>
              <ActionButton endpoint="POST /ui/v1/users (invite)">Invite user</ActionButton>
              <ActionButton endpoint="POST /ui/v1/users" variant="primary">
                + Add user
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="max-w-[990px]">
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Email</TH>
              <TH>User type</TH>
              <TH>Location scope</TH>
              <TH>Last active</TH>
              <TH>Status</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody zebra>
            {users.rows.map((user) => (
              <TR key={user.id}>
                <TD strong className="h-9">
                  {user.display_name}
                </TD>
                <TD muted className="h-9">
                  {user.email}
                </TD>
                <TD className="h-9">
                  <Pill tone={roleTone[user.role.kind]}>{user.role.name}</Pill>
                </TD>
                <TD className="h-9">{scopeLabel(user)}</TD>
                <TD muted className="h-9">
                  {user.last_active}
                </TD>
                <TD className="h-9">
                  <Pill tone={user.status === "active" ? "green" : "gray"}>
                    {user.status === "active" ? "Active" : "Inactive"}
                  </Pill>
                </TD>
                <TD align="right" className="h-9">
                  {canManageUsers ? (
                    <ActionButton
                      endpoint="PATCH /ui/v1/users/{id}"
                      variant="link"
                      aria-label={`Edit ${user.display_name}`}
                      className="text-[11.5px] font-normal text-gray-500"
                    >
                      Edit
                    </ActionButton>
                  ) : null}
                </TD>
              </TR>
            ))}
            {users.remaining ? (
              <TR>
                <TD strong className="h-9">
                  + {users.remaining.count} more users
                </TD>
                <TD muted className="h-9">
                  across {users.remaining.site_codes.join(", ")}
                </TD>
                <TD className="h-9">
                  <Pill tone="gray">{users.remaining.role_label}</Pill>
                </TD>
                <TD muted className="h-9">
                  {users.remaining.scope_label}
                </TD>
                <TD muted className="h-9">
                  —
                </TD>
                <TD className="h-9">
                  <Pill tone="gray">Active</Pill>
                </TD>
                <TD className="h-9" />
              </TR>
            ) : null}
          </TBody>
        </Table>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-gray-900">
          Permission matrix by user type — IAM-style, configurable (FB-23 · FB-24)
        </h2>
        {canManageRoles ? (
          <ButtonLink href="/privileges" variant="soft" size="sm" className="h-[30px] text-[13px]">
            Open full editor → F36
          </ButtonLink>
        ) : null}
      </div>

      <div className="mt-4">
        <Table>
          <THead>
            <TR>
              <TH>Capability</TH>
              {TYPES.map((type) => (
                <TH key={type} align="center" className="w-[120px]">
                  {type}
                </TH>
              ))}
              <TH>Applies to</TH>
            </TR>
          </THead>
          <TBody zebra>
            {summary.map((row) => (
              <TR key={row.capability}>
                <TD strong className="h-[33px]">
                  {row.capability}
                </TD>
                {row.granted.map((granted, index) => (
                  <TD key={TYPES[index]} align="center" className="h-[33px]">
                    {granted ? (
                      <Pill tone="dark">Yes</Pill>
                    ) : (
                      <Pill tone="gray">No</Pill>
                    )}
                  </TD>
                ))}
                <TD muted className="h-[33px]">
                  {row.applies_to}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </>
  );
}
