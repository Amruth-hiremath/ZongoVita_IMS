"""Tenant context: the customer a request or job acts for.

Isolation by construction (HLD section 2): the only function that returns a database
connection requires a resolved ``TenantContext``, and a context is only ever built by the
kernel from a verified token or, for jobs, from the work-pending index. No endpoint accepts a
customer or database identifier (AD-21). A static check keeps construction inside the kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

from ims_contracts.enums import ActorType, PrincipalType
from ims_contracts.licence import LicenceSnapshot, LicenceState

Source = Literal["ui", "api", "worker", "system"]


@dataclass(frozen=True)
class Principal:
    """Who is acting: a user, an API client, or a support principal under a customer's grant."""

    type: PrincipalType
    id: UUID
    session_id: UUID | None = None
    support_grant_id: UUID | None = None

    @property
    def actor_type(self) -> ActorType:
        return ActorType(self.type.value)


@dataclass(frozen=True)
class TenantContext:
    customer_id: UUID
    customer_code: str
    snapshot: LicenceSnapshot
    licence_state: LicenceState
    request_id: str
    source: Source
    principal: Principal | None = None
    trace_id: str | None = None

    @property
    def gxp_mode(self) -> bool:
        return self.snapshot.gxp_mode


def with_principal(ctx: TenantContext, principal: Principal) -> TenantContext:
    """The same context acting as ``principal``: used by credential flows once the caller is
    identified (sign-in, token refresh), so audit entries name them."""
    return replace(ctx, principal=principal)
