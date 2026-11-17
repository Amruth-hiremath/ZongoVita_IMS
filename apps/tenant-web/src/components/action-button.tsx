"use client";

import { Button, useNotice, type ButtonProps } from "@ims/ui";

export interface ActionButtonProps extends Omit<ButtonProps, "onClick"> {
  /**
   * The Core endpoint this action will call, as in the LLD route tables
   * (e.g. "POST /ui/v1/issue-requests/{id}/approve").
   */
  endpoint: string;
  /**
   * "endpoint" (default): Core does not provide the endpoint yet.
   * "design": Core provides it, but the form or dialog the action opens has no approved
   * wireframe yet (Implementation_Progress U-06), so nothing is invented in its place.
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
      ? `IMS Core provides ${endpoint}, but the form for this action has no approved design yet.`
      : `This action needs ${endpoint}, which IMS Core does not provide yet.`;
  return (
    <Button {...rest} onClick={() => notify("Not connected yet", message)}>
      {children}
    </Button>
  );
}
