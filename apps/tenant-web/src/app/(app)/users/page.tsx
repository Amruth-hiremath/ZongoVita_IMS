import { hasPermission } from "@ims/api-client";
import { ButtonLink, PageHeader, Pill, TBody, TD, TH, THead, TR, Table, type Tone } from "@ims/ui";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { NotPermitted } from "@/components/not-permitted";
import { getCapabilitySummary, listUsers, type Granted, type RoleKind, type UserRow } from "@/data/users";
import { canOpen } from "@/session/access";
import { requireSession } from "@/session/server";

export const metadata: Metadata = { title: "Users & User Types" };

const roleTone: Record<RoleKind, Tone> = {
  super_admin: "dark",
  approver: "blue",
  store_keeper: "blue",
  standard: "gray",
  custom: "violet",
};

const statusPill: Record<UserRow["status"], { tone: Tone; label: string }> = {
  active: { tone: "green", label: "Active" },
  invited: { tone: "blue", label: "Invited" },
  inactive: { tone: "gray", label: "Inactive" },
};

const grantedPill: Record<Granted, { tone: Tone; label: string }> = {
  yes: { tone: "dark", label: "Yes" },
  partly: { tone: "blue", label: "Partly" },
  no: { tone: "gray", label: "No" },
};

const TYPES = ["Type 1", "Type 2", "Type 3", "Type 4"] as const;

/**
 * F22 Users & User Types. Signed in to Core, the list and the summary are live (GET /ui/v1/users,
 * GET /ui/v1/privilege-matrix). Adding, inviting and editing users have endpoints in Core but no
 * drawn form yet, so those buttons say so (U-06).
 */
export default async function UsersPage() {
  // Session and permission first: the layout's guard renders in parallel with this page, and
  // Core must not be asked for what the person may not see.
  const { me, workspace } = await requireSession();
  if (!canOpen(me, workspace, "/users")) return <NotPermitted />;
  const [users, summary] = await Promise.all([listUsers(), getCapabilitySummary()]);
  const canManageUsers = hasPermission(me, "access.user.manage");
  const canManageRoles = hasPermission(me, "access.role.manage");

  return (
    <>
      <PageHeader
        title="Users & User Types"
        actions={
          canManageUsers ? (
            <>
              <ActionButton endpoint="POST /ui/v1/users" waitingFor="design">
                Invite user
              </ActionButton>
              <ActionButton endpoint="POST /ui/v1/users" waitingFor="design" variant="primary">
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
                  {user.email ?? "—"}
                </TD>
                <TD className="h-9">
                  {user.role ? <Pill tone={roleTone[user.role.kind]}>{user.role.name}</Pill> : <span className="text-gray-400">No role</span>}
                </TD>
                <TD className="h-9">{user.scope_label}</TD>
                <TD muted className="h-9">
                  {user.last_active}
                </TD>
                <TD className="h-9">
                  <Pill tone={statusPill[user.status].tone}>{statusPill[user.status].label}</Pill>
                </TD>
                <TD align="right" className="h-9">
                  {canManageUsers ? (
                    <ActionButton
                      endpoint="PATCH /ui/v1/users/{id}"
                      waitingFor="design"
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
                    <Pill tone={grantedPill[granted].tone}>{grantedPill[granted].label}</Pill>
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
