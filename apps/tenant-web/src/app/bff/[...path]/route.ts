import { forwardHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** /bff/<path> -> IMS Core /ui/v1/<path> as the signed-in user (LLD 15, LD-49; @ims/web-session). */
const forward = forwardHandler(tenantBff);

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
