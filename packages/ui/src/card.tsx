import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";
import type { Tone } from "./pill";

/** White panel with the 1.4px gray border and 8px radius used for every card in the frames. */
export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-lg border-[1.4px] border-gray-300 bg-white", className)} {...rest}>
      {children}
    </div>
  );
}

export interface CardHeaderProps {
  title: ReactNode;
  /** Right-aligned link, pill or button. */
  action?: ReactNode;
  className?: string;
}

export function CardHeader({ title, action, className }: CardHeaderProps) {
  return (
    <div className={cn("flex items-center justify-between gap-3 px-4 pt-4", className)}>
      <h2 className="text-[13.5px] font-semibold text-gray-900">{title}</h2>
      {action}
    </div>
  );
}

export function CardBody({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("p-4", className)} {...rest}>
      {children}
    </div>
  );
}

export interface StatCardProps {
  label: string;
  value: ReactNode;
  /** Small gray line under the value. */
  hint?: ReactNode;
  /** Pill under the value (used instead of, or as well as, the hint). */
  badge?: ReactNode;
  className?: string;
}

/** KPI tile: small-caps label, large value, then a hint line or a pill. */
export function StatCard({ label, value, hint, badge, className }: StatCardProps) {
  return (
    <Card className={cn("flex min-h-[96px] flex-col px-4 pb-3 pt-4", className)}>
      <div className="label-caps">{label}</div>
      <div className="tabular mt-1.5 text-[24px] font-bold leading-8 text-gray-900">{value}</div>
      {hint ? <div className="text-[11px] leading-4 text-gray-500">{hint}</div> : null}
      {badge ? <div className="mt-0.5">{badge}</div> : null}
    </Card>
  );
}

/** Small-caps heading that sits directly above a table or a group of fields. */
export function SectionLabel({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("label-caps", className)} {...rest}>
      {children}
    </div>
  );
}

export interface KeyValueProps {
  label: ReactNode;
  children: ReactNode;
  className?: string;
}

/** One "label ........ value" row (gray label left, value right). */
export function KeyValue({ label, children, className }: KeyValueProps) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-1.5 text-[12.5px]", className)}>
      <dt className="shrink-0 text-gray-500">{label}</dt>
      <dd className="text-right text-gray-900">{children}</dd>
    </div>
  );
}

const noteTones: Record<Exclude<Tone, "dark" | "gray"> | "gray", string> = {
  blue: "border-blue-200 bg-blue-50",
  amber: "border-amber-200 bg-amber-50",
  green: "border-green-200 bg-green-50",
  red: "border-red-200 bg-red-50",
  violet: "border-violet-200 bg-violet-50",
  gray: "border-gray-200 bg-gray-50",
};

export interface NoteBoxProps extends HTMLAttributes<HTMLDivElement> {
  tone?: keyof typeof noteTones;
}

/** Tinted box for an explanatory step or highlight inside a card. */
export function NoteBox({ tone = "blue", className, children, ...rest }: NoteBoxProps) {
  return (
    <div className={cn("rounded-md border-[1.4px] p-3", noteTones[tone], className)} {...rest}>
      {children}
    </div>
  );
}
