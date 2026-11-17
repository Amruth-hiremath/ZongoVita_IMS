/** FIXTURE: the matrix drawn in wireframe F36. Temporary; see src/data/source.ts. */
import type { MatrixCapability, PrivilegeMatrix } from "@/data/privileges";

const capabilities: MatrixCapability[] = [
  { capability_id: "raise_issuance", label: "Raise issuance request" },
  { capability_id: "approve_requests", label: "Approve requests · locks stock" },
  { capability_id: "issue_from_store", label: "Issue from store · barcode" },
  { capability_id: "receive_stock", label: "Receive stock · GRN" },
  { capability_id: "returns_intake", label: "Returns intake" },
  { capability_id: "quarantine_verdict", label: "Quarantine verdict" },
  { capability_id: "edit_items", label: "Add / edit items" },
  { capability_id: "manage_categories", label: "Manage categories" },
  { capability_id: "manage_vendors", label: "Manage vendors & purchase recs" },
  { capability_id: "view_reports", label: "View reports & audit trail" },
  { capability_id: "manage_users", label: "Manage users" },
  { capability_id: "configure_privileges", label: "Configure privileges" },
];

const grants: Record<string, string[]> = {
  "role-type-1": capabilities.map((capability) => capability.capability_id),
  "role-type-2": [
    "raise_issuance",
    "approve_requests",
    "receive_stock",
    "quarantine_verdict",
    "edit_items",
    "view_reports",
  ],
  "role-type-3": ["raise_issuance", "issue_from_store", "receive_stock", "returns_intake", "view_reports"],
  "role-type-4": ["raise_issuance", "returns_intake", "view_reports"],
};

export const privilegeMatrix: PrivilegeMatrix = {
  roles: [
    { role_id: "role-type-1", name: "Type 1", summary: "super admin" },
    { role_id: "role-type-2", name: "Type 2", summary: "approve" },
    { role_id: "role-type-3", name: "Type 3", summary: "request · issue" },
    { role_id: "role-type-4", name: "Type 4", summary: "view · request" },
  ],
  capabilities,
  grants,
  seeded_defaults: grants,
};
