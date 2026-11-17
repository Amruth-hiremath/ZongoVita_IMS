import { Card, cn } from "@ims/ui";
import { ArrowRight } from "lucide-react";

/**
 * F37 "Vendor lifecycle": four left-aligned stages joined by an arrowed rule. The kit's Stepper
 * centres its labels and carries no description line, so this strip is drawn here with the same
 * tokens (circle and gradient as Stepper's current step).
 */
const stages = [
  { title: "Onboarding", text: "registration · catalogue & MOQ · rate list · lead times (F39)" },
  { title: "Active", text: "selectable as a purchase source across the tenant" },
  { title: "Under review", text: "quality rollups inform the decision (F33)" },
  { title: "Suspended / retired", text: "kept for history — never deleted" },
];

export function VendorLifecycle() {
  return (
    <Card className="mt-6 max-w-[1136px] px-4 pb-4 pt-4">
      <h2 className="text-[13.5px] font-semibold text-gray-900">Vendor lifecycle</h2>
      <ol className="mt-3 grid grid-cols-4 gap-y-5 max-lg:grid-cols-2 max-sm:grid-cols-1">
        {stages.map((stage, index) => (
          <li key={stage.title} className="min-w-0 pr-6">
            <div className="flex items-center">
              <span
                className={cn(
                  "flex size-[22px] shrink-0 items-center justify-center rounded-full border-[1.4px] text-[10.5px] font-semibold",
                  index === 0
                    ? "border-brand-deep bg-linear-to-b from-blue-600 to-brand-deep text-white"
                    : "border-gray-300 bg-white text-gray-700",
                )}
              >
                {index + 1}
              </span>
              {index < stages.length - 1 ? (
                <span aria-hidden className="relative ml-1 flex h-px flex-1 items-center bg-gray-300 max-lg:hidden">
                  <ArrowRight className="absolute left-1/2 size-3 -translate-x-1/2 bg-white text-gray-400" strokeWidth={1.8} />
                </span>
              ) : null}
            </div>
            <p className="mt-2 text-[12.5px] font-semibold text-gray-900">{stage.title}</p>
            <p className="mt-0.5 max-w-[180px] text-[10.5px] leading-[14px] text-gray-500">{stage.text}</p>
          </li>
        ))}
      </ol>
    </Card>
  );
}
