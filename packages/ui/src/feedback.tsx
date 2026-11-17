"use client";

import { AlertTriangle, Check, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { cn } from "./cn";

type CalloutTone = "info" | "warning" | "danger" | "success";

const calloutTones: Record<CalloutTone, string> = {
  info: "border-blue-200 bg-blue-50 text-gray-700",
  warning: "border-amber-200 bg-amber-50 text-gray-700",
  danger: "border-red-200 bg-red-50 text-red-700",
  success: "border-green-200 bg-green-50 text-gray-700",
};

const calloutIcons: Record<CalloutTone, ReactNode> = {
  info: <Info className="size-4 text-blue-600" strokeWidth={1.6} />,
  warning: <AlertTriangle className="size-4 text-amber-700" strokeWidth={1.6} />,
  danger: <AlertTriangle className="size-4 text-red-700" strokeWidth={1.6} />,
  success: <Check className="size-4 text-green-700" strokeWidth={1.8} />,
};

export interface CalloutProps {
  tone?: CalloutTone;
  /** Show the × at the right edge; the bar hides itself when pressed. */
  dismissible?: boolean;
  className?: string;
  children: ReactNode;
}

/** Full-width tinted bar with a leading glyph, as used for policy and state notes. */
export function Callout({ tone = "info", dismissible, className, children }: CalloutProps) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div
      role={tone === "danger" || tone === "warning" ? "alert" : "note"}
      className={cn(
        "flex min-h-10 items-center gap-2.5 rounded-md border-[1.4px] px-3.5 py-2 text-[12.5px]",
        calloutTones[tone],
        className,
      )}
    >
      <span className="shrink-0">{calloutIcons[tone]}</span>
      <div className="min-w-0 flex-1">{children}</div>
      {dismissible ? (
        <button type="button" aria-label="Dismiss" className="shrink-0 text-gray-500" onClick={() => setOpen(false)}>
          <X className="size-3.5" strokeWidth={1.6} />
        </button>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------------------------ notices

interface Notice {
  id: number;
  title: string;
  detail?: string;
}

const NoticeContext = createContext<((title: string, detail?: string) => void) | null>(null);

/** Hosts short-lived notices in the bottom-right corner. Mount once, in the app shell. */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([]);

  const push = useCallback((title: string, detail?: string) => {
    setNotices((current) => [...current.slice(-2), { id: Date.now() + Math.random(), title, detail }]);
  }, []);

  useEffect(() => {
    if (notices.length === 0) return;
    const timer = setTimeout(() => setNotices((current) => current.slice(1)), 6000);
    return () => clearTimeout(timer);
  }, [notices]);

  const value = useMemo(() => push, [push]);

  return (
    <NoticeContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[340px] flex-col gap-2">
        {notices.map((notice) => (
          <div
            key={notice.id}
            className="pointer-events-auto rounded-lg border-[1.4px] border-gray-300 bg-white p-3.5 shadow-lg"
          >
            <div className="flex items-start gap-2.5">
              <Info className="mt-0.5 size-4 shrink-0 text-blue-600" strokeWidth={1.6} />
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] font-semibold text-gray-900">{notice.title}</p>
                {notice.detail ? <p className="mt-0.5 break-words text-[11.5px] text-gray-500">{notice.detail}</p> : null}
              </div>
              <button
                type="button"
                aria-label="Dismiss"
                className="text-gray-500"
                onClick={() => setNotices((current) => current.filter((n) => n.id !== notice.id))}
              >
                <X className="size-3.5" strokeWidth={1.6} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </NoticeContext.Provider>
  );
}

/** Show a notice from a client component. Outside a provider it is a no-op. */
export function useNotice(): (title: string, detail?: string) => void {
  return useContext(NoticeContext) ?? (() => undefined);
}

// -------------------------------------------------------------------------------------- modal

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  /** Buttons row at the bottom. */
  footer?: ReactNode;
  className?: string;
}

/** Centred dialog over a dimmed page (the "Cannot issue 40 pcs" guard-rail in F12). */
export function Modal({ open, onClose, title, children, footer, className }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-900/35 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className={cn("w-full max-w-[560px] rounded-lg border-[1.4px] border-gray-300 bg-white p-6 shadow-xl", className)}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-[15px] font-semibold text-gray-900">{title}</h2>
          <button type="button" aria-label="Close" className="text-gray-500" onClick={onClose}>
            <X className="size-4" strokeWidth={1.6} />
          </button>
        </div>
        <div className="mt-3">{children}</div>
        {footer ? <div className="mt-5 flex flex-wrap items-center gap-2.5">{footer}</div> : null}
      </div>
    </div>
  );
}
