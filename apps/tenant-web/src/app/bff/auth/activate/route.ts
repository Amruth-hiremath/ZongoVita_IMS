import { activateHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** New user: set a password with the one-time activation code. */
export const POST = activateHandler(tenantBff);
