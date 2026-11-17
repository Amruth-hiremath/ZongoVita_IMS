"""Error codes and the problem-details body (LLD section 12)."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """Stable machine-readable error codes. Additive only within /api/v1 (AD-57)."""

    # 400 / 422
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    MANUAL_CODE_IN_SEQUENCE_RANGE = "MANUAL_CODE_IN_SEQUENCE_RANGE"
    REASON_REQUIRED = "REASON_REQUIRED"
    SIGNATURE_REQUIRED = "SIGNATURE_REQUIRED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    # 401
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105 - an error code, not a credential
    PRINCIPAL_INACTIVE = "PRINCIPAL_INACTIVE"
    SESSION_REVOKED = "SESSION_REVOKED"
    MFA_REQUIRED = "MFA_REQUIRED"
    MFA_INVALID = "MFA_INVALID"
    # 403
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SITE_SCOPE_DENIED = "SITE_SCOPE_DENIED"
    LICENCE_READ_ONLY = "LICENCE_READ_ONLY"
    LICENCE_SUSPENDED = "LICENCE_SUSPENDED"
    LICENCE_TERMINATED = "LICENCE_TERMINATED"
    MODULE_NOT_LICENSED = "MODULE_NOT_LICENSED"
    # 404
    NOT_FOUND = "NOT_FOUND"
    # 409
    INSUFFICIENT_FREE_STOCK = "INSUFFICIENT_FREE_STOCK"
    OVER_ISSUE = "OVER_ISSUE"
    LOT_UNAVAILABLE = "LOT_UNAVAILABLE"
    ITEM_MISMATCH = "ITEM_MISMATCH"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    DUPLICATE_CATEGORY = "DUPLICATE_CATEGORY"
    ITEM_CODE_TAKEN = "ITEM_CODE_TAKEN"
    LOGIN_IDENTIFIER_TAKEN = "LOGIN_IDENTIFIER_TAKEN"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    STOCK_BUSY = "STOCK_BUSY"
    REQUEST_IN_PROGRESS = "REQUEST_IN_PROGRESS"
    SOD_VIOLATION = "SOD_VIOLATION"
    # 412 / 428 / 429
    VERSION_CONFLICT = "VERSION_CONFLICT"
    PRECONDITION_REQUIRED = "PRECONDITION_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    # 503 / 500
    LICENCE_UNVERIFIABLE = "LICENCE_UNVERIFIABLE"
    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    DB_BUSY = "DB_BUSY"
    PLATFORM_UNAVAILABLE = "PLATFORM_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Protocol level (not a business rule): the path exists but not for this HTTP method.
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"


PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_type_uri(code: ErrorCode | str) -> str:
    """Stable identifier for a problem type; a URN so it never dereferences."""
    return "urn:zongovita:ims:problem:" + str(code).lower().replace("_", "-")


class FieldError(BaseModel):
    """One entry of ProblemDetails.errors."""

    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
    code: str | None = None


class ProblemDetails(BaseModel):
    """Body of every error response: type, title, status, code, detail, errors, request_id."""

    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    errors: list[FieldError] = Field(default_factory=list)
    request_id: str | None = None

    def to_body(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
