/** FIXTURE: sample data from wireframe F51 Platform Overview. Temporary; see src/data/source.ts. */
import type { PlatformOverview } from "@/data/overview";

export const platformOverview: PlatformOverview = {
  kpis: {
    enterprises: { total: 16, active: 14, onboarding: 1, trial: 1 },
    seats: { used: 312, licensed: 420, utilisation_percent: 74 },
    uptime: { percent: "99.95", window: "rolling 30 d", sla_percent: "99.9" },
    api_today: { calls: "1.2 M", p95_ms: 84, failures: 0 },
  },
  tenants: [
    {
      enterprise_code: "ENT-0007",
      company: "ZongoVita Industries",
      plan: "Enterprise",
      database: "db-ent-0007",
      seats_used: 38,
      seats_licensed: 50,
      api_calls_7d: "412 K",
      last_activity_label: "today 09:41",
    },
    {
      enterprise_code: "ENT-0012",
      company: "Gokulda Metals Pvt Ltd",
      plan: "Growth",
      database: "db-ent-0012",
      seats_used: 11,
      seats_licensed: 20,
      api_calls_7d: "96 K",
      last_activity_label: "today 08:12",
    },
    {
      enterprise_code: "ENT-0009",
      company: "Deccan Polymers LLP",
      plan: "Starter",
      database: "db-ent-0009",
      seats_used: 4,
      seats_licensed: 5,
      api_calls_7d: "14 K",
      last_activity_label: "22 Sep 16:40",
    },
    {
      enterprise_code: "ENT-0016",
      company: "Sunrise Auto Components",
      plan: null,
      database: "provisioning",
      seats_used: 0,
      seats_licensed: 10,
      api_calls_7d: null,
      last_activity_label: "wizard step 3",
    },
  ],
  activity: [
    { title: "Onboarding started · ENT-0016 Sunrise Auto", meta: "Kiran Desai · 26 Sep 09:05 · wizard step 3" },
    { title: "License renewed · ENT-0012 Gokulda Metals", meta: "Kiran Desai · 20 Sep 14:22 · Growth · annual" },
    { title: "Seat add-on +5 · ENT-0007 ZongoVita", meta: "Kiran Desai · 12 Sep 11:03 · prorated ₹ 4,470" },
    { title: "Plan upgraded Starter → Growth · ENT-0012", meta: "Platform · billing sync · 04 Jun 2026" },
  ],
  health: [
    { label: "API p95 latency", value: "84 ms — target < 150 ms (NFR-3)" },
    { label: "Webhook delivery", value: "99.7% first attempt · 3 retries then DLQ" },
    { label: "Backups", value: "daily 02:30 IST · point-in-time recovery (NFR-6)" },
  ],
};
