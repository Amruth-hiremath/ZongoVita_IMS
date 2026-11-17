import Link from "next/link";
import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";

import { cn } from "./cn";

/**
 * The five button treatments in the wireframes:
 *   primary    blue gradient, white bold label          ("Save item", "Approve & lock stock")
 *   secondary  white-to-gray gradient, gray border      ("Cancel", "Export")
 *   danger     white-to-pink gradient, red label        ("Reject", "Suspend")
 *   soft       pale blue fill, blue label, no border    ("Sync now", "Generate")
 *   link       plain blue text with optional arrow      ("Configure workflow →")
 */
export type ButtonVariant = "primary" | "secondary" | "danger" | "soft" | "link";
export type ButtonSize = "md" | "sm";

const base =
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md transition-[filter] " +
  "hover:brightness-[0.97] active:brightness-95 disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<ButtonVariant, string> = {
  primary: "border border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep font-semibold text-white",
  secondary: "border-[1.2px] border-gray-300 bg-linear-to-b from-white to-button-shade font-medium text-gray-700",
  danger: "border-[1.2px] border-red-200 bg-linear-to-b from-white to-danger-shade font-semibold text-red-700",
  soft: "bg-blue-50 font-semibold text-blue-600",
  link: "font-medium text-blue-600 hover:underline",
};

const sizes: Record<ButtonSize, string> = {
  md: "h-9 px-4 text-[13px]",
  sm: "h-7 px-3 text-[11.5px]",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", className?: string): string {
  return cn(base, variants[variant], variant === "link" ? "text-[12.5px]" : sizes[size], className);
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
}

export function Button({ variant = "secondary", size = "md", icon, className, children, type, ...rest }: ButtonProps) {
  return (
    <button type={type ?? "button"} className={buttonClass(variant, size, className)} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export interface ButtonLinkProps extends ComponentProps<typeof Link> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
}

export function ButtonLink({ variant = "secondary", size = "md", icon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
