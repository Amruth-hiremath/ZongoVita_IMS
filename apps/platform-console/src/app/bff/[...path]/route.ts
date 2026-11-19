import { forwardHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** /bff/<path> -> Platform Service /platform/v1/<path> as the signed-in staff member (LLD 15, LD-49). */
const forward = forwardHandler(consoleBff);

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
