import { Bell, MapPin, Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { NoticeProvider } from "./feedback";
import { Select } from "./form";
import { SidebarNav, type NavItem } from "./sidebar-nav";

export interface ShellUser {
  name: string;
  /** Second line under the name, e.g. "Super Admin · Type 1". */
  role: string;
  initials: string;
}

export interface ShellScope {
  /** Options of the scope selector (locations for a customer, enterprises for the platform). */
  options: { value: string; label: string }[];
  value: string;
  ariaLabel: string;
}

export interface AppShellProps {
  nav: NavItem[];
  /** Small-caps line at the foot of the sidebar, e.g. "TYPE 1 · ARJUN MEHTA". */
  footer: string;
  user: ShellUser;
  scope: ShellScope;
  /** Unread notifications; null when the count is not available (no badge is drawn). */
  notificationCount: number | null;
  homeHref: string;
  /** Strip rendered above the top bar (licence banners, fixture-mode marker). */
  banner?: ReactNode;
  children: ReactNode;
}

/**
 * The frame shared by every signed-in screen: a 60px top bar (brand, global search, scope
 * selector, notifications, user) over a 240px sidebar and the page content with a 32px gutter.
 * Below the `lg` breakpoint the sidebar turns into a horizontal strip under the top bar.
 */
export function AppShell({ nav, footer, user, scope, notificationCount, homeHref, banner, children }: AppShellProps) {
  return (
    <NoticeProvider>
      <div className="flex min-h-screen flex-col">
        {banner}
        <header className="sticky top-0 z-30 flex h-topbar shrink-0 items-center border-y border-gray-200 bg-white pl-6 pr-4">
          <Link href={homeHref} className="flex w-[296px] shrink-0 items-center gap-3 max-lg:w-auto max-lg:pr-4">
            <span className="flex size-7 items-center justify-center rounded-md bg-gray-900 text-[13px] font-bold text-white">
              I
            </span>
            <span className="text-[15px] font-bold tracking-tight text-gray-900">IMS</span>
          </Link>

          <form role="search" action="#" className="relative w-[300px] max-md:hidden">
            <Search
              aria-hidden
              className="pointer-events-none absolute left-3.5 top-1/2 size-3.5 -translate-y-1/2 text-gray-500"
              strokeWidth={1.6}
            />
            <input
              type="search"
              name="q"
              aria-label="Search"
              placeholder="Search items, SKUs, transactions…"
              className="h-8 w-full rounded-md border border-gray-300 bg-white pl-10 pr-3 text-[12px] text-gray-900 placeholder:text-gray-400"
            />
          </form>

          <div className="ml-auto flex items-center">
            <div className="w-[216px] max-sm:hidden">
              <Select
                compact
                raised
                aria-label={scope.ariaLabel}
                defaultValue={scope.value}
                leading={<MapPin className="size-3.5" strokeWidth={1.6} />}
                className="border pl-8 pr-7 text-[12px] text-gray-700"
              >
                {scope.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <button
              type="button"
              aria-label={notificationCount === null ? "Notifications" : `Notifications: ${notificationCount} unread`}
              className="relative ml-[34px] p-1.5 max-sm:ml-2"
            >
              <Bell className="size-4 text-gray-700" strokeWidth={2} />
              {notificationCount !== null && notificationCount > 0 ? (
                <span className="absolute -top-1 right-0 flex size-4 items-center justify-center rounded-full bg-red-700 text-[9px] font-bold text-white">
                  {notificationCount}
                </span>
              ) : null}
            </button>

            <div className="ml-[77px] flex min-w-[130px] items-center gap-2.5 max-md:ml-4 max-sm:min-w-0">
              <span className="flex size-[26px] shrink-0 items-center justify-center rounded-full border border-gray-300 bg-gray-50 text-[9px] font-bold text-gray-700">
                {user.initials}
              </span>
              <span className="min-w-0 leading-tight max-sm:hidden">
                <span className="block truncate text-[12.5px] text-gray-900">{user.name}</span>
                <span className="block whitespace-nowrap text-[10px] text-gray-500">{user.role}</span>
              </span>
            </div>
          </div>
        </header>

        <div className="flex flex-1 max-lg:flex-col">
          <aside className="flex w-sidebar shrink-0 flex-col border-r border-gray-200 bg-gray-50 max-lg:w-full max-lg:border-b max-lg:border-r-0">
            <div className="label-caps px-6 pb-3 pt-[18px] text-gray-500 max-lg:hidden">Menu</div>
            <SidebarNav items={nav} />
            <div className="mx-4 mt-auto border-t border-gray-200 px-2 pb-6 pt-4 text-[10px] uppercase tracking-wide text-gray-400 max-lg:hidden">
              {footer}
            </div>
          </aside>
          <main className="min-w-0 flex-1 px-8 pb-10 pt-3 max-sm:px-4">{children}</main>
        </div>
      </div>
    </NoticeProvider>
  );
}
