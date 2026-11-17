import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";

import { cn } from "./cn";

type Align = "left" | "right" | "center";

const aligns: Record<Align, string> = { left: "text-left", right: "text-right", center: "text-center" };

/**
 * The scroll wrapper is positioned so that absolutely positioned descendants (screen-reader-only
 * header labels) stay inside it instead of widening the page on narrow screens.
 *
 * Table primitives matching the frames: a tinted header row with small bold labels, 46px body
 * rows separated by hairlines, and an optional zebra tint.
 *
 *   <Table>
 *     <THead><TR><TH>SKU</TH><TH align="right">On hand</TH></TR></THead>
 *     <TBody>{rows.map(r => <TR key={r.sku}><TD>{r.sku}</TD><TD align="right" numeric>{r.on_hand}</TD></TR>)}</TBody>
 *   </Table>
 */
export function Table({ className, children, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table className={cn("w-full border-collapse text-[13px]", className)} {...rest}>
        {children}
      </table>
    </div>
  );
}

export function THead({ className, children, ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn("bg-gray-50", className)} {...rest}>
      {children}
    </thead>
  );
}

export interface TBodyProps extends HTMLAttributes<HTMLTableSectionElement> {
  /** Tint every second row, as the list screens do. */
  zebra?: boolean;
}

export function TBody({ zebra, className, children, ...rest }: TBodyProps) {
  return (
    <tbody className={cn(zebra && "[&>tr:nth-child(even)]:bg-surface-alt", className)} {...rest}>
      {children}
    </tbody>
  );
}

export function TR({ className, children, ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn("border-b border-gray-200", className)} {...rest}>
      {children}
    </tr>
  );
}

export interface THProps extends ThHTMLAttributes<HTMLTableCellElement> {
  align?: Align;
}

export function TH({ align = "left", className, children, ...rest }: THProps) {
  return (
    <th
      scope="col"
      className={cn(
        "h-10 whitespace-nowrap border-b-[1.4px] border-gray-300 px-3.5 text-[11px] font-semibold text-gray-700",
        aligns[align],
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export interface TDProps extends TdHTMLAttributes<HTMLTableCellElement> {
  align?: Align;
  /** Tabular figures for quantities and money. */
  numeric?: boolean;
  /** Secondary information: smaller and gray. */
  muted?: boolean;
  /** Emphasised cell (item names in summary tables). */
  strong?: boolean;
}

export function TD({ align = "left", numeric, muted, strong, className, children, ...rest }: TDProps) {
  return (
    <td
      className={cn(
        "h-[46px] px-3.5",
        aligns[align],
        numeric && "tabular",
        muted ? "text-[11.5px] text-gray-500" : "text-gray-900",
        strong && "font-semibold",
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  );
}
