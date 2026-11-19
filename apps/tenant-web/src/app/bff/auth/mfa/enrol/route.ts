import { enrolHandler } from "@ims/web-session";

import { tenantBff } from "@/bff/config";

/** First sign-in: create the authenticator secret (POST /ui/v1/auth/mfa/enrol, D-16). */
export const POST = enrolHandler(tenantBff);
