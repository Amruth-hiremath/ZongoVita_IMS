"""Access tokens (AD-21, AD-23; LLD 6.2).

Tokens are EdDSA JWTs signed by Core with a key ID, so keys rotate without invalidating live
tokens. The customer comes from the ``cid`` claim of a verified token and from nowhere else.
Login, MFA, refresh and session handling build on this in the identity module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from ims_common.problem import DomainError
from ims_common.tokens import TokenCodec, TokenError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode

AUDIENCE_UI = "ims-ui"
AUDIENCE_API = "ims-api"

# LLD 6.2 lifetimes (LLD defaults, open item #26).
USER_ACCESS_TTL = timedelta(minutes=15)
API_CLIENT_ACCESS_TTL = timedelta(minutes=10)
SUPPORT_ACCESS_TTL = timedelta(minutes=15)

#: Which principal types may present a token for which audience.
_AUDIENCE_PRINCIPALS: dict[str, frozenset[PrincipalType]] = {
    AUDIENCE_UI: frozenset({PrincipalType.USER, PrincipalType.SUPPORT}),
    AUDIENCE_API: frozenset({PrincipalType.API_CLIENT}),
}


@dataclass(frozen=True)
class AccessClaims:
    subject: UUID
    principal_type: PrincipalType
    customer_id: UUID
    session_id: UUID | None
    support_grant_id: UUID | None
    token_id: str
    expires_at: int


def _unauthenticated(code: ErrorCode = ErrorCode.AUTH_REQUIRED) -> DomainError:
    # One generic failure for every reason, so a caller learns nothing about why.
    return DomainError(code, headers={"WWW-Authenticate": "Bearer"})


class Authenticator:
    def __init__(self, codec: TokenCodec) -> None:
        self._codec = codec

    # ------------------------------------------------------------------------- verification
    def authenticate(self, authorization: str | None, *, audience: str) -> AccessClaims:
        """Step 2 of the request pipeline: signature by key ID, issuer, audience for this API,
        expiry. Step 3 reads the customer from the returned claims and consults nothing else."""
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _unauthenticated()
        try:
            claims = self._codec.decode(token.strip(), audience=audience)
        except TokenError as exc:
            raise _unauthenticated(
                ErrorCode.TOKEN_EXPIRED if exc.reason == "expired" else ErrorCode.AUTH_REQUIRED
            ) from None
        try:
            principal_type = PrincipalType(claims["ptype"])
            parsed = AccessClaims(
                subject=UUID(claims["sub"]),
                principal_type=principal_type,
                customer_id=UUID(claims["cid"]),
                session_id=UUID(claims["sid"]) if claims.get("sid") else None,
                support_grant_id=UUID(claims["gid"]) if claims.get("gid") else None,
                token_id=str(claims["jti"]),
                expires_at=int(claims["exp"]),
            )
        except (KeyError, ValueError, TypeError):
            raise _unauthenticated() from None
        if principal_type not in _AUDIENCE_PRINCIPALS.get(audience, frozenset()):
            raise _unauthenticated()
        if principal_type is PrincipalType.USER and parsed.session_id is None:
            raise _unauthenticated()
        if principal_type is PrincipalType.SUPPORT and (
            parsed.support_grant_id is None or parsed.session_id is None
        ):
            raise _unauthenticated()
        return parsed

    # ----------------------------------------------------------------------------- issuance
    def issue_user_access(self, *, customer_id: UUID, user_id: UUID, session_id: UUID) -> str:
        """Access token for a signed-in user. Issued only after MFA (LD-79)."""
        return self._codec.encode(
            subject=str(user_id),
            audience=AUDIENCE_UI,
            ttl=USER_ACCESS_TTL,
            claims={"ptype": PrincipalType.USER.value, "cid": str(customer_id), "sid": str(session_id)},
        )

    def issue_api_client_access(self, *, customer_id: UUID, client_id: UUID) -> str:
        """Access token for the client-credentials grant at /api/v1/oauth/token."""
        return self._codec.encode(
            subject=str(client_id),
            audience=AUDIENCE_API,
            ttl=API_CLIENT_ACCESS_TTL,
            claims={"ptype": PrincipalType.API_CLIENT.value, "cid": str(customer_id)},
        )

    def issue_support_access(
        self,
        *,
        customer_id: UUID,
        support_principal_id: UUID,
        session_id: UUID,
        grant_id: UUID,
        ttl: timedelta = SUPPORT_ACCESS_TTL,
    ) -> str:
        """Access token for a support session; never outlives the customer's grant (LD-83)."""
        return self._codec.encode(
            subject=str(support_principal_id),
            audience=AUDIENCE_UI,
            ttl=min(ttl, SUPPORT_ACCESS_TTL),
            claims={
                "ptype": PrincipalType.SUPPORT.value,
                "cid": str(customer_id),
                "sid": str(session_id),
                "gid": str(grant_id),
            },
        )


# ------------------------------------------------------------------------- credential tokens
AUDIENCE_REFRESH = "ims-refresh"
AUDIENCE_MFA = "ims-mfa"


@dataclass(frozen=True)
class RefreshClaims:
    """A refresh token (LLD 6.2): valid only while its ID is the session's current one (LD-26)."""

    customer_id: UUID
    user_id: UUID
    session_id: UUID
    token_id: str


@dataclass(frozen=True)
class ChallengeClaims:
    """An MFA challenge, issued after a correct password; single use (LD-79)."""

    customer_id: UUID
    user_id: UUID
    token_id: str


class CredentialTokens:
    """Refresh tokens and MFA challenges. Both carry the customer, so the endpoints that accept
    them (no access token) still route only from a verified claim (AD-21)."""

    def __init__(self, codec: TokenCodec) -> None:
        self._codec = codec

    def _claims(self, token: str, audience: str) -> dict[str, object]:
        try:
            return self._codec.decode(token, audience=audience)
        except TokenError:
            # Expired or invalid alike: the caller has to sign in again.
            raise _unauthenticated() from None

    def issue_refresh(
        self, *, customer_id: UUID, user_id: UUID, session_id: UUID, token_id: str, ttl: timedelta
    ) -> str:
        return self._codec.encode(
            subject=str(user_id),
            audience=AUDIENCE_REFRESH,
            ttl=ttl,
            claims={"cid": str(customer_id), "sid": str(session_id)},
            token_id=token_id,
        )

    def verify_refresh(self, token: str) -> RefreshClaims:
        claims = self._claims(token, AUDIENCE_REFRESH)
        try:
            return RefreshClaims(
                customer_id=UUID(str(claims["cid"])),
                user_id=UUID(str(claims["sub"])),
                session_id=UUID(str(claims["sid"])),
                token_id=str(claims["jti"]),
            )
        except (KeyError, ValueError):
            raise _unauthenticated() from None

    def issue_mfa_challenge(self, *, customer_id: UUID, user_id: UUID, token_id: str, ttl: timedelta) -> str:
        return self._codec.encode(
            subject=str(user_id),
            audience=AUDIENCE_MFA,
            ttl=ttl,
            claims={"cid": str(customer_id)},
            token_id=token_id,
        )

    def verify_mfa_challenge(self, token: str) -> ChallengeClaims:
        claims = self._claims(token, AUDIENCE_MFA)
        try:
            return ChallengeClaims(
                customer_id=UUID(str(claims["cid"])),
                user_id=UUID(str(claims["sub"])),
                token_id=str(claims["jti"]),
            )
        except (KeyError, ValueError):
            raise _unauthenticated() from None
