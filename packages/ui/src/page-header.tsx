import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "./cn";

export interface Crumb {
  label: string;
  href?: string;
}

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  /** Trail above the title on detail screens ("Vendors › VD-0028"). */
  breadcrumbs?: Crumb[];
  /** Pills shown under the title on detail screens. */
  badges?: ReactNode;
  /** Buttons at the right, primary action last. */
  actions?: ReactNode;
  /** Thumbnail or icon box to the left of the title (Item Detail). */
  leading?: ReactNode;
  className?: string;
}

/** Page title block: 21px bold title, gray one-line subtitle, actions aligned right. */
export function PageHeader({ title, subtitle, breadcrumbs, badges, actions, leading, className }: PageHeaderProps) {
  return (
    <div className={cn("mb-5 flex items-start justify-between gap-6 max-md:flex-col", className)}>
      <div className="flex min-w-0 items-start gap-4">
        {leading}
        <div className="min-w-0">
          {breadcrumbs && breadcrumbs.length > 0 ? (
            <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-[11.5px] text-gray-500">
              {breadcrumbs.map((crumb, index) => {
                const last = index === breadcrumbs.length - 1;
                return (
                  <span key={`${crumb.label}-${index}`} className="flex items-center gap-1.5">
                    {crumb.href && !last ? (
                      <Link href={crumb.href} className="hover:text-gray-700">
                        {crumb.label}
                      </Link>
                    ) : (
                      <span className={cn(last && "font-semibold text-gray-900")}>{crumb.label}</span>
                    )}
                    {last ? null : <ChevronRight aria-hidden className="size-3" strokeWidth={1.6} />}
                  </span>
                );
              })}
            </nav>
          ) : null}
          <h1 className="mt-1 text-[21px] font-bold leading-7 tracking-[-0.01em] text-gray-900">{title}</h1>
          {subtitle ? <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">{subtitle}</p> : null}
          {badges ? <div className="mt-2 flex flex-wrap items-center gap-2">{badges}</div> : null}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}
