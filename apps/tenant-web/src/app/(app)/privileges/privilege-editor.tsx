"use client";

import { USER_TYPE_1, USER_TYPE_2, USER_TYPE_3, USER_TYPE_4, type PermissionCode } from "@ims/api-client";
import { Button, Card, Checkbox, PageHeader, Pill, TBody, TD, TH, THead, TR, Table, useNotice } from "@ims/ui";
import { Lock, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useMemo, useState } from "react";

import type { MatrixPermission, MatrixRole, PrivilegeMatrix } from "@/data/privileges";

const guards: { title: string; detail: string }[] = [
  { title: "Tenant isolation", detail: "no permission can cross enterprises" },
  { title: "Audit trail read-only", detail: "no type can edit history — ever" },
  { title: "One super admin", detail: "exactly one person, always, per tenant · changed only by transfer" },
  { title: "Changes are audited", detail: "who changed what, when — immutable" },
];

/** The LLD section 7 module groups, in the LLD's order. */
const GROUPS: { title: string; modules: string[] }[] = [
  { title: "Catalogue", modules: ["catalog"] },
  { title: "Inventory, receiving", modules: ["inventory", "receiving"] },
  { title: "Issuance, transfers, counts", modules: ["issuance", "transfers", "counts"] },
  { title: "Returns and quality", modules: ["returns", "quality"] },
  { title: "Purchasing, replenishment", modules: ["purchasing", "replenishment"] },
  { title: "Workflow, access, organisation", modules: ["workflow", "access", "org"] },
  { title: "Alerts, reporting, audit, integration, settings", modules: ["alerts", "reporting", "audit", "integration", "config"] },
];

/** Seeded defaults of the user types (LLD 5.1), restored by "Reset to seeded defaults". */
const SEEDED: Record<string, readonly PermissionCode[]> = {
  user_type_1: USER_TYPE_1,
  user_type_2: USER_TYPE_2,
  user_type_3: USER_TYPE_3,
  user_type_4: USER_TYPE_4,
};

/** Short line under each column title; the user-type lines are the wireframe's. */
function summaryOf(role: MatrixRole): string {
  if (role.is_super_admin) return "every permission · fixed";
  switch (role.user_type_no) {
    case 1:
      return "all but reserved";
    case 2:
      return "approve";
    case 3:
      return "request · issue";
    case 4:
      return "view · request";
    default:
      return "custom role";
  }
}

type Grants = Record<string, PermissionCode[]>;

interface SaveResult {
  role: string;
  added: string[];
  removed: string[];
  affected: { name: string; added: string[]; removed: string[] }[];
}

interface Problem {
  code?: string;
  detail?: string | null;
  title?: string;
}

function problemMessage(role: MatrixRole, status: number, problem: Problem | null): string {
  switch (problem?.code) {
    case "VERSION_CONFLICT":
      return `${role.name} was changed by someone else meanwhile. Reload the page and make the change again.`;
    case "REASON_REQUIRED":
      return `${role.name}: in GxP mode a reason for change is required; its field has no approved design yet.`;
    case "PERMISSION_DENIED":
    case "SITE_SCOPE_DENIED":
      return `${role.name}: ${problem.detail ?? "you cannot make this change"}.`;
    default:
      return `${role.name} was not saved (${problem?.title ?? `HTTP ${status}`}).`;
  }
}

/**
 * F36 Privilege Matrix (LLD 7): permissions x roles. Rows are the permission catalogue in the
 * LLD's module groups; the frame's twelve capability rows do not exist in the design
 * (Docs/UI_Implementation.md section 10). Ticks change locally; "Save type configuration" writes
 * each changed role with PUT /ui/v1/roles/{id}/permissions and shows who is affected.
 *
 * What the page lets you tick reflects the rules Core enforces: the Super Admin column is fixed,
 * reserved permissions stay with it, and you can only add a permission you hold at every site
 * (no self-escalation).
 */
