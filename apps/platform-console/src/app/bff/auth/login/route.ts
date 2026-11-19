import { loginHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** Password step: POST /platform/v1/auth/login; the MFA challenge stays in an HttpOnly cookie. */
export const POST = loginHandler(consoleBff);
