"""Internal interface of the Platform Service (LLD 6.8).

Accepts only short-lived service tokens with audience ``platform-internal`` and is not routed
from the internet. This module carries the licensing part of the narrow interface: licence
snapshot (which includes the database location) and the change feed.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from ims_common.problem import DomainError
from ims_common.service_auth import ServiceCaller
from ims_common.tokens import TokenError
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import LicenceSnapshot
from ims_contracts.platform_api import ChangesResponse
from ims_platform.registry import MAX_CHANGES_PAGE
from ims_platform.runtime import PlatformRuntime

CORE_AND_WORKER = frozenset({"ims-core", "ims-worker"})


def get_runtime(request: Request) -> PlatformRuntime:
    return request.app.state.runtime


def require_service(allowed: frozenset[str]):
    """Dependency: the caller is one of the allowed services, proven by its signed token."""

    def _dependency(
        request: Request, runtime: Annotated[PlatformRuntime, Depends(get_runtime)]
    ) -> ServiceCaller:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise DomainError(ErrorCode.AUTH_REQUIRED, "service token required")
        try:
            return runtime.service_verifier.verify(token.strip(), allowed=allowed)
        except TokenError as exc:
            code = ErrorCode.TOKEN_EXPIRED if exc.reason == "expired" else ErrorCode.AUTH_REQUIRED
            raise DomainError(code, "service token rejected") from exc

    return _dependency


router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.get("/customers/{customer_id}/snapshot", response_model=LicenceSnapshot)
async def get_snapshot(
    customer_id: UUID,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    _caller: Annotated[ServiceCaller, Depends(require_service(CORE_AND_WORKER))],
) -> LicenceSnapshot:
    """Licence snapshot of one customer. 404 means the customer is unknown or was never
    licensed, which callers must treat as a refusal, not as an outage."""
    snapshot = await runtime.registry.get_snapshot(customer_id)
    if snapshot is None:
        raise DomainError(ErrorCode.NOT_FOUND, "customer is unknown or not licensed")
    return snapshot


@router.get("/changes", response_model=ChangesResponse)
async def get_changes(
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    _caller: Annotated[ServiceCaller, Depends(require_service(CORE_AND_WORKER))],
    after_seq: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_CHANGES_PAGE)] = MAX_CHANGES_PAGE,
) -> ChangesResponse:
    """Registry changes after ``after_seq`` in commit order; omit it to learn the head position."""
    return await runtime.registry.changes(after_seq, limit)
