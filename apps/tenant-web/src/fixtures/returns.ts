/** FIXTURE: sample data from wireframes F43 and F49. Temporary; see src/data/source.ts. */
import type { ManagerReturns, StoreReturns } from "@/data/returns";

export const managerReturns: ManagerReturns = {
  kpis: [
    { label: "Open returns", value: "5", hint: "2 sites · 3 requesters" },
    { label: "In quarantine", value: "3 lines", badge: { label: "1 overdue", tone: "amber" } },
    { label: "Verdicts due", value: "2", badge: { label: "your call", tone: "blue" } },
    { label: "Supplier claims", value: "₹2,140", hint: "3 fail lines · F33" },
  ],
  rows: [
    {
      return_ref: "RET-0421",
      items_summary: "Seal kit ×1 · V-belt ×2",
      qty_display: "1 + 2",
      reason: "Poor + wrong",
      returned_by: "Rahul Verma",
      stage: "Quarantine",
      state: { kind: "verdict_due", label: "Verdict due" },
    },
    {
      return_ref: "RET-0419",
      items_summary: "V-Belt A-43",
      qty_display: "2",
      reason: "Wrong item",
      returned_by: "Kavita Rao",
      stage: "Quarantine",
      state: { kind: "spec_check", label: "Spec check" },
    },
    {
      return_ref: "RET-0418",
      items_summary: "Safety Gloves (L)",
      qty_display: "6 pairs",
      reason: "Damaged",
      returned_by: "Rahul Verma",
      stage: "Quarantine",
      state: { kind: "overdue", label: "Overdue 1 d" },
    },
    {
      return_ref: "RET-0412",
      items_summary: "Safety Gloves (L)",
      qty_display: "2 pairs",
      reason: "Poor quality",
      returned_by: "Ananya Iyer",
      stage: "Vendor claim",
      state: { kind: "claim_open", label: "Claim open" },
    },
    {
      return_ref: "RET-0409",
      items_summary: "Grease EP-2 5 kg",
      qty_display: "2 tubs",
      reason: "Mismatch",
      returned_by: "Kavita Rao",
      stage: "Restocked",
      state: { kind: "closed", label: "Closed" },
    },
  ],
  notice: "QTN-0029 is overdue — the store's FAIL recommendation awaits your confirmation.",
  verdicts: [
    {
      return_ref: "RET-0418",
      quarantine_ref: "QTN-0029",
      title: "Verdict — QTN-0029 · Gloves ×6",
      facts: [
        { label: "Return", value: "RET-0418 · Rahul Verma" },
        { label: "Reason", value: "Damaged — torn seams" },
        { label: "Hold since", value: "21 Sep 14:02 · overdue 1 d" },
        { label: "Vendor · PO", value: "SafeGuard · PO-2213" },
      ],
      store_validation: "FAIL recommended — 6 of 6 pairs torn at the seam · photos + issuance record attached",
      disposition_label: "Disposition · Damaged",
      // F32 names the dispositions: "scrap, rework or supplier return (configurable)".
      disposition_options: ["Scrap — configurable (FB-16)", "Rework", "Supplier return"],
      disposition_default: "Scrap — configurable (FB-16)",
    },
  ],
  selected_ref: "RET-0418",
  semantics: {
    title: "Verdict semantics — what your decision unlocks",
    steps: [
      {
        tone: "blue",
        title: "1 · Store validates",
        body: "spec · condition · evidence",
        meta: "F32 — recommendation only",
      },
      {
        tone: "amber",
        title: "2 · You give verdict",
        body: "restock · relabel · quality-hold",
        meta: "binding · audit-logged",
      },
      {
        tone: "green",
        title: "3 · System executes",
        body: "stock + vendor register update",
        meta: "F33 · external event",
      },
    ],
    footnote: "A FAIL line can never re-enter stock — a PASS restores availability and reorder instantly",
  },
  attribution: {
    title: "Quality attribution",
    intro: "FAIL verdicts roll up per vendor with PO attribution (FB-16):",
    bullets: [
      { tone: "red", text: "SafeGuard — 2 poor · Sep · under review" },
      { tone: "blue", text: "Deccan — 1 poor · Sep · active" },
      { tone: "blue", text: "Events fire to purchasing: EF-0041 · EF-0038" },
    ],
  },
};

