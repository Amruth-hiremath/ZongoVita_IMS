"use client";

import { useState } from "react";

import { cn } from "./cn";

export interface PaginationProps {
  /** Page tokens exactly as shown, for example [1, 2, "…", 9, 10]. */
  pages: (number | "…")[];
  /** Current page. With onSelect the parent controls it; without, it is the starting page. */
  current: number;
  onSelect?: (page: number) => void;
  onNext?: () => void;
  className?: string;
}

/**
 * Numbered page buttons with a trailing "Next", as under every list.
 *
 * Usable straight from a server component: without handlers it keeps the highlighted page
 * itself. Fetching another page belongs to the list's endpoint (cursor pagination, LLD 12).
 */
export function Pagination({ pages, current, onSelect, onNext, className }: PaginationProps) {
  const [internal, setInternal] = useState(current);
  const active = onSelect ? current : internal;
  const numbers = pages.filter((token): token is number => token !== "…");

  const select = (page: number) => {
    setInternal(page);
    onSelect?.(page);
  };
  const next = () => {
    if (onNext) return onNext();
    const following = numbers.find((page) => page > active);
    if (following !== undefined) select(following);
  };

  const box = "inline-flex h-[30px] min-w-[30px] items-center justify-center rounded-md border-[1.1px] px-2 text-[12px]";
  return (
    <nav aria-label="Pagination" className={cn("flex items-center gap-1.5", className)}>
      {pages.map((page, index) =>
        page === "…" ? (
          <span key={`gap-${index}`} className={cn(box, "border-gray-300 text-gray-500")}>
            …
          </span>
        ) : (
          <button
            key={page}
            type="button"
            aria-current={page === active ? "page" : undefined}
            onClick={() => select(page)}
            className={cn(
              box,
              page === active
                ? "border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep font-semibold text-white"
                : "border-gray-300 bg-white text-gray-700",
            )}
          >
            {page}
          </button>
        ),
      )}
      <button type="button" onClick={next} className={cn(box, "border-gray-300 bg-white px-3.5 text-gray-700")}>
        Next
      </button>
    </nav>
  );
}
