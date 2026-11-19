import { logoutHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** Sign out: the Platform Service revokes the session; the cookies are cleared. */
export const POST = logoutHandler(consoleBff);
