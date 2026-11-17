import { ChevronDown } from "lucide-react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "./cn";

const control =
  "h-10 w-full rounded-md border-[1.4px] border-gray-300 bg-white px-3.5 text-[13px] text-gray-900 " +
  "placeholder:text-gray-400 disabled:bg-gray-50 disabled:text-gray-500";

export interface FieldProps {
  /** Small-caps label above the control. */
  label: ReactNode;
  hint?: ReactNode;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

/** Label + control + optional hint, stacked. */
export function Field({ label, hint, htmlFor, className, children }: FieldProps) {
  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor={htmlFor} className="label-caps mb-2 block">
        {label}
      </label>
      {children}
      {hint ? <p className="mt-1 text-[11px] text-gray-500">{hint}</p> : null}
    </div>
  );
}

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  /** Icon or text inside the left edge (search glyph). */
  leading?: ReactNode;
  /** Unit or icon inside the right edge ("pcs", "days", a scan glyph). */
  trailing?: ReactNode;
  /** 32px tall instead of 40px, for inputs inside table rows and the top bar. */
  compact?: boolean;
}

export function Input({ leading, trailing, compact, className, ...rest }: InputProps) {
  const input = (
    <input
      className={cn(control, compact && "h-8 px-2.5", leading && "pl-9", trailing && "pr-12", className)}
      {...rest}
    />
  );
  if (!leading && !trailing) return input;
  return (
    <div className="relative">
      {leading ? (
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-gray-500">{leading}</span>
      ) : null}
      {input}
      {trailing ? (
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[11px] text-gray-500">
          {trailing}
        </span>
      ) : null}
    </div>
  );
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  leading?: ReactNode;
  compact?: boolean;
  /** Gray gradient face, as the scope selector in the top bar. */
  raised?: boolean;
}

/** Native select drawn with the design's chevron. */
export function Select({ leading, compact, raised, className, children, ...rest }: SelectProps) {
  return (
    <div className="relative">
      {leading ? (
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-gray-500">{leading}</span>
      ) : null}
      <select
        className={cn(
          control,
          "cursor-pointer pr-9",
          compact && "h-8 px-2.5",
          leading && "pl-9",
          raised && "bg-linear-to-b from-white to-button-shade",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-gray-500"
        strokeWidth={1.6}
      />
    </div>
  );
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, "h-auto min-h-[72px] py-2.5 leading-5", className)} {...rest} />;
}

export interface ToggleProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
}

/** Switch: blue track with a white knob when on, gray when off. */
export function Toggle({ label, className, ...rest }: ToggleProps) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-3 text-[13px] text-gray-700", className)}>
      <span className="relative inline-flex">
        <input type="checkbox" className="peer sr-only" {...rest} />
        <span className="h-[22px] w-11 rounded-full bg-gray-300 transition-colors peer-checked:bg-linear-to-b peer-checked:from-blue-600 peer-checked:to-brand-deep peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-blue-600" />
        <span className="absolute left-[3px] top-[3px] size-4 rounded-full bg-white transition-transform peer-checked:translate-x-[22px]" />
      </span>
      {label}
    </label>
  );
}

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
}

/** Square checkbox with the blue outline used in the matrices and checklists. */
export function Checkbox({ label, className, ...rest }: CheckboxProps) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-2.5 text-[12.5px] text-gray-700", className)}>
      <input
        type="checkbox"
        className="size-4 cursor-pointer appearance-none rounded-[3px] border-[1.5px] border-gray-300 bg-white bg-center bg-no-repeat checked:border-blue-600 checked:bg-blue-50 checked:bg-[url('data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2016%2016%22%3E%3Cpath%20d%3D%22M3.5%208.3l3%203%206-6.6%22%20fill%3D%22none%22%20stroke%3D%22%232563eb%22%20stroke-width%3D%221.8%22%2F%3E%3C%2Fsvg%3E')] disabled:cursor-not-allowed disabled:opacity-60"
        {...rest}
      />
      {label}
    </label>
  );
}
