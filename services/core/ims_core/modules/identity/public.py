"""What other modules and the application may use from the identity module (LD-01)."""

from __future__ import annotations

from ims_common.problem import DomainError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode
from ims_core.kernel.authn import AccessClaims
from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.identity import repository
from ims_core.modules.identity.service import (
    CreatedApiClient,
    CreatedUser,
    IdentityService,
    SessionTokens,
    SignInChallenge,
)

__all__ = [
    "CreatedApiClient",
    "CreatedUser",
    "IdentityService",
    "PrincipalStage",
    "SessionTokens",
    "SignInChallenge",
]


class PrincipalStage:
    """Pipeline step 6 (LLD 6.1): the principal is active and, for a user, the session is live.

    Primary-key reads only (LD-28). A revoked, expired or unknown session is SESSION_REVOKED; an
    account that is no longer active is PRINCIPAL_INACTIVE. Support sessions come with support
    grants (LD-83, unit 12); until then a support token is refused.
    """

    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        if claims.principal_type is PrincipalType.USER:
            session = (
                await repository.session_principal(uow.db, claims.session_id) if claims.session_id else None
            )
            now = uow.clock.now()
            if (
                session is None
                or session.principal_type != "user"
                or session.user_id != claims.subject
                or session.revoked_at is not None
                or now >= session.idle_expires_at
                or now >= session.absolute_expires_at
            ):
                raise DomainError(ErrorCode.SESSION_REVOKED)
            if session.user_status != "active":
                raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
            return
        if claims.principal_type is PrincipalType.API_CLIENT:
            client = await repository.get_api_client(uow.db, claims.subject)
            if client is None or client.status != "active":
                raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
            return
        raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
