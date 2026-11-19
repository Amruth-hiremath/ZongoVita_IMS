import type { ConsoleSource } from "@/session/config";

/**
 * Thin strip above the top bar saying where the screens' data comes from. Signed in to the
 * Platform Service, Overview and Licenses read the registry; Platform Config shows the
 * wireframe's sample data, which no /platform/v1 resource provides (Docs/UI_Implementation.md).
 */
export function DataSourceBanner({ source }: { source: ConsoleSource }) {
  return (
    <div className="flex h-6 items-center justify-center bg-gray-50 px-4 text-center text-[10.5px] tracking-wide text-gray-500">
      {source === "platform"
        ? "Signed in to the Platform Service · Overview and Licenses are live; Platform Config shows sample data from the wireframes"
        : "Sample data from the wireframes · not signed in to the Platform Service"}
    </div>
  );
}
