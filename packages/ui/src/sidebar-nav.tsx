"use client";

import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  BarChart3,
  Box,
  Building2,
  Check,
  ClipboardList,
  Clock,
  KeyRound,
  LayoutGrid,
  MapPin,
  RotateCcw,
  ScanLine,
  Send,
  Settings,
  Shield,
  Tag,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "./cn";

/** Icon names a navigation entry may use; the set drawn in the wireframe sidebars. */
export const navIcons = {
  dashboard: LayoutGrid,
  items: Box,
  categories: Tag,
  vendors: Building2,
  quality: AlertTriangle,
  locations: MapPin,
  users: Users,
  privileges: KeyRound,
  approvals: Check,
  audit: Shield,
  settings: Settings,
  receive: ArrowDownToLine,
  issuance: ArrowUpFromLine,
  returns: RotateCcw,
  transfers: Truck,
  counts: ClipboardList,
  alerts: AlertTriangle,
  reports: BarChart3,
  fulfilment: Send,
  scan: ScanLine,
  quarantine: Clock,
} satisfies Record<string, LucideIcon>;

export type NavIconName = keyof typeof navIcons;

export interface NavItem {
  label: string;
  href: string;
  icon: NavIconName;
  /** Other path prefixes that keep this entry highlighted (detail and sub-screens). */
  match?: string[];
}

function isActive(pathname: string, item: NavItem): boolean {
  const prefixes = [item.href, ...(item.match ?? [])];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * Sidebar entries. Each is a 36px row; the current one carries the blue bar at its left edge,
 * a blue glow fading to the right, and a bold blue label.
 */
export function SidebarNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  // When several entries match (e.g. /approvals and /approvals/configuration), the longest wins.
  const active = items
    .filter((item) => isActive(pathname, item))
    .sort((a, b) => b.href.length - a.href.length)[0];

  return (
    <nav aria-label="Main" className="flex flex-col gap-2 px-2 max-lg:flex-row max-lg:overflow-x-auto max-lg:py-2">
      {items.map((item) => {
        const Icon = navIcons[item.icon];
        const current = item === active;
        return (
          <Link
            key={item.href}
            href={item.href}
            // Every screen is rendered per user on the server; prefetching the whole menu on each
            // page view would multiply that work for no gain.
            prefetch={false}
            aria-current={current ? "page" : undefined}
            className={cn(
              "relative flex h-9 shrink-0 items-center gap-2.5 rounded-md pl-[18px] pr-3 text-[13px]",
              current
                ? "bg-linear-to-r from-nav-glow to-nav-fade font-semibold text-blue-600"
                : "text-gray-700 hover:bg-gray-100",
            )}
          >
            {current ? <span aria-hidden className="absolute inset-y-[7px] left-0 w-[3px] bg-blue-600" /> : null}
            <Icon aria-hidden className={cn("size-4 shrink-0", current ? "text-blue-600" : "text-gray-500")} strokeWidth={2} />
            <span className="whitespace-nowrap">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
