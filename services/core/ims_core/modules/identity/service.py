"""Identity use cases (LLD 6.2, 6.3; AD-20 to AD-23, AD-65; LD-79, LD-80).

Sign-in is two steps: the password (POST /ui/v1/auth/login), then MFA (POST /ui/v1/auth/mfa),
with enrolment (POST /ui/v1/auth/mfa/enrol) at first sign-in. A session exists, and an access
token is issued, only after MFA. Every local user enrols; there is no way to defer it.

Three rules shape the code:

* Constant work (LD-80). Every sign-in path performs exactly one Argon2id verification, against
  the dummy hash where there is nothing real to check, and fails with the same generic answer.
* Failures persist. A failed attempt is recorded and committed before the error is returned, so it
  counts toward the lockout (five failures lock for 15 minutes; MFA failures count too).
* Expensive work outside transactions. Argon2id runs between two short transactions, so a sign-in
  never holds one of the customer's few pooled connections while hashing (LLD 6.5).
"""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text

from ims_common.identifiers import InvalidIdentifierError, normalise_login_identifier
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_contracts.enums import LicenceModule, PrincipalType
from ims_contracts.errors import ErrorCode, FieldError
from ims_core.kernel.authn import API_CLIENT_ACCESS_TTL, USER_ACCESS_TTL, ChallengeClaims
from ims_core.kernel.context import Principal, Source, TenantContext, with_principal
from ims_core.kernel.licence import RegistryUnavailableError
from ims_core.kernel.uow import UnitOfWork, unit_of_work
from ims_core.modules.identity import domain, events, repository
from ims_core.modules.identity.credentials import PasswordHasher, SecretBox

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from ims_core.kernel.directory import DirectoryCache
    from ims_core.kernel.runtime import CoreRuntime

log = logging.getLogger("ims.identity")

SIGN_IN_FAILED = "Sign-in failed"
ACTIVATION_FAILED = "Activation failed"
CLIENT_AUTHENTICATION_FAILED = "Client authentication failed"

#: Licence answers that must not be told apart from a wrong credential before authentication.
_QUIET_REFUSALS = frozenset(
    {
        ErrorCode.AUTH_REQUIRED,
        ErrorCode.LICENCE_SUSPENDED,
        ErrorCode.LICENCE_TERMINATED,
        ErrorCode.MODULE_NOT_LICENSED,
    }
)


def _refused(detail: str) -> DomainError:
    return DomainError(ErrorCode.AUTH_REQUIRED, detail, headers={"WWW-Authenticate": "Bearer"})


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


def _factor_context(user_id: UUID) -> str:
    """Binds an encrypted TOTP secret to its user: a copy on another row does not decrypt."""
    return f"iam.mfa_factors:{user_id}"


@dataclass(frozen=True)
class SignInChallenge:
    challenge_token: str
    enrolment_required: bool
    expires_in: int


@dataclass(frozen=True)
class Enrolment:
    secret: str
    otpauth_uri: str


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_at: datetime
    recovery_codes: list[str] | None = None


@dataclass(frozen=True)
class ClientToken:
    access_token: str
    expires_in: int


@dataclass(frozen=True)
class CreatedUser:
    user_id: UUID
    activation_code: str
    activation_expires_at: datetime


@dataclass(frozen=True)
class CreatedApiClient:
    client_id: UUID
    client_secret: str


