import { enrolHandler } from "@ims/web-session";

import { consoleBff } from "@/bff/config";

/** First sign-in: create the authenticator secret (POST /platform/v1/auth/mfa/enrol). */
export const POST = enrolHandler(consoleBff);
