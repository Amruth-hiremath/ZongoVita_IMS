/**
 * Error contract of the IMS APIs (LLD section 12): every error response is a problem-details
 * document carrying one of these stable codes.
 *
 * Mirrors ims_contracts.errors.ErrorCode (packages/py-contracts). A repository test compares
 * the two lists, so they cannot drift.
 */
export const ERROR_CODES = [
  "VALIDATION_FAILED",
  "IDEMPOTENCY_KEY_REUSED",
  "MANUAL_CODE_IN_SEQUENCE_RANGE",
  "REASON_REQUIRED",
  "SIGNATURE_REQUIRED",
  "SIGNATURE_INVALID",
  "AUTH_REQUIRED",
  "TOKEN_EXPIRED",
  "PRINCIPAL_INACTIVE",
  "SESSION_REVOKED",
  "MFA_REQUIRED",
  "MFA_INVALID",
  "PERMISSION_DENIED",
  "SITE_SCOPE_DENIED",
  "LICENCE_READ_ONLY",
  "LICENCE_SUSPENDED",
  "LICENCE_TERMINATED",
  "MODULE_NOT_LICENSED",
  "NOT_FOUND",
  "INSUFFICIENT_FREE_STOCK",
  "OVER_ISSUE",
  "LOT_UNAVAILABLE",
  "ITEM_MISMATCH",
  "INVALID_STATE_TRANSITION",
  "DUPLICATE_CATEGORY",
  "ITEM_CODE_TAKEN",
  "LOGIN_IDENTIFIER_TAKEN",
  "LIMIT_EXCEEDED",
  "STOCK_BUSY",
  "REQUEST_IN_PROGRESS",
  "SOD_VIOLATION",
  "VERSION_CONFLICT",
  "PRECONDITION_REQUIRED",
  "RATE_LIMITED",
  "LICENCE_UNVERIFIABLE",
  "SCHEMA_VERSION_UNSUPPORTED",
  "DB_BUSY",
  "INTERNAL_ERROR",
  "METHOD_NOT_ALLOWED",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export interface FieldError {
  field: string;
  message: string;
  code?: string;
}

/** Body of every error response: type, title, status, code, detail, errors, request_id. */
export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  code: ErrorCode;
  detail?: string;
  errors?: FieldError[];
  request_id?: string;
}

export function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.status === "number" &&
    (ERROR_CODES as readonly string[]).includes(candidate.code)
  );
}
