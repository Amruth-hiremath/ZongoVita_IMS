/** FIXTURE: sample data from wireframe F51 Platform Overview. Temporary; see src/data/source.ts. */
import type { PlatformOverview } from "@/data/overview";

export const platformOverview: PlatformOverview = {
  kpis: {
    enterprises: { total: 16, active: 14, provisioning: 1, suspended: 1 },
    users: { used: 312, licensed: 420, utilisation_percent: 74 },
    uptime: { percent: "99.95", window: "rolling 30 d", sla_percent: "99.9" },
    api_today: { calls: "1.2 M", p95_ms: 84, failures: 0 },
  },
  tenants: [
    {
      enterprise_code: "ENT-0007",
      company: "ZongoVita Industries",
      database: "db-ent-0007",
      users_used: 38,
      users_licensed: 50,
      api_calls_7d: "412 K",
      last_activity_label: "today 09:41",
    },
    {
      enterprise_code: "ENT-0012",
      company: "Gokulda Metals Pvt Ltd",
      database: "db-ent-0012",
      users_used: 11,
      users_licensed: 20,
      api_calls_7d: "96 K",
      last_activity_label: "today 08:12",
    },
    {
      enterprise_code: "ENT-0009",
      company: "Deccan Polymers LLP",
      database: "db-ent-0009",
      users_used: 4,
      users_licensed: 5,
      api_calls_7d: "14 K",
      last_activity_label: "22 Sep 16:40",
    },
    {
      enterprise_code: "ENT-0016",
      company: "Sunrise Auto Components",
      database: "provisioning",
      users_used: 0,
      users_licensed: 10,
      api_calls_7d: null,
      last_activity_label: "wizard step 3",
    },
  ],
  activity: [
    { title: "Onboarding started · ENT-0016 Sunrise Auto", meta: "Kiran Desai · 26 Sep 09:05 · wizard step 3" },
    { title: "License renewed · ENT-0012 Gokulda Metals", meta: "Kiran Desai · 20 Sep 14:22 · valid to 30 Nov 2027" },
    { title: "User limit raised to 50 · ENT-0007 ZongoVita", meta: "Kiran Desai · 12 Sep 11:03 · new licence record" },
    { title: "Schema migration 0003 · all customers", meta: "Pipeline · 10 Sep 02:10 · canary → 100%" },
  ],
  health: [
    { label: "API p95 latency", value: "84 ms — target < 150 ms (NFR-3)" },
    { label: "Webhook delivery", value: "99.7% first attempt · retries up to 24 h, then parked" },
    { label: "Backups", value: "daily 02:30 IST · point-in-time recovery (NFR-6)" },
  ],
};
