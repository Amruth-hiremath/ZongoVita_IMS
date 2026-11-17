"use client";

import { Toggle } from "@ims/ui";
import { useState } from "react";

import type { ModuleFlag } from "@/data/config";

/**
 * Module flag switches of F53. They change on the page; nothing is stored until
 * "Save configuration" is connected.
 */
export function ModuleFlags({ flags }: { flags: ModuleFlag[] }) {
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(flags.map((flag) => [flag.flag_id, flag.enabled])),
  );

  return (
    <ul className="space-y-4">
      {flags.map((flag) => (
        <li key={flag.flag_id}>
          <Toggle
            checked={enabled[flag.flag_id] ?? false}
            onChange={(event) => setEnabled((current) => ({ ...current, [flag.flag_id]: event.target.checked }))}
            label={<span className="text-[12.5px] text-gray-700">{flag.label}</span>}
          />
        </li>
      ))}
    </ul>
  );
}
