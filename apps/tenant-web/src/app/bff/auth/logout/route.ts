import { logoutHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** Sign out: Core revokes the session; the cookies are cleared. */
export const POST = logoutHandler(tenantBff);
