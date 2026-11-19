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
from ims_contracts.platform_api import (
    ChangesResponse,
    DirectoryActivationRequest,
    DirectoryDisableRequest,
    DirectoryEntry,
    DirectoryListing,
    DirectoryReservationRequest,
    DirectoryReservationResponse,
    DirectoryResolveRequest,
)
from ims_platform.registry import MAX_CHANGES_PAGE, Actor
from ims_platform.runtime import PlatformRuntime

CORE_AND_WORKER = frozenset({"ims-core", "ims-worker"})
CORE_ONLY = frozenset({"ims-core"})


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


@router.get("/customers/{customer_id}/provisioning-snapshot", response_model=LicenceSnapshot)
async def get_provisioning_snapshot(
    customer_id: UUID,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    _caller: Annotated[ServiceCaller, Depends(require_service(CORE_ONLY))],
) -> LicenceSnapshot:
    """For IMS Core during provisioning step 6 only (LLD 6.6): the snapshot of a customer whose
    run is creating its super admin. 404 at any other time."""
    snapshot = await runtime.registry.get_provisioning_snapshot(customer_id)
    if snapshot is None:
        raise DomainError(ErrorCode.NOT_FOUND, "no provisioning run is creating this customer's super admin")
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


# ---------------------------------------------------------------------------- login directory
# Core resolves and reserves while creating principals; Workers activate, disable and reconcile
# (LLD 6.8). Until Workers exist (unit 6) Core also completes activation and disabling itself.


def _service_actor(caller: ServiceCaller, request: Request) -> Actor:
    return Actor(f"service:{caller.name}", request_id=request.headers.get("x-request-id"))


@router.post("/directory/resolve", response_model=DirectoryEntry)
async def resolve_identifier(
    body: DirectoryResolveRequest,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    _caller: Annotated[ServiceCaller, Depends(require_service(frozenset({"ims-core"})))],
) -> DirectoryEntry:
    """Identifier -> customer, principal, status. 404 when unknown or only reserved."""
    entry = await runtime.directory.resolve(body.identifier)
    if entry is None:
        raise DomainError(ErrorCode.NOT_FOUND, "identifier is not in the directory")
    return entry


@router.post("/directory/reservations", response_model=DirectoryReservationResponse, status_code=201)
async def reserve_identifier(
    body: DirectoryReservationRequest,
    request: Request,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    caller: Annotated[ServiceCaller, Depends(require_service(frozenset({"ims-core"})))],
) -> DirectoryReservationResponse:
    """Hold an identifier for 15 minutes for a principal being created; 409 if taken."""
    return await runtime.directory.reserve(
        customer_id=body.customer_id,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        identifier=body.identifier,
        actor=_service_actor(caller, request),
    )


@router.post("/directory/{principal_id}/activate", status_code=204)
async def activate_identifier(
    principal_id: UUID,
    body: DirectoryActivationRequest,
    request: Request,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    caller: Annotated[ServiceCaller, Depends(require_service(CORE_AND_WORKER))],
) -> None:
    await runtime.directory.activate(
        customer_id=body.customer_id,
        principal_type=body.principal_type,
        principal_id=principal_id,
        identifier=body.identifier,
        actor=_service_actor(caller, request),
    )


@router.post("/directory/{principal_id}/disable", status_code=204)
async def disable_identifier(
    principal_id: UUID,
    body: DirectoryDisableRequest,
    request: Request,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    caller: Annotated[ServiceCaller, Depends(require_service(CORE_AND_WORKER))],
) -> None:
    await runtime.directory.disable(
        customer_id=body.customer_id,
        principal_type=body.principal_type,
        principal_id=principal_id,
        actor=_service_actor(caller, request),
    )


@router.get("/directory", response_model=DirectoryListing)
async def list_directory(
    customer_id: UUID,
    runtime: Annotated[PlatformRuntime, Depends(get_runtime)],
    _caller: Annotated[ServiceCaller, Depends(require_service(CORE_AND_WORKER))],
) -> DirectoryListing:
    return DirectoryListing(entries=await runtime.directory.list_for_customer(customer_id))