export const storeReturns: StoreReturns = {
  kpis: [
    { label: "Returns in flight", value: "5", hint: "3 requesters · 2 sites" },
    { label: "Awaiting my check", value: "1 line", badge: { label: "today", tone: "amber" } },
    { label: "Routed to quarantine", value: "3 lines", badge: { label: "validating", tone: "blue" } },
    { label: "Restocked · Sep", value: "1", badge: { label: "closed", tone: "green" } },
  ],
  rows: [
    {
      return_ref: "RET-0421",
      items_summary: "Seal kit ×1 · V-belt ×2",
      qty_display: "1 + 2",
      reason: "Poor + wrong",
      returned_by: "Rahul Verma",
      stage: "→ QTN-0031 · QTN-0027",
      state: { kind: "routed", label: "Routed" },
    },
    {
      return_ref: "RET-0419",
      items_summary: "V-Belt A-43",
      qty_display: "2",
      reason: "Wrong item",
      returned_by: "Kavita Rao",
      stage: "Spec check vs PO-2188",
      state: { kind: "validating", label: "Validating" },
    },
    {
      return_ref: "RET-0418",
      items_summary: "Safety Gloves (L)",
      qty_display: "6 pairs",
      reason: "Damaged",
      returned_by: "Rahul Verma",
      stage: "FAIL recommended",
      state: { kind: "overdue", label: "Overdue 1 d" },
    },
    {
      return_ref: "RET-0412",
      items_summary: "Safety Gloves (L)",
      qty_display: "2 pairs",
      reason: "Poor quality",
      returned_by: "Ananya Iyer",
      stage: "Quality-hold · F33",
      state: { kind: "claim_open", label: "Claim open" },
    },
    {
      return_ref: "RET-0409",
      items_summary: "Grease EP-2 5 kg",
      qty_display: "2 tubs",
      reason: "Mismatch",
      returned_by: "Kavita Rao",
      stage: "Checked · restocked",
      state: { kind: "closed", label: "Closed" },
    },
  ],
  validations: [
    {
      return_ref: "RET-0419",
      title: "Now validating — RET-0419 · V-Belt ×2",
      facts: [
        { label: "Return", value: "RET-0419 · Kavita Rao" },
        { label: "Reason", value: "Wrong item" },
        { label: "Ordered", value: "VBLT-A43 ×2 · PO-2188" },
        { label: "Supplied", value: "A-43L — one class off" },
      ],
      store_check: "Spec vs order + condition + issuance evidence — the requester's photos are attached.",
      // F32 names the two outcomes: "PASS — validated OK" and "FAIL — poor quality / damage".
      recommendation_options: ["PASS — spec equivalent · restock", "FAIL — poor quality / damage"],
      recommendation_default: "PASS — spec equivalent · restock",
    },
  ],
  selected_ref: "RET-0419",
  routing: {
    title: "Reason code → destination — the routing you execute",
    routes: [
      { tone: "blue", title: "Mismatch", body: "verify condition → restock", meta: "RET-0409 ✓ closed" },
      { tone: "violet", title: "Wrong item", body: "quarantine · spec validation", meta: "F32 · verdict by Type 2" },
      { tone: "red", title: "Poor quality", body: "quality-hold — never restocks", meta: "F33 · vendor register" },
      { tone: "amber", title: "Damaged", body: "hold · disposition configurable", meta: "F43 · scrap is default" },
    ],
  },
  never_back: {
    title: "Never back to stock",
    intro: "Poor-quality lines go to quality-hold — they can never re-enter stock (FB-14). They roll up per vendor:",
    bullets: [
      { tone: "red", text: "SafeGuard — 2.1% poor · under review" },
      { tone: "blue", text: "Deccan — 0.8% · claims ₹2,140 open (F33)" },
    ],
  },
};
