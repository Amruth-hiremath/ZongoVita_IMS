"use client";

import { Button, useNotice, type ButtonProps } from "@ims/ui";

export interface ActionButtonProps extends Omit<ButtonProps, "onClick"> {
  /** The Platform Service endpoint this action calls, as in the LLD route tables. */
  endpoint: string;
  /**
   * "endpoint" (default): the Platform Service does not provide the endpoint.
   * "design": it does, but the form the action opens has no approved wireframe yet
   * (Implementation_Progress U-06), so nothing is invented in its place.
   */
  waitingFor?: "endpoint" | "design";
}

/**
 * A button for an action that changes data but is not connected. Rather than pretend, the
 * button says so and names what it is waiting for. Connecting an action means replacing this
 * component with a real submit at that call site.
 */
export function ActionButton({ endpoint, waitingFor = "endpoint", children, ...rest }: ActionButtonProps) {
  const notify = useNotice();
  const message =
    waitingFor === "design"
      ? `The Platform Service provides ${endpoint}, but the form for this action has no approved design yet.`
      : `This action needs ${endpoint}, which the Platform Service does not provide.`;
  return (
    <Button {...rest} onClick={() => notify("Not connected yet", message)}>
      {children}
    </Button>
  );
}
