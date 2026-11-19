import { loginHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** Password step (LLD 6.2): POST /ui/v1/auth/login; the MFA challenge stays in a cookie. */
export const POST = loginHandler(tenantBff);
