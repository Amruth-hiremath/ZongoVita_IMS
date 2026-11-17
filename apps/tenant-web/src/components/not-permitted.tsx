import { Card } from "@ims/ui";

/**
 * Shown instead of a screen whose permission the signed-in person does not hold (LLD 15). It
 * names no permission and no role: actions are labelled by action, not by role.
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
          Your administrator can change what your role allows.
        </p>
      </Card>
    </div>
  );
}
