"use client";

import { Button, useNotice, type ButtonProps } from "@ims/ui";

export interface ActionButtonProps extends Omit<ButtonProps, "onClick"> {
  /**
   * The Core endpoint this action will call, as in the LLD route tables
   * (e.g. "POST /ui/v1/issue-requests/{id}/approve").
   */
  endpoint: string;
}

/**
 * A button for an action that changes data.
 *
 * No such action is wired yet: Core does not expose the endpoints. Rather than pretend, the
 * button says so and names the endpoint it is waiting for. Connecting an action means replacing
 * this component with a real submit at that call site.
 */
export function ActionButton({ endpoint, children, ...rest }: ActionButtonProps) {
  const notify = useNotice();
  return (
    <Button
      {...rest}
      onClick={() => notify("Not connected yet", `This action needs ${endpoint}, which IMS Core does not provide yet.`)}
    >
      {children}
    </Button>
  );
}
