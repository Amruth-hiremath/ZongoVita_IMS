import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

/**
 * Status pills. Tone carries meaning consistently across every screen:
 *   green  good / done          amber  needs attention soon     red  problem / blocked
 *   blue   informational state  violet external or linked       gray neutral / closed
 *   dark   terminal or selected (e.g. "Dead 180 d", the active filter chip)
 */
export type Tone = "green" | "amber" | "red" | "blue" | "violet" | "gray" | "dark";

const tones: Record<Tone, string> = {
  green: "border-green-200 bg-green-50 text-green-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  red: "border-red-200 bg-red-50 text-red-700",
  blue: "border-blue-200 bg-blue-50 text-blue-600",
  violet: "border-violet-200 bg-violet-50 text-violet-700",
  gray: "border-gray-300 bg-white text-gray-700",
  dark: "border-gray-900 bg-gray-900 text-white",
};

export interface PillProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  /** Slightly smaller, for dense tables. */
  small?: boolean;
}

export function Pill({ tone = "gray", small, className, children }: PillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border font-semibold",
        small ? "h-5 px-2 text-[10px]" : "h-[22px] px-2.5 text-[11px]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Tone when not selected; the selected chip is always the dark tone. */
  tone?: Tone;
  selected?: boolean;
  children: ReactNode;
}

/** Selectable filter chip (the "All · Below min · Expiring · Dead" row above lists). */
export function Chip({ tone = "gray", selected, className, children, ...rest }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "inline-flex h-6 items-center whitespace-nowrap rounded-full border px-3 text-[11px] font-semibold",
        tones[selected ? "dark" : tone],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
