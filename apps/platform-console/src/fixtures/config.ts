/** FIXTURE: sample data from wireframe F53 Platform Config. Temporary; see src/data/source.ts. */
import type { PlatformConfig } from "@/data/config";

export const platformConfig: PlatformConfig = {
  environment: "PRODUCTION",
  module_flags: [
    { flag_id: "core", label: "Core IMS — items, stock, approvals", enabled: true },
    { flag_id: "integrations", label: "Integrations — connector framework · Asset Maintenance live", enabled: true },
    { flag_id: "developer", label: "Developer & API console — keys · webhooks · sandbox", enabled: true },
    { flag_id: "sandbox", label: "Sandbox environments for every tenant", enabled: true },
    { flag_id: "sms", label: "SMS alert channel (Q12 — undecided)", enabled: false },
    { flag_id: "accounting", label: "Accounting connector (Q27 — Phase 2)", enabled: false },
  ],
  environment_rails: [
    { label: "API versioning", value: "/api/v1 · additive changes only (FR-22)" },
    { label: "Sandbox", value: "synthetic data · separate keys (FR-21)" },
    { label: "Webhooks", value: "signed · retries 1 min → 24 h, then parked (FR-16)" },
    { label: "Authentication", value: "password + authenticator (MFA) · API client credentials · SSO in Phase 2" },
  ],
  tenants_may_tune: [
    "Document numbering (F58)",
    "Notification preferences",
    "Custom workflows (F23 · F61)",
    "Custom attributes (Q5)",
  ],
  tenants_may_not_touch: ["Tenant isolation (FB-22)", "Audit retention · lifetime (Q22)", "API rate limits (LD-88)"],
};
