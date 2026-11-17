"""What other modules and the application may use from the access module (LD-01)."""

from __future__ import annotations

from uuid import UUID

from ims_common.problem import DomainError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode
from ims_core.kernel.grants import Grants
from ims_core.kernel.routes import Access, Authenticated, GateApprover, NoPermission, Permission
from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.access import repository
from ims_core.modules.access.evaluation import PermissionCache
from ims_core.modules.access.ratelimit import RateLimiter, RateLimits
from ims_core.modules.access.service import compute_grants

__all__ = ["Authoriser", "PermissionCache", "RateLimiter", "RateLimits", "compute_grants"]


class Authoriser:
    """Pipeline step 8 (LLD 6.1, section 7): the route's declared access rule holds.

    The principal's effective permissions are placed on the unit of work (``uow.grants``) for
    the handler's site checks and list filters. ``Permission(code)`` passes when the code is held
    at one site at least; the record's own site is checked by the handler once it is loaded
    ("site-scoped checks use the site of the loaded record, never a request parameter").
    ``GateApprover`` routes pass here: eligibility is the gate's approver selector, evaluated by
    the workflow engine against the task (section 8).
    """

    def __init__(self, cache: PermissionCache | None = None) -> None:
        self.cache = cache or PermissionCache()

    async def grants_for(self, uow: UnitOfWork, principal_type: str, principal_id: UUID) -> Grants:
        version = await repository.access_version(uow.db)
        now = uow.clock.monotonic()
        customer_id = uow.ctx.customer_id
        cached = self.cache.get(customer_id, principal_type, principal_id, version, now)
        if cached is not None:
            return cached
        grants = await compute_grants(uow, principal_type, principal_id)
        self.cache.put(customer_id, principal_type, principal_id, version, now, grants)
        return grants

    async def authorise(self, uow: UnitOfWork, access: Access) -> None:
        principal = uow.ctx.principal
        if principal is None or isinstance(access, NoPermission):
            raise RuntimeError("the authorise stage runs only for routes with an access token")
        if principal.type is PrincipalType.SUPPORT:
            # Support grants (LD-83) arrive with unit 12; step 6 already refuses these tokens.
            raise DomainError(ErrorCode.PERMISSION_DENIED)
        uow.grants = await self.grants_for(uow, principal.type.value, principal.id)
        if isinstance(access, Permission):
            uow.grants.require(access.code)
        elif not isinstance(access, Authenticated | GateApprover):
            raise RuntimeError(f"unknown access rule {access!r}")
