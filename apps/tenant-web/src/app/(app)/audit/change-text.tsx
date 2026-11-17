import { cn } from "@ims/ui";

import type { AuditChange } from "@/data/audit";
import { formatQty } from "@/lib/format";

/** The Change column of the audit frames: bold "52 → 48 pcs", green / red outcomes, gray words. */
export function ChangeText({ change }: { change: AuditChange }) {
  if (change.kind === "quantity") {
    return (
      <span className="tabular text-[13.5px] font-bold text-gray-700">
        {formatQty(change.from)} → {formatQty(change.to)} {change.uom}
      </span>
    );
  }
  return (
    <span
      className={cn(
        change.tone === "good" && "text-[13.5px] font-bold text-green-700",
        change.tone === "bad" && "text-[13.5px] font-bold text-red-700",
        change.tone === "plain" && "text-[11.5px] text-gray-500",
      )}
    >
      {change.text}
    </span>
  );
}
