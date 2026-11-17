import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export interface TimelineEntry {
  title: ReactNode;
  /** Gray line under the title: who, when, where. */
  meta?: ReactNode;
}

export interface TimelineProps {
  entries: TimelineEntry[];
  /** The first entry gets the filled blue dot (the latest event). Default true. */
  highlightFirst?: boolean;
  className?: string;
}

/** Vertical list of events joined by a hairline, newest first. */
export function Timeline({ entries, highlightFirst = true, className }: TimelineProps) {
  return (
    <ol className={cn("relative", className)}>
      {entries.map((entry, index) => (
        <li key={index} className="relative flex gap-3.5 pb-4 last:pb-0">
          {index < entries.length - 1 ? (
            <span aria-hidden className="absolute bottom-0 left-[5px] top-3 w-px bg-gray-300" />
          ) : null}
          <span
            aria-hidden
            className={cn(
              "relative mt-1 size-[11px] shrink-0 rounded-full border-[1.4px]",
              highlightFirst && index === 0 ? "border-blue-600 bg-blue-600" : "border-gray-300 bg-white",
            )}
          />
          <div className="min-w-0">
            <p className="text-[13px] leading-5 text-gray-900">{entry.title}</p>
            {entry.meta ? <p className="text-[11px] leading-4 text-gray-500">{entry.meta}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export type StepState = "done" | "current" | "upcoming";

export interface Step {
  label: ReactNode;
  /** Gray line under the label (date, status). */
  meta?: ReactNode;
  state: StepState;
}

export interface StepperProps {
  steps: Step[];
  className?: string;
}

/** Horizontal numbered steps joined by a line: check when done, filled blue when current. */
export function Stepper({ steps, className }: StepperProps) {
  return (
    <ol className={cn("flex w-full items-start", className)}>
      {steps.map((step, index) => (
        <li key={index} className="relative flex flex-1 flex-col items-center text-center">
          {index > 0 ? (
            <span
              aria-hidden
              className={cn(
                "absolute right-1/2 top-[11px] h-px w-full",
                steps[index - 1]?.state === "upcoming" || step.state === "upcoming" ? "bg-gray-300" : "bg-gray-400",
              )}
            />
          ) : null}
          <span
            className={cn(
              "relative z-10 flex size-[22px] items-center justify-center rounded-full border-[1.4px] text-[10.5px] font-semibold",
              step.state === "current" && "border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep text-white",
              step.state === "done" && "border-gray-400 bg-white text-gray-700",
              step.state === "upcoming" && "border-gray-300 bg-white text-gray-500",
            )}
          >
            {step.state === "done" ? <Check className="size-3" strokeWidth={2.2} /> : index + 1}
          </span>
          <span
            className={cn(
              "mt-2 text-[11.5px] font-semibold",
              step.state === "current" ? "text-blue-600" : "text-gray-700",
            )}
          >
            {step.label}
          </span>
          {step.meta ? <span className="text-[10.5px] text-gray-500">{step.meta}</span> : null}
        </li>
      ))}
    </ol>
  );
}

export interface MeterProps {
  /** 0 to 100. */
  percent: number;
  label?: string;
  className?: string;
}

/**
 * Thin progress bar. Drawn as SVG so the fill width is an attribute, not an inline style:
 * the apps run under a strict Content Security Policy that forbids inline styles.
 */
export function Meter({ percent, label, className }: MeterProps) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <svg
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={label}
      className={cn("block h-1.5 w-full", className)}
      preserveAspectRatio="none"
    >
      <rect width="100%" height="100%" rx="3" className="fill-gray-200" />
      <rect width={`${clamped}%`} height="100%" rx="3" className="fill-gray-900" />
    </svg>
  );
}
