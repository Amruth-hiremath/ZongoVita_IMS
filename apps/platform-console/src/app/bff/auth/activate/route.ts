import { activateHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** New staff account: set a password with the one-time activation code. */
export const POST = activateHandler(consoleBff);
