import { mfaHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** Second factor, required for all staff (LLD 15); the session's tokens go into HttpOnly cookies. */
export const POST = mfaHandler(consoleBff);
