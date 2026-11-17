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
    { label: "API versioning", value: "v1.4 · X-API-Version header (FR-22)" },
    { label: "Sandbox", value: "synthetic data · separate keys (FR-21)" },
    { label: "Webhooks", value: "signed · 3 retries → dead-letter queue (FR-16)" },
    { label: "Authentication", value: "OAuth2 + PKCE · company SSO (Q24)" },
  ],
  plan_rails: [
    { rail: "Seats", starter: "5", growth: "20", enterprise: "50+ add-on" },
    { rail: "Sites", starter: "1", growth: "3", enterprise: "Unlimited" },
    { rail: "Audit retention", starter: "7 years", growth: "7 years", enterprise: "7 years · immutable" },
    { rail: "API rate limit", starter: "60 req/min", growth: "300 req/min", enterprise: "600 req/min" },
    { rail: "Support tier", starter: "Standard", growth: "Standard", enterprise: "Priority · 4 h SLA" },
    { rail: "Data residency", starter: "India", growth: "India", enterprise: "India · choice" },
  ],
  tenants_may_tune: [
    "Document numbering (F58)",
    "Notification preferences",
    "Custom workflows (F23 · F61)",
    "Custom attributes (Q5)",
  ],
  tenants_may_not_touch: ["Tenant isolation (FB-22)", "Audit retention · lifetime (Q22)", "Data residency · India"],
};
