"""Typed domain errors and their mapping to problem-details responses (LLD section 12, 16).

``DomainError`` is the only exception type that reaches a client with meaning. Its HTTP status
and title come from one catalogue so a code never maps to two statuses by accident. Anything
else becomes 500 INTERNAL_ERROR with details kept to the logs.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ims_contracts.errors import (
    PROBLEM_CONTENT_TYPE,
    ErrorCode,
    FieldError,
    ProblemDetails,
    problem_type_uri,
)

log = logging.getLogger("ims.errors")

E = ErrorCode

#: code -> (default HTTP status, title). LLD section 12.
ERROR_CATALOGUE: Mapping[ErrorCode, tuple[int, str]] = {
    E.VALIDATION_FAILED: (422, "The request is not valid"),
    E.IDEMPOTENCY_KEY_REUSED: (422, "Idempotency key was already used for a different request"),
    E.MANUAL_CODE_IN_SEQUENCE_RANGE: (422, "Manual code falls in a numbering scheme's future range"),
    E.REASON_REQUIRED: (422, "A reason for change is required"),
    E.SIGNATURE_REQUIRED: (422, "An electronic signature is required"),
    E.SIGNATURE_INVALID: (422, "The electronic signature is not valid"),
    E.AUTH_REQUIRED: (401, "Authentication is required"),
    E.TOKEN_EXPIRED: (401, "The access token has expired"),
    E.PRINCIPAL_INACTIVE: (401, "The account is not active"),
    E.SESSION_REVOKED: (401, "The session has been revoked"),
    E.MFA_REQUIRED: (401, "Multi-factor authentication is required"),
    E.MFA_INVALID: (401, "Multi-factor authentication failed"),
    E.PERMISSION_DENIED: (403, "You do not have permission for this action"),
    E.SITE_SCOPE_DENIED: (403, "You do not have this permission at this site"),
    E.LICENCE_READ_ONLY: (403, "The licence is in read-only state"),
    E.LICENCE_SUSPENDED: (403, "The licence is suspended"),
    E.LICENCE_TERMINATED: (403, "The licence is terminated"),
    E.MODULE_NOT_LICENSED: (403, "This module is not licensed"),
    E.NOT_FOUND: (404, "Not found"),
    E.INSUFFICIENT_FREE_STOCK: (409, "Insufficient free stock"),
    E.OVER_ISSUE: (409, "Quantity exceeds the reservation"),
    E.LOT_UNAVAILABLE: (409, "The lot does not have enough issuable stock"),
    E.ITEM_MISMATCH: (409, "The scanned item does not match"),
    E.INVALID_STATE_TRANSITION: (409, "This action is not allowed in the record's current state"),
    E.DUPLICATE_CATEGORY: (409, "A matching category already exists"),
    E.ITEM_CODE_TAKEN: (409, "The item code is already in use"),
    E.LOGIN_IDENTIFIER_TAKEN: (409, "The login identifier is already in use"),
    E.LIMIT_EXCEEDED: (409, "The licence limit has been reached"),
    E.STOCK_BUSY: (409, "The stock position is busy; retry shortly"),
    E.REQUEST_IN_PROGRESS: (409, "An identical request is still in progress"),
    E.SOD_VIOLATION: (409, "Segregation of duties prevents this action"),
    E.VERSION_CONFLICT: (412, "The record was changed by someone else"),
    E.PRECONDITION_REQUIRED: (428, "If-Match is required"),
    E.RATE_LIMITED: (429, "Too many requests"),
    E.LICENCE_UNVERIFIABLE: (503, "The licence cannot be verified at the moment"),
    E.SCHEMA_VERSION_UNSUPPORTED: (503, "The database schema version is not supported by this release"),
    E.DB_BUSY: (503, "The database is busy; retry shortly"),
    E.INTERNAL_ERROR: (500, "Internal error"),
    E.METHOD_NOT_ALLOWED: (405, "Method not allowed"),
}


class DomainError(Exception):
    """An expected failure with a stable code. Raising it rolls back the unit of work."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str | None = None,
        *,
        status: int | None = None,
        errors: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        default_status, title = ERROR_CATALOGUE[code]
        super().__init__(f"{code}: {detail or title}")
        self.code = code
        self.status = status or default_status
        self.title = title
        self.detail = detail
        self.errors = errors or []
        self.headers = headers or {}

    def to_problem(self, request_id: str | None) -> ProblemDetails:
        return ProblemDetails(
            type=problem_type_uri(self.code),
            title=self.title,
            status=self.status,
            code=self.code,
            detail=self.detail,
            errors=self.errors,
            request_id=request_id,
        )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def problem_response(error: DomainError, request_id: str | None) -> JSONResponse:
    headers = dict(error.headers)
    if request_id:
        headers.setdefault("X-Request-ID", request_id)
    return JSONResponse(
        error.to_problem(request_id).to_body(),
        status_code=error.status,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
    )


def validation_error(exc: RequestValidationError) -> DomainError:
    """422 VALIDATION_FAILED with field paths and messages only: submitted values are never
    echoed back or logged."""
    errors = [
        FieldError(
            field=".".join(str(part) for part in err.get("loc", ()) if part != "body") or "body",
            message=str(err.get("msg", "invalid")),
            code=str(err.get("type")) if err.get("type") else None,
        )
        for err in exc.errors()
    ]
    return DomainError(E.VALIDATION_FAILED, errors=errors)


def install_problem_handlers(app: FastAPI) -> None:
    """Make every error response a problem-details document."""

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return problem_response(exc, _request_id(request))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(validation_error(exc), _request_id(request))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            error = DomainError(E.NOT_FOUND)
        elif exc.status_code == 405:
            error = DomainError(E.METHOD_NOT_ALLOWED, headers=dict(exc.headers or {}))
        elif exc.status_code >= 500:
            error = DomainError(E.INTERNAL_ERROR)
        else:
            error = DomainError(E.VALIDATION_FAILED, status=exc.status_code)
        return problem_response(error, _request_id(request))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error", exc_info=exc, extra={"route": request.url.path})
        return problem_response(DomainError(E.INTERNAL_ERROR), _request_id(request))
