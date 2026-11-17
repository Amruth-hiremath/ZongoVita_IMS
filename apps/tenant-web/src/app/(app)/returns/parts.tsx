import { NoteBox, Pill, StatCard, cn, type Tone } from "@ims/ui";

import type { Bullet, Kpi, ReturnState, ToneNote } from "@/data/returns";

export const stateTone: Record<ReturnState, Tone> = {
  verdict_due: "amber",
  spec_check: "blue",
  overdue: "red",
  claim_open: "violet",
  closed: "green",
  routed: "blue",
  validating: "blue",
};

const noteTitle: Record<ToneNote["tone"], string> = {
  blue: "text-blue-600",
  amber: "text-amber-700",
  green: "text-green-700",
  red: "text-red-700",
  violet: "text-violet-700",
};

export function KpiRow({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
      {kpis.map((kpi) => (
        <StatCard
          key={kpi.label}
          label={kpi.label}
          value={kpi.value}
          hint={kpi.hint}
          badge={kpi.badge ? <Pill tone={kpi.badge.tone}>{kpi.badge.label}</Pill> : undefined}
        />
      ))}
    </div>
  );
}

/** Tinted box with a coloured title, a body line and a small reference line. */
export function ToneNoteBox({ note, className }: { note: ToneNote; className?: string }) {
  return (
    <NoteBox tone={note.tone} className={cn("flex flex-col px-3.5 py-3", className)}>
      <p className={cn("text-[12px] font-semibold", noteTitle[note.tone])}>{note.title}</p>
      <p className="mt-1.5 text-[11.5px] leading-4 text-gray-700">{note.body}</p>
      <p className="mt-auto pt-3 text-[10px] text-gray-500">{note.meta}</p>
    </NoteBox>
  );
}

export function BulletList({ bullets }: { bullets: Bullet[] }) {
  return (
    <ul className="space-y-1">
      {bullets.map((bullet) => (
        <li
          key={bullet.text}
          className={cn(
            "flex items-center gap-3 text-[11.5px]",
            bullet.tone === "red" ? "text-red-700" : "text-gray-700",
          )}
        >
          <span
            aria-hidden
            className={cn("size-1.5 shrink-0 rounded-full", bullet.tone === "red" ? "bg-red-600" : "bg-blue-600")}
          />
          {bullet.text}
        </li>
      ))}
    </ul>
  );
}
