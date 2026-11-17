"""Pipeline stages supplied by the identity and access modules (LLD 6.1 steps 6 to 8).

The kernel defines the order and the contract; it does not know about users, roles or grants.
An application cannot be built without all three stages, so a tenant route can never be served
with a stage silently missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ims_core.kernel.authn import AccessClaims
from ims_core.kernel.routes import Access
from ims_core.kernel.uow import UnitOfWork


class PrincipalStage(Protocol):
    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        """Step 6: the user, API client or support principal is active, the session is not
        revoked and, for support, the grant is active. Primary-key reads only (LD-28).

        Raises 401 PRINCIPAL_INACTIVE or SESSION_REVOKED."""
        ...


class RateLimitStage(Protocol):
    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        """Step 7: token buckets per user, per API client and per customer (LD-88).

        Raises 429 RATE_LIMITED with Retry-After."""
        ...


class AuthoriseStage(Protocol):
    async def authorise(self, uow: UnitOfWork, access: Access) -> None:
        """Step 8: the route's declared access rule holds for the principal (section 7).

        Raises 403 PERMISSION_DENIED or SITE_SCOPE_DENIED."""
        ...


@dataclass(frozen=True)
class PipelineStages:
    principal: PrincipalStage
    rate_limit: RateLimitStage
    authorise: AuthoriseStage