export function PrivilegeEditor({
  matrix,
  canEdit,
  heldEverywhere,
}: {
  matrix: PrivilegeMatrix;
  canEdit: boolean;
  heldEverywhere: PermissionCode[];
}) {
  const router = useRouter();
  const notify = useNotice();
  const live = matrix.source === "core";
  const [roles, setRoles] = useState<MatrixRole[]>(matrix.roles);
  const [grants, setGrants] = useState<Grants>(() =>
    Object.fromEntries(matrix.roles.map((role) => [role.id, role.permissions])),
  );
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState<SaveResult[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const held = useMemo(() => new Set(heldEverywhere), [heldEverywhere]);
  const rows = useMemo(
    () =>
      GROUPS.map((group) => ({
        ...group,
        permissions: matrix.permissions.filter((p) => group.modules.includes(p.module)),
      })),
    [matrix.permissions],
  );

  const changed = roles.filter((role) => {
    const now = new Set(grants[role.id]);
    return role.editable && (now.size !== role.permissions.length || role.permissions.some((code) => !now.has(code)));
  });

  const toggle = (roleId: string, code: PermissionCode, on: boolean) => {
    setGrants((current) => {
      const set = new Set(current[roleId] ?? []);
      if (on) set.add(code);
      else set.delete(code);
      return { ...current, [roleId]: [...set] };
    });
  };

  const resetToSeeded = () =>
    setGrants((current) => ({
      ...current,
      ...Object.fromEntries(roles.filter((role) => SEEDED[role.code]).map((role) => [role.id, [...SEEDED[role.code]!]])),
    }));

  async function save() {
    setSaving(true);
    setErrors([]);
    const done: SaveResult[] = [];
    const failed: string[] = [];
    let refreshMe = false;
    for (const role of changed) {
      const response = await fetch(`/bff/roles/${role.id}/permissions`, {
        method: "PUT",
        headers: {
          "content-type": "application/json",
          "x-ims-csrf": "1",
          "if-match": `"${role.version}"`,
          "idempotency-key": `f36-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({ permissions: [...grants[role.id]!].sort() }),
      }).catch(() => null);
      if (response === null) {
        failed.push(`${role.name} was not saved: IMS Core could not be reached.`);
        continue;
      }
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      const body = (await response.json().catch(() => null)) as
        | (Problem & {
            role?: MatrixRole;
            added?: string[];
            removed?: string[];
            preview?: { display_name: string; added: string[]; removed: string[] }[];
          })
        | null;
      if (!response.ok || !body?.role) {
        if (response.status === 403) refreshMe = true;
        failed.push(problemMessage(role, response.status, body));
        continue;
      }
      const saved = body.role;
      setRoles((current) => current.map((r) => (r.id === saved.id ? saved : r)));
      setGrants((current) => ({ ...current, [saved.id]: saved.permissions }));
      done.push({
        role: role.name,
        added: body.added ?? [],
        removed: body.removed ?? [],
        affected: (body.preview ?? []).map((p) => ({ name: p.display_name, added: p.added, removed: p.removed })),
      });
    }
    setResults(done);
    setErrors(failed);
    setSaving(false);
    // A refusal can mean this person's own permissions changed: re-read /me (LLD 15).
    if (refreshMe) router.refresh();
  }

  const cell = (role: MatrixRole, permission: MatrixPermission) => {
    const checked = (grants[role.id] ?? []).includes(permission.code);
    const reservedElsewhere = permission.reserved_to_super_admin && !role.is_super_admin;
    const cannotAdd = !checked && !held.has(permission.code);
    const disabled = !canEdit || !role.editable || reservedElsewhere || cannotAdd;
    return (
      <Checkbox
        aria-label={`${permission.code} — ${role.name}`}
        checked={checked}
        disabled={disabled}
        title={
          reservedElsewhere
            ? "Reserved to the Super Admin"
            : cannotAdd && canEdit && role.editable
              ? "You can only grant permissions you hold at every site"
              : undefined
        }
        onChange={(event) => toggle(role.id, permission.code, event.target.checked)}
        className="justify-center"
      />
    );
  };

  return (
    <>
      <PageHeader
        title="Privilege Matrix"
        subtitle="Permissions × roles — tick and submit; the role instantly carries those privileges (FB-23, FB-24)"
        actions={
          canEdit ? (
            <>
              <Button onClick={resetToSeeded}>Reset to seeded defaults</Button>
              {live ? (
                <Button variant="primary" disabled={saving || changed.length === 0} onClick={save}>
                  {saving ? "Saving…" : "Save type configuration"}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={() =>
                    notify(
                      "Sample data",
                      "This session uses a sample persona, so nothing is saved. Signed in to IMS Core, this saves each changed role.",
                    )
                  }
                >
                  Save type configuration
                </Button>
              )}
            </>
          ) : null
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)_276px] items-start gap-8 max-lg:grid-cols-1">
        <Table>
          <THead>
            <TR>
              <TH className="h-16 pt-3 align-top text-[12.5px] text-gray-900">Permission</TH>
              {roles.map((role) => (
                <TH key={role.id} align="center" className="h-16 w-[98px] pt-3 align-top">
                  <span className="block text-[12.5px] text-gray-900">{role.name}</span>
                  <span className="mt-1.5 block text-[10px] font-normal text-gray-500">{summaryOf(role)}</span>
                </TH>
              ))}
            </TR>
          </THead>
          <TBody zebra>
            {rows.map((group) => (
              <Fragment key={group.title}>
                <TR>
                  <TH scope="rowgroup" colSpan={roles.length + 1} className="h-8 bg-gray-50 text-[11px] text-gray-700">
                    {group.title}
                  </TH>
                </TR>
                {group.permissions.map((permission) => (
                  <TR key={permission.code}>
                    <TD className="h-[38px] text-[12px] text-gray-700">
                      <span className="font-mono text-[11.5px]">{permission.code}</span>
                      {permission.site_scoped ? (
                        <Pill tone="gray" className="ml-2">
                          per site
                        </Pill>
                      ) : null}
                      {permission.reserved_to_super_admin ? (
                        <span className="ml-2 inline-flex items-center gap-1 text-[10.5px] text-gray-500">
                          <Lock aria-hidden className="size-3" strokeWidth={2} />
                          Super Admin only
                        </span>
                      ) : null}
                    </TD>
                    {roles.map((role) => (
                      <TD key={role.id} align="center" className="h-[38px]">
                        {cell(role, permission)}
                      </TD>
                    ))}
                  </TR>
                ))}
              </Fragment>
            ))}
          </TBody>
        </Table>

        <div className="flex flex-col gap-5">
          {errors.length > 0 ? (
            <Card className="border-red-200 p-4">
              <h2 className="text-[13px] font-semibold text-red-700">Not saved</h2>
              <ul role="alert" className="mt-2 space-y-1.5 text-[11.5px] leading-4 text-red-700">
                {errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </Card>
          ) : null}

          {results.length > 0 ? (
            <Card className="p-4">
              <h2 className="text-[13px] font-semibold text-gray-900">Saved</h2>
              <ul role="status" className="mt-3 space-y-3 text-[11.5px] leading-4 text-gray-700">
                {results.map((result) => (
                  <li key={result.role}>
                    <p className="font-semibold text-gray-900">{result.role}</p>
                    {result.added.length ? <p className="mt-1">Added: {result.added.join(", ")}</p> : null}
                    {result.removed.length ? <p className="mt-1">Removed: {result.removed.join(", ")}</p> : null}
                    <p className="mt-1 text-gray-500">
                      {result.affected.length === 0
                        ? "Nobody holds this role yet."
                        : `Effective now for ${result.affected.length} ${result.affected.length === 1 ? "person" : "people"}: ${result.affected
                            .map((person) => person.name)
                            .join(", ")}`}
                    </p>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          <Card className="p-4">
            <h2 className="text-[13px] font-semibold text-gray-900">How privileges work</h2>
            <dl className="mt-6 space-y-4 text-[11.5px] leading-4 text-gray-700">
              <div>
                <dt className="label-caps">Permission</dt>
                <dd className="mt-1.5">one action on one resource — e.g. “issue stock at a site”</dd>
              </div>
              <div>
                <dt className="label-caps">User type</dt>
                <dd className="mt-1.5">a named set of permissions — seeded 1–4, fully editable</dd>
              </div>
              <div>
                <dt className="label-caps">User</dt>
                <dd className="mt-1.5">
                  assigned one or more roles, at every site or at one · effective privileges are their union
                </dd>
              </div>
            </dl>
            <p className="mt-4 text-[10.5px] leading-4 text-gray-500">
              Types can be cloned into custom roles — e.g. “Purchasing” (cloned from type 2).
            </p>
          </Card>

          <Card className="p-4">
            <h2 className="text-[13px] font-semibold text-gray-900">Platform guards — not configurable</h2>
            <ul className="mt-5 space-y-6">
              {guards.map((guard) => (
                <li key={guard.title} className="flex gap-2.5">
                  <Shield aria-hidden className="mt-0.5 size-3.5 shrink-0 text-blue-600" strokeWidth={1.8} />
                  <div>
                    <p className="text-[11.5px] font-semibold text-gray-900">{guard.title}</p>
                    <p className="mt-0.5 text-[10px] leading-[14px] text-gray-500">{guard.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
