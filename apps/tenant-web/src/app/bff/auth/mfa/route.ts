import { mfaHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** Second factor (LD-79); the session's tokens go into HttpOnly cookies. */
export const POST = mfaHandler(tenantBff);