class IdentityService:
    def __init__(self, runtime: CoreRuntime, hasher: PasswordHasher) -> None:
        self._runtime = runtime
        self._clock = runtime.clock
        self._settings = runtime.settings
        self.hasher = hasher
        self._box: SecretBox | None = None
        self._dummy_client_hash = domain.hash_client_secret(domain.new_client_secret())

    # =============================================================================== helpers
    @property
    def directory(self) -> DirectoryCache:
        if self._runtime.directory is None:
            raise RuntimeError("the Login Directory client is not configured")
        return self._runtime.directory

    async def _secret_box(self) -> SecretBox:
        if self._box is None:
            self._box = SecretBox(await self._runtime.secrets.get(self._settings.mfa_encryption_key_ref))
        return self._box

    async def _quiet_context(
        self, customer_id: UUID, request_id: str, *, module: LicenceModule, source: Source
    ) -> TenantContext | None:
        """The customer's context, or None where a refusal must look like a wrong credential."""
        try:
            return await self._runtime.credential_context(
                customer_id, module=module, request_id=request_id, source=source
            )
        except DomainError as exc:
            if exc.code in _QUIET_REFUSALS:
                log.info("credential refused by the licence gate", extra={"code": exc.code})
                return None
            raise

    async def _user_context(self, customer_id: UUID, user_id: UUID, request_id: str) -> TenantContext:
        """Context for a caller already identified by a signed token (MFA challenge, refresh)."""
        ctx = await self._runtime.credential_context(
            customer_id, module=LicenceModule.CORE, request_id=request_id, source="ui"
        )
        return with_principal(ctx, Principal(type=PrincipalType.USER, id=user_id))

    def _uow(self, ctx: TenantContext, *, read_only: bool = False) -> AbstractAsyncContextManager[UnitOfWork]:
        return unit_of_work(self._runtime.router, ctx, self._clock, read_only=read_only)

    def _now(self) -> datetime:
        return self._clock.now()

    def _locked(self, user: repository.UserRow) -> bool:
        return user.locked_until is not None and user.locked_until > self._now()

    async def _record_failure(self, uow: UnitOfWork, user_id: UUID) -> None:
        """Count a failed password, MFA code or activation code; lock at the threshold (LLD 6.2)."""
        user = await repository.lock_user(uow.db, user_id)
        if user is None:
            return
        attempts = user.failed_attempts + 1
        if attempts < self._settings.lockout_threshold:
            await repository.update_user(uow.db, user_id, actor=None, failed_attempts=attempts)
            return
        until = self._now() + timedelta(minutes=self._settings.lockout_minutes)
        await repository.update_user(
            uow.db,
            user_id,
            actor=None,
            failed_attempts=0,
            locked_until=until,
            mfa_challenge_jti=None,
            mfa_challenge_expires_at=None,
        )
        await uow.audit.record(
            action="iam.user.locked",
            entity_type="iam.user",
            entity_id=user_id,
            after={"locked_until": until, "failed_attempts": attempts},
        )

    def _check_challenge(
        self, user: repository.UserRow | None, claims: ChallengeClaims
    ) -> repository.UserRow:
        """The challenge is the user's current one, unexpired, and the account can still sign in."""
        if (
            user is None
            or user.status != "active"
            or self._locked(user)
            or user.mfa_challenge_jti is None
            or user.mfa_challenge_expires_at is None
            or user.mfa_challenge_expires_at <= self._now()
            or not hmac.compare_digest(user.mfa_challenge_jti, claims.token_id)
        ):
            raise _refused(SIGN_IN_FAILED)
        return user

    def _session_tokens(
        self,
        customer_id: UUID,
        user_id: UUID,
        session_id: UUID,
        refresh_jti: str,
        idle_expires_at: datetime,
        recovery_codes: list[str] | None = None,
    ) -> SessionTokens:
        return SessionTokens(
            access_token=self._runtime.authenticator.issue_user_access(
                customer_id=customer_id, user_id=user_id, session_id=session_id
            ),
            refresh_token=self._runtime.credential_tokens.issue_refresh(
                customer_id=customer_id,
                user_id=user_id,
                session_id=session_id,
                token_id=refresh_jti,
                ttl=idle_expires_at - self._now(),
            ),
            expires_in=int(USER_ACCESS_TTL.total_seconds()),
            refresh_expires_at=idle_expires_at,
            recovery_codes=recovery_codes,
        )

    async def _open_session(
        self, uow: UnitOfWork, user_id: UUID, *, recovery_codes: list[str] | None
    ) -> SessionTokens:
        """MFA passed: clear the challenge, reset failures, create the session (LLD 6.2)."""
        now = self._now()
        await repository.update_user(
            uow.db,
            user_id,
            actor=user_id,
            failed_attempts=0,
            mfa_challenge_jti=None,
            mfa_challenge_expires_at=None,
        )
        session_id = uuid7()
        refresh_jti = str(uuid7())
        absolute = now + timedelta(days=self._settings.session_absolute_days)
        idle = min(now + timedelta(hours=self._settings.session_idle_hours), absolute)
        await repository.insert_session(
            uow.db,
            session_id=session_id,
            user_id=user_id,
            refresh_jti=refresh_jti,
            at=now,
            idle_expires_at=idle,
            absolute_expires_at=absolute,
        )
        await uow.audit.record(
            action="iam.session.created",
            entity_type="iam.session",
            entity_id=session_id,
            after={"user_id": user_id, "idle_expires_at": idle, "absolute_expires_at": absolute},
        )
        return self._session_tokens(
            uow.ctx.customer_id, user_id, session_id, refresh_jti, idle, recovery_codes
        )

    # =============================================================================== sign-in
    async def sign_in(self, identifier: str, password: str, *, request_id: str) -> SignInChallenge:
        """Step 1, the password. Returns a single-use MFA challenge (LLD 6.2)."""
        entry = await self.directory.resolve(identifier)
        ctx: TenantContext | None = None
        if entry is not None and entry.principal_type == "user" and entry.status == "active":
            ctx = await self._quiet_context(
                entry.customer_id, request_id, module=LicenceModule.CORE, source="ui"
            )
        if entry is None or ctx is None:
            await self.hasher.burn(password)
            raise _refused(SIGN_IN_FAILED)
        user_id = entry.principal_id
        ctx = with_principal(ctx, Principal(type=PrincipalType.USER, id=user_id))
        normalised = normalise_login_identifier(identifier)

        async with self._uow(ctx, read_only=True) as uow:
            user = await repository.read_user(uow.db, user_id)
        usable = (
            user is not None
            and user.login_identifier == normalised
            and user.status == "active"
            and not self._locked(user)
        )
        stored_hash = user.password_hash if usable and user is not None else None
        matched = await self.hasher.verify(stored_hash, password)  # the one verification (LD-80)
        if not usable:
            raise _refused(SIGN_IN_FAILED)
        rehashed = (
            await self.hasher.hash(password)
            if matched and self.hasher.needs_rehash(stored_hash or "")
            else None
        )

        challenge: SignInChallenge | None = None
        async with self._uow(ctx) as uow:
            current = await repository.lock_user(uow.db, user_id)
            if current is None:
                pass
            elif not matched:
                await self._record_failure(uow, user_id)
            elif (
                current.password_hash == stored_hash
                and current.status == "active"
                and not self._locked(current)
            ):
                challenge = await self._start_challenge(uow, current, rehashed)
        if challenge is None:
            raise _refused(SIGN_IN_FAILED)
        return challenge

    async def _start_challenge(
        self, uow: UnitOfWork, user: repository.UserRow, rehashed: str | None
    ) -> SignInChallenge:
        minutes = self._settings.mfa_challenge_minutes
        jti = str(uuid7())
        fields: dict[str, object] = {
            "failed_attempts": 0,
            "mfa_challenge_jti": jti,
            "mfa_challenge_expires_at": self._now() + timedelta(minutes=minutes),
        }
        if rehashed is not None:  # Argon2 parameters were raised since this hash was made
            fields["password_hash"] = rehashed
        await repository.update_user(uow.db, user.id, actor=user.id, **fields)
        return SignInChallenge(
            challenge_token=self._runtime.credential_tokens.issue_mfa_challenge(
                customer_id=uow.ctx.customer_id, user_id=user.id, token_id=jti, ttl=timedelta(minutes=minutes)
            ),
            enrolment_required=user.mfa_enrolled_at is None,
            expires_in=int(minutes * 60),
        )

    async def begin_enrolment(self, challenge_token: str, *, request_id: str) -> Enrolment:
        """First sign-in: create the user's TOTP factor, unconfirmed until a code proves it (LD-79)."""
        claims = self._runtime.credential_tokens.verify_mfa_challenge(challenge_token)
        ctx = await self._user_context(claims.customer_id, claims.user_id, request_id)
        box = await self._secret_box()
        async with self._uow(ctx) as uow:
            user = self._check_challenge(await repository.lock_user(uow.db, claims.user_id), claims)
            if user.mfa_enrolled_at is not None:
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION, "multi-factor authentication is already set up"
                )
            secret = domain.new_totp_secret()
            sealed, key_id = box.seal(secret, context=_factor_context(user.id))
            await repository.revoke_pending_factors(uow.db, user.id, self._now())
            factor_id = uuid7()
            await repository.insert_factor(
                uow.db, factor_id=factor_id, user_id=user.id, ciphertext=sealed, key_id=key_id
            )
            await uow.audit.record(
                action="iam.mfa.enrolment_started",
                entity_type="iam.mfa_factor",
                entity_id=factor_id,
                after={"user_id": user.id, "kind": "totp"},
            )
        return Enrolment(
            secret=domain.base32_secret(secret),
            otpauth_uri=domain.otpauth_uri(
                secret, account=user.login_identifier, issuer=self._settings.totp_issuer
            ),
        )

    async def complete_mfa(
        self, challenge_token: str, *, code: str | None, recovery_code: str | None, request_id: str
    ) -> SessionTokens:
        """Step 2: an authenticator code (confirming enrolment the first time) or a recovery code."""
        if (code is None) == (recovery_code is None):
            raise _invalid("code", "give either an authenticator code or a recovery code")
        claims = self._runtime.credential_tokens.verify_mfa_challenge(challenge_token)
        ctx = await self._user_context(claims.customer_id, claims.user_id, request_id)
        box = await self._secret_box()
        tokens: SessionTokens | None = None
        async with self._uow(ctx) as uow:
            user = self._check_challenge(await repository.lock_user(uow.db, claims.user_id), claims)
            if user.mfa_enrolled_at is None:
                if code is None:
                    raise _invalid("recovery_code", "recovery codes exist only after enrolment")
                tokens = await self._confirm_enrolment(uow, user.id, code, box)
            elif code is not None:
                tokens = await self._check_code(uow, user.id, code, box)
            else:
                tokens = await self._use_recovery_code(uow, user.id, recovery_code or "")
            if tokens is None:
                await self._record_failure(uow, user.id)
        if tokens is None:
            raise DomainError(ErrorCode.MFA_INVALID)
        return tokens

    async def _confirm_enrolment(
        self, uow: UnitOfWork, user_id: UUID, code: str, box: SecretBox
    ) -> SessionTokens | None:
        """The first code proves the authenticator holds the secret; then MFA is set up."""
        factor = await repository.lock_pending_factor(uow.db, user_id)
        if factor is None:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "start enrolment first")
        secret = box.open(
            factor.secret_ciphertext, key_id=factor.secret_key_id, context=_factor_context(user_id)
        )
        step = domain.match_totp(secret, code, self._now(), last_used_step=None)
        return None if step is None else await self._finish_enrolment(uow, user_id, factor.id, step)

    async def _check_code(
        self, uow: UnitOfWork, user_id: UUID, code: str, box: SecretBox
    ) -> SessionTokens | None:
        factor = await repository.lock_active_factor(uow.db, user_id)
        if factor is None:
            return None
        secret = box.open(
            factor.secret_ciphertext, key_id=factor.secret_key_id, context=_factor_context(user_id)
        )
        step = domain.match_totp(secret, code, self._now(), last_used_step=factor.last_used_step)
        if step is None:
            return None
        await repository.record_factor_step(uow.db, factor.id, step)
        return await self._open_session(uow, user_id, recovery_codes=None)

    async def _use_recovery_code(
        self, uow: UnitOfWork, user_id: UUID, recovery_code: str
    ) -> SessionTokens | None:
        if not await repository.use_recovery_code(
            uow.db, user_id, domain.hash_code(recovery_code), self._now()
        ):
            return None
        remaining = await repository.remaining_recovery_codes(uow.db, user_id)
        await uow.audit.record(
            action="iam.mfa.recovery_code_used",
            entity_type="iam.user",
            entity_id=user_id,
            after={"remaining_recovery_codes": remaining},
        )
        return await self._open_session(uow, user_id, recovery_codes=None)

    async def _finish_enrolment(
        self, uow: UnitOfWork, user_id: UUID, factor_id: UUID, step: int
    ) -> SessionTokens:
        now = self._now()
        await repository.confirm_factor(uow.db, factor_id, at=now, step=step)
        codes = domain.new_recovery_codes()
        await repository.insert_recovery_codes(
            uow.db, [(uuid7(), user_id, domain.hash_code(c)) for c in codes]
        )
        await repository.update_user(uow.db, user_id, actor=user_id, mfa_enrolled_at=now)
        await uow.audit.record(
            action="iam.mfa.enrolled",
            entity_type="iam.mfa_factor",
            entity_id=factor_id,
            after={"user_id": user_id, "kind": "totp", "recovery_codes_issued": len(codes)},
        )
        return await self._open_session(uow, user_id, recovery_codes=codes)

    # ============================================================================== sessions
    async def refresh(self, refresh_token: str, *, request_id: str) -> SessionTokens:
        """Rotate the refresh token. Presenting an older one revokes the session (LD-26)."""
        claims = self._runtime.credential_tokens.verify_refresh(refresh_token)
        ctx = await self._user_context(claims.customer_id, claims.user_id, request_id)
        tokens: SessionTokens | None = None
        async with self._uow(ctx) as uow:
            session = await repository.lock_session(uow.db, claims.session_id)
            now = self._now()
            if session is None or session.user_id != claims.user_id or session.principal_type != "user":
                raise _refused("Sign in again")
            if session.revoked_at is not None:
                raise DomainError(ErrorCode.SESSION_REVOKED)
            if now >= session.idle_expires_at or now >= session.absolute_expires_at:
                raise _refused("Sign in again")
            if not hmac.compare_digest(session.current_refresh_jti, claims.token_id):
                await repository.revoke_session(uow.db, session.id, at=now, reason="refresh_token_reuse")
                await uow.audit.record(
                    action="iam.session.revoked",
                    entity_type="iam.session",
                    entity_id=session.id,
                    after={"reason": "refresh_token_reuse"},
                )
            else:
                user = await repository.read_user(uow.db, claims.user_id)
                if user is None or user.status != "active":
                    raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
                refresh_jti = str(uuid7())
                idle = min(
                    now + timedelta(hours=self._settings.session_idle_hours), session.absolute_expires_at
                )
                await repository.rotate_session(
                    uow.db, session.id, refresh_jti=refresh_jti, at=now, idle_expires_at=idle
                )
                tokens = self._session_tokens(ctx.customer_id, claims.user_id, session.id, refresh_jti, idle)
        if tokens is None:
            raise DomainError(ErrorCode.SESSION_REVOKED)
        return tokens

    async def sign_out(self, refresh_token: str, *, request_id: str) -> None:
        """Revoke the session the refresh token belongs to. Idempotent; never says why it did nothing."""
        try:
            claims = self._runtime.credential_tokens.verify_refresh(refresh_token)
            ctx = await self._user_context(claims.customer_id, claims.user_id, request_id)
        except DomainError:
            return
        async with self._uow(ctx) as uow:
            session = await repository.lock_session(uow.db, claims.session_id)
            if session is None or session.user_id != claims.user_id or session.revoked_at is not None:
                return
            await repository.revoke_session(uow.db, session.id, at=self._now(), reason="sign_out")
            await uow.audit.record(
                action="iam.session.revoked",
                entity_type="iam.session",
                entity_id=session.id,
                after={"reason": "sign_out"},
            )

    # ============================================================================ activation
    async def activate(
        self, identifier: str, activation_code: str, new_password: str, *, request_id: str
    ) -> None:
        """A new user sets a password with the one-time code they were given (LLD 6.2)."""
        problems = domain.password_problems(new_password)
        if problems:
            raise DomainError(
                ErrorCode.VALIDATION_FAILED,
                errors=[FieldError(field="new_password", message=p.message) for p in problems],
            )
        entry = await self.directory.resolve(identifier)
        ctx: TenantContext | None = None
        if entry is not None and entry.principal_type == "user" and entry.status == "active":
            ctx = await self._quiet_context(
                entry.customer_id, request_id, module=LicenceModule.CORE, source="ui"
            )
        if entry is None or ctx is None:
            await self.hasher.burn(new_password)
            raise _refused(ACTIVATION_FAILED)
        user_id = entry.principal_id
        ctx = with_principal(ctx, Principal(type=PrincipalType.USER, id=user_id))
        code_hash = domain.hash_code(activation_code)

        async with self._uow(ctx, read_only=True) as uow:
            user = await repository.read_user(uow.db, user_id)
        valid = user is not None and self._activation_valid(
            user, normalise_login_identifier(identifier), code_hash
        )
        if not valid:
            await self.hasher.burn(new_password)
            if user is not None and user.status == "invited" and not self._locked(user):
                async with self._uow(ctx) as uow:
                    await self._record_failure(uow, user_id)
            raise _refused(ACTIVATION_FAILED)
        password_hash = await self.hasher.hash(new_password)

        activated = False
        async with self._uow(ctx) as uow:
            current = await repository.lock_user(uow.db, user_id)
            if current is not None and self._activation_valid(current, current.login_identifier, code_hash):
                await repository.update_user(
                    uow.db,
                    user_id,
                    actor=user_id,
                    status="active",
                    password_hash=password_hash,
                    failed_attempts=0,
                    activation_code_hash=None,
                    activation_expires_at=None,
                )
                await uow.audit.record(
                    action="iam.user.activated",
                    entity_type="iam.user",
                    entity_id=user_id,
                    before={"status": "invited"},
                    after={"status": "active"},
                )
                activated = True
        if not activated:
            raise _refused(ACTIVATION_FAILED)

    def _activation_valid(self, user: repository.UserRow, normalised: str, code_hash: bytes) -> bool:
        return (
            user.status == "invited"
            and user.login_identifier == normalised
            and not self._locked(user)
            and user.activation_code_hash is not None
            and user.activation_expires_at is not None
            and user.activation_expires_at > self._now()
            and hmac.compare_digest(user.activation_code_hash, code_hash)
        )

    # ======================================================================= API clients
    async def client_token(self, client_id: str, client_secret: str, *, request_id: str) -> ClientToken:
        """Client-credentials grant at /api/v1/oauth/token (AD-22, LLD 6.2)."""
        presented = domain.hash_client_secret(client_secret)
        entry = await self.directory.resolve(client_id)
        ctx: TenantContext | None = None
        if entry is not None and entry.principal_type == "api_client" and entry.status == "active":
            ctx = await self._quiet_context(
                entry.customer_id, request_id, module=LicenceModule.INTEGRATION, source="api"
            )
        if entry is None or ctx is None:
            hmac.compare_digest(self._dummy_client_hash, presented)
            raise _refused(CLIENT_AUTHENTICATION_FAILED)
        async with self._uow(ctx, read_only=True) as uow:
            client = await repository.get_api_client(uow.db, entry.principal_id)
        stored = client.secret_hash if client is not None else self._dummy_client_hash
        matched = hmac.compare_digest(stored, presented)
        if client is None or client.status != "active" or not matched:
            raise _refused(CLIENT_AUTHENTICATION_FAILED)
        return ClientToken(
            access_token=self._runtime.authenticator.issue_api_client_access(
                customer_id=ctx.customer_id, client_id=client.id
            ),
            expires_in=int(API_CLIENT_ACCESS_TTL.total_seconds()),
        )

    # ==================================================================== creating principals
    async def create_user(
        self, uow: UnitOfWork, *, login_identifier: str, display_name: str, email: str | None = None
    ) -> CreatedUser:
        """Reserve -> create -> activate (LLD 6.3).

        The identifier is reserved in the Login Directory, then the user, its audit entry and an
        ``iam.user.created`` event are written in the caller's transaction after a licence
        user-limit check under a transaction-level advisory lock. After commit the directory entry
        is activated; if that fails it is retried by reconciliation and the user stays invited.
        The user receives a one-time activation code to set a password.
        """
        try:
            normalised = normalise_login_identifier(login_identifier)
        except InvalidIdentifierError as exc:
            raise _invalid("login_identifier", str(exc)) from None
        if not display_name.strip():
            raise _invalid("display_name", "is required")
        await uow.db.execute(text("SELECT pg_advisory_xact_lock(hashtext('iam.licensed_users'))"))
        if await repository.count_licensed_users(uow.db) >= uow.ctx.snapshot.max_users:
            raise DomainError(ErrorCode.LIMIT_EXCEEDED, "the licence user limit has been reached")

        user_id = uuid7()
        await self._reserve(uow.ctx, PrincipalType.USER, user_id, normalised)
        code = domain.new_activation_code()
        expires = self._now() + timedelta(hours=self._settings.activation_code_hours)
        actor = uow.ctx.principal.id if uow.ctx.principal else None
        await repository.insert_user(
            uow.db,
            user_id=user_id,
            login_identifier=normalised,
            display_name=display_name.strip(),
            email=email,
            activation_code_hash=domain.hash_code(code),
            activation_expires_at=expires,
            actor=actor,
        )
        await uow.audit.record(
            action="iam.user.created",
            entity_type="iam.user",
            entity_id=user_id,
            after={"login_identifier": normalised, "display_name": display_name.strip(), "status": "invited"},
        )
        await uow.events.publish(
            event_type=events.USER_CREATED,
            subject_type="iam.user",
            subject_id=user_id,
            subject_version=1,
            data={"user_id": user_id, "login_identifier": normalised, "status": "invited"},
        )
        self._activate_after_commit(uow, PrincipalType.USER, user_id, normalised)
        return CreatedUser(user_id=user_id, activation_code=code, activation_expires_at=expires)

    async def create_api_client(
        self, uow: UnitOfWork, *, name: str, rate_limit_per_minute: int = 600
    ) -> CreatedApiClient:
        """A per-customer API credential (AD-22). The secret is returned once and stored hashed."""
        if not name.strip():
            raise _invalid("name", "is required")
        client_id = uuid7()
        identifier = str(client_id)
        await self._reserve(uow.ctx, PrincipalType.API_CLIENT, client_id, identifier)
        secret = domain.new_client_secret()
        await repository.insert_api_client(
            uow.db,
            client_id=client_id,
            name=name.strip(),
            secret_hash=domain.hash_client_secret(secret),
            rate_limit_per_minute=rate_limit_per_minute,
            actor=uow.ctx.principal.id if uow.ctx.principal else None,
        )
        await uow.audit.record(
            action="iam.api_client.created",
            entity_type="iam.api_client",
            entity_id=client_id,
            after={"name": name.strip(), "rate_limit_per_minute": rate_limit_per_minute, "status": "active"},
        )
        await uow.events.publish(
            event_type=events.API_CLIENT_CREATED,
            subject_type="iam.api_client",
            subject_id=client_id,
            subject_version=1,
            data={"client_id": client_id},
        )
        self._activate_after_commit(uow, PrincipalType.API_CLIENT, client_id, identifier)
        return CreatedApiClient(client_id=client_id, client_secret=secret)

    async def _reserve(
        self, ctx: TenantContext, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> None:
        try:
            await self.directory.client.reserve(
                customer_id=ctx.customer_id,
                principal_type=principal_type,
                principal_id=principal_id,
                identifier=identifier,
            )
        except RegistryUnavailableError:
            raise DomainError(ErrorCode.PLATFORM_UNAVAILABLE, headers={"Retry-After": "2"}) from None

    def _activate_after_commit(
        self, uow: UnitOfWork, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> None:
        ctx = uow.ctx

        async def _activate() -> None:
            try:
                await self.activate_directory_entry(ctx, principal_type, principal_id, identifier)
            except Exception:
                log.exception("directory activation failed; reconciliation will retry")

        uow.on_commit(_activate)

    async def activate_directory_entry(
        self, ctx: TenantContext, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> None:
        """Complete reserve -> create -> activate (LLD 6.3). Idempotent.

        If another customer took the identifier while the reservation had lapsed, the user is
        suspended with the reason "identifier in use" (LLD 6.3 failure table).
        """
        try:
            await self.directory.client.activate(
                customer_id=ctx.customer_id,
                principal_type=principal_type,
                principal_id=principal_id,
                identifier=identifier,
            )
        except DomainError as exc:
            if exc.code is not ErrorCode.LOGIN_IDENTIFIER_TAKEN or principal_type is not PrincipalType.USER:
                raise
            async with self._uow(ctx) as uow:
                user = await repository.lock_user(uow.db, principal_id)
                if user is not None and user.status == "invited":
                    await repository.update_user(uow.db, principal_id, actor=None, status="suspended")
                    await uow.audit.record(
                        action="iam.user.suspended",
                        entity_type="iam.user",
                        entity_id=principal_id,
                        before={"status": "invited"},
                        after={"status": "suspended"},
                        reason="identifier in use",
                    )
            return
        self.directory.forget(identifier)
