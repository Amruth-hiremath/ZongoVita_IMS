import { Card } from "@ims/ui";

/**
 * Shown instead of a console screen the signed-in staff member may not open. The Platform Service
 * refuses the screen's endpoints in any case.
 */
export function NotPermitted() {
  return (
    <div>
      <h1 className="text-[21px] font-bold leading-7 text-gray-900">Not available</h1>
      <Card className="mt-6 max-w-[640px] p-5">
        <p role="alert" className="text-[13px] font-semibold text-gray-900">
          You do not have permission to open this screen
        </p>
        <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">
          Platform administration is for ZongoVita system admins. Support engineers work through support access the
          customer grants, which has no console screen yet.
        </p>
      </Card>
    </div>
  );
}
