import { Card } from "@ims/ui";

export interface NoScreenProps {
  title: string;
  /** Why there is nothing to show, in one or two sentences. */
  children: React.ReactNode;
}

/**
 * Shown where the wireframes provide no screen: a menu entry without a frame, or a user type
 * the frames were not drawn for. Nothing is invented in its place.
 */
export function NoScreen({ title, children }: NoScreenProps) {
  return (
    <div>
      <h1 className="text-[21px] font-bold leading-7 text-gray-900">{title}</h1>
      <Card className="mt-6 max-w-[640px] p-5">
        <p className="text-[13px] font-semibold text-gray-900">No wireframe for this screen</p>
        <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">{children}</p>
      </Card>
    </div>
  );
}
