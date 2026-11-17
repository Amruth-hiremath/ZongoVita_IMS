"use client";

import { useState, type ReactNode } from "react";

import { cn } from "./cn";

export interface TabItem {
  id: string;
  label: ReactNode;
  /** Panel shown while this tab is selected. Omit when the parent renders the content itself. */
  content?: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  /**
   * underline  text tabs with a blue rule under the selected one (Item Detail, Vendor Detail)
   * segmented  boxed group where the selected tab is a white pill (Manual entry / From suggestion)
   */
  variant?: "underline" | "segmented";
  defaultId?: string;
  /** Controlled selection. */
  value?: string;
  onChange?: (id: string) => void;
  className?: string;
  panelClassName?: string;
}

export function Tabs({ items, variant = "underline", defaultId, value, onChange, className, panelClassName }: TabsProps) {
  const [internal, setInternal] = useState(defaultId ?? items[0]?.id ?? "");
  const selected = value ?? internal;
  const active = items.find((item) => item.id === selected);

  const select = (id: string) => {
    setInternal(id);
    onChange?.(id);
  };

  return (
    <div className="min-w-0 max-w-full">
      <div
        role="tablist"
        className={cn(
          variant === "underline"
            ? "flex max-w-full gap-9 overflow-x-auto border-b border-gray-200"
            : "inline-flex max-w-full gap-1 overflow-x-auto rounded-md border-[1.4px] border-gray-300 bg-white p-[3px]",
          className,
        )}
      >
        {items.map((item) => {
          const isActive = item.id === selected;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => select(item.id)}
              className={cn(
                "whitespace-nowrap text-[12.5px]",
                variant === "underline"
                  ? cn(
                      "-mb-px border-b-2 pb-2",
                      isActive ? "border-blue-600 font-semibold text-blue-600" : "border-transparent text-gray-500",
                    )
                  : cn(
                      "h-[30px] rounded-[5px] px-3.5",
                      isActive
                        ? "border-[1.4px] border-blue-200 bg-white font-semibold text-blue-600"
                        : "border-[1.4px] border-transparent text-gray-500",
                    ),
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {active?.content !== undefined ? (
        <div role="tabpanel" className={panelClassName}>
          {active.content}
        </div>
      ) : null}
    </div>
  );
}
