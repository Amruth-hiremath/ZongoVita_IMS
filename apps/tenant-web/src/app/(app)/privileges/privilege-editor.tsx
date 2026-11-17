"use client";

import { Button, Card, Checkbox, PageHeader, TBody, TD, TH, THead, TR, Table } from "@ims/ui";
import { Shield } from "lucide-react";
import { useState } from "react";

import { ActionButton } from "@/components/action-button";
import type { PrivilegeMatrix } from "@/data/privileges";

type Grants = Record<string, string[]>;

const guards: { title: string; detail: string }[] = [
  { title: "Tenant isolation", detail: "no permission can cross enterprises" },
  { title: "Audit trail read-only", detail: "no type can edit history — ever" },
  { title: "One super-admin type", detail: "exactly one, always on, per tenant" },
  { title: "Changes are audited", detail: "who changed what, when — immutable" },
];

/**
 * F36 matrix. Ticks change locally; "Save type configuration" is where Core takes the new set
 * (PUT /ui/v1/roles/{id}/permissions). "Reset to seeded defaults" restores the seeded ticks on
 * the page only; nothing is stored until saved.
 */
export function PrivilegeEditor({ matrix, canEdit }: { matrix: PrivilegeMatrix; canEdit: boolean }) {
  const [grants, setGrants] = useState<Grants>(matrix.grants);

  const toggle = (roleId: string, capabilityId: string, on: boolean) => {
    setGrants((current) => {
      const set = new Set(current[roleId] ?? []);
      if (on) set.add(capabilityId);
      else set.delete(capabilityId);
      return { ...current, [roleId]: [...set] };
    });
  };

  return (
    <>
      <PageHeader
        title="Privilege Matrix"
        subtitle="Capabilities × user types — tick and submit; the type instantly carries those privileges (FB-23, FB-24)"
        actions={
          canEdit ? (
            <>
              <Button onClick={() => setGrants(matrix.seeded_defaults)}>Reset to seeded defaults</Button>
              <ActionButton endpoint="PUT /ui/v1/roles/{id}/permissions" variant="primary">
                Save type configuration
              </ActionButton>
            </>
          ) : null
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)_276px] items-start gap-8 max-lg:grid-cols-1">
        <Table>
          <THead>
            <TR>
              <TH className="h-16 pt-3 align-top text-[12.5px] text-gray-900">Capability</TH>
              {matrix.roles.map((role) => (
                <TH key={role.role_id} align="center" className="h-16 w-[98px] pt-3 align-top">
                  <span className="block text-[12.5px] text-gray-900">{role.name}</span>
                  <span className="mt-1.5 block text-[10px] font-normal text-gray-500">{role.summary}</span>
                </TH>
              ))}
            </TR>
          </THead>
          <TBody zebra>
            {matrix.capabilities.map((capability) => (
              <TR key={capability.capability_id}>
                <TD className="h-[42px] text-[12.5px] text-gray-700">{capability.label}</TD>
                {matrix.roles.map((role) => (
                  <TD key={role.role_id} align="center" className="h-[42px]">
                    <Checkbox
                      aria-label={`${capability.label} — ${role.name}`}
                      checked={(grants[role.role_id] ?? []).includes(capability.capability_id)}
                      disabled={!canEdit}
                      onChange={(event) => toggle(role.role_id, capability.capability_id, event.target.checked)}
                      className="justify-center"
                    />
                  </TD>
                ))}
              </TR>
            ))}
          </TBody>
        </Table>

        <div className="flex flex-col gap-5">
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
                <dd className="mt-1.5">assigned a type · effective privileges are that type&apos;s set</dd>
              </div>
            </dl>
            <p className="mt-4 text-[10.5px] leading-4 text-gray-500">
              Types can be cloned into custom roles — e.g. “Purchasing” (cloned from type 2).
            </p>
          </Card>

          <Card className="min-h-[348px] p-4">
            <h2 className="text-[13px] font-semibold text-gray-900">Platform guards — not configurable</h2>
            <ul className="mt-5 space-y-6">
              {guards.map((guard) => (
                <li key={guard.title} className="flex gap-2.5">
                  <Shield aria-hidden className="mt-0.5 size-3.5 shrink-0 text-blue-600" strokeWidth={1.8} />
                  <div>
                    <p className="text-[11.5px] font-semibold text-gray-900">{guard.title}</p>
                    <p className="mt-0.5 text-[10px] leading-[14px] text-gray-500">
                      {guard.detail}
                    </p>
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
