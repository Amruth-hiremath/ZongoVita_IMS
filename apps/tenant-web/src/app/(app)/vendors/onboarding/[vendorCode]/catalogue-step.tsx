"use client";

import { Input, TBody, TD, TH, THead, TR, Table } from "@ims/ui";
import { Plus } from "lucide-react";
import { useState } from "react";

import type { OnboardingDraft } from "@/data/vendors";

type Line = OnboardingDraft["catalogue"][number] & { key: string };

/**
 * Step 2 of F39: the catalogue lines are editable in place and "Add supplied item" appends a
 * blank line. Nothing is stored until "Save draft" (PATCH /ui/v1/vendors/{id}) is connected;
 * the item name of a new line comes from the SKU lookup once GET /ui/v1/items is wired here.
 */
export function CatalogueStep({ lines: initial }: { lines: OnboardingDraft["catalogue"] }) {
  const [lines, setLines] = useState<Line[]>(() => initial.map((line) => ({ ...line, key: line.vendor_item_code })));

  const update = (key: string, field: "vendor_item_code" | "item_code" | "moq" | "rate", value: string) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, [field]: value } : line)));

  const add = () =>
    setLines((current) => [
      ...current,
      { key: `new-${current.length}`, vendor_item_code: "", item_code: "", item_name: "", moq: "", rate: "" },
    ]);

  return (
    <>
      <div className="mt-6">
        <Table>
          <THead>
            <TR>
              <TH>Vendor code</TH>
              <TH>Our SKU · link</TH>
              <TH>Item</TH>
              <TH align="center">MOQ</TH>
              <TH align="right">Rate (₹)</TH>
            </TR>
          </THead>
          <TBody zebra>
            {lines.map((line, index) => (
              <TR key={line.key}>
                <TD className="h-[52px] pr-0">
                  <Input
                    compact
                    aria-label={`Vendor code, line ${index + 1}`}
                    className="w-[92px] px-1.5 text-[12.5px]"
                    value={line.vendor_item_code}
                    onChange={(event) => update(line.key, "vendor_item_code", event.target.value)}
                  />
                </TD>
                <TD className="h-[52px] pr-0">
                  <Input
                    compact
                    aria-label={`Our SKU, line ${index + 1}`}
                    className="w-[94px] text-[12.5px]"
                    value={line.item_code}
                    onChange={(event) => update(line.key, "item_code", event.target.value)}
                  />
                </TD>
                <TD className="h-[52px]">{line.item_name === "" ? <span className="text-gray-400">—</span> : line.item_name}</TD>
                <TD align="center" className="h-[52px]">
                  <Input
                    compact
                    inputMode="decimal"
                    aria-label={`MOQ, line ${index + 1}`}
                    className="mx-auto w-[90px] text-[12.5px]"
                    value={line.moq}
                    onChange={(event) => update(line.key, "moq", event.target.value)}
                  />
                </TD>
                <TD align="right" className="h-[52px]">
                  <div className="relative ml-auto w-[90px]">
                    <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-[12.5px] text-gray-900">
                      ₹
                    </span>
                    <Input
                      compact
                      inputMode="decimal"
                      aria-label={`Rate, line ${index + 1}`}
                      className="pl-5 text-[12.5px]"
                      value={line.rate}
                      onChange={(event) => update(line.key, "rate", event.target.value)}
                    />
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <button
        type="button"
        onClick={add}
        className="mx-4 mt-6 flex h-12 w-[calc(100%-2rem)] items-center gap-3 rounded-md border-[1.4px] border-dashed border-blue-200 px-6 text-[12.5px] font-semibold text-blue-600 hover:bg-blue-50"
      >
        <Plus aria-hidden className="size-4" strokeWidth={1.8} />
        Add supplied item — vendor code, our SKU, MOQ, rate
      </button>
    </>
  );
}
