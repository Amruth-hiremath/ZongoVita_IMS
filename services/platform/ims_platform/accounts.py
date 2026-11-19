"""ZongoVita staff accounts and Platform Console sign-in (LLD section 4 platform_users, 6.2, 15;
AD-23: MFA mandatory for platform staff; LD-79, LD-80).

Staff sign in the way customer users do (Core's identity module), against the Control-Plane
database instead of a customer database:

* Password step, then TOTP (enrolment at first sign-in; ten single-use recovery codes). A session
  and an access token exist only after MFA.
* Constant work (LD-80): every sign-in path runs exactly one Argon2id verification, against a
  dummy hash where there is nothing real to check, and fails with the same generic answer. The
  hash runs outside any transaction.
* Five failures (password, MFA or activation code) lock the account for 15 minutes.
* Refresh rotates on every use; presenting an older refresh token revokes the session (LD-26).

Platform tokens are signed with the Platform Service's own key and carry the platform issuer
and audiences, so Core rejects them (LLD 6.2 "Platform: different issuer and audience").

Staff roles are the two staff actors of HLD section 3: ``system_admin`` (customers, licences and
licence state, provisioning, migrations) and ``support_engineer`` (support sessions under a
customer's grant, unit 12).
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common import auth_codes
from ims_common.clock import Clock
from ims_common.credentials import PasswordHasher, SecretBox
from ims_common.identifiers import InvalidIdentifierError, normalise_login_identifier
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_common.tokens import TokenCodec, TokenError
from ims_contracts.errors import ErrorCode, FieldError
from ims_platform.registry import Actor, audit_change

PLATFORM_ISSUER = "ims-platform"
AUDIENCE_CONSOLE = "platform-console"
AUDIENCE_REFRESH = "platform-refresh"
AUDIENCE_MFA = "platform-mfa"
ACCESS_TTL = timedelta(minutes=15)  # LLD 6.2 "Platform ... 15 min"
SIGN_IN_FAILED = "Sign-in failed"
ACTIVATION_FAILED = "Activation failed"


class StaffRole(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    SUPPORT_ENGINEER = "support_engineer"


@dataclass(frozen=True)
class AccountSettings:
    session_idle_hours: int = 8
    session_absolute_days: int = 7
    mfa_challenge_minutes: int = 5
    lockout_threshold: int = 5
    lockout_minutes: int = 15
    activation_code_hours: int = 72
    totp_issuer: str = "ZongoVita Platform"


def _refused(detail: str = SIGN_IN_FAILED) -> DomainError:
    return DomainError(ErrorCode.AUTH_REQUIRED, detail, headers={"WWW-Authenticate": "Bearer"})


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


def _factor_context(user_id: UUID) -> str:
    """Binds a sealed TOTP secret to its account: a copy on another row does not open."""
    return f"platform.platform_users:mfa:{user_id}"


# ==================================================================================== rows
_USER_COLUMNS = (
    "id, login_identifier, display_name, email, role, status, password_hash, failed_attempts, "
    "locked_until, activation_code_hash, activation_expires_at, mfa_ciphertext, mfa_key_id, "
    "mfa_enrolled_at, mfa_last_used_step, mfa_pending_ciphertext, mfa_pending_key_id, "
    "mfa_challenge_jti, mfa_challenge_expires_at, created_at, updated_at, version"
)
_READ_USER = text("SELECT " + _USER_COLUMNS + " FROM platform.platform_users WHERE id = :id")  # noqa: S608
_LOCK_USER = text("SELECT " + _USER_COLUMNS + " FROM platform.platform_users WHERE id = :id FOR UPDATE")  # noqa: S608
_BY_LOGIN = text(
    "SELECT " + _USER_COLUMNS + " FROM platform.platform_users WHERE login_identifier = :login"  # noqa: S608
)
_LIST_USERS = text("SELECT " + _USER_COLUMNS + " FROM platform.platform_users ORDER BY id")  # noqa: S608


@dataclass(frozen=True)
class StaffRow:
    id: UUID
    login_identifier: str
    display_name: str
    email: str | None
    role: str
    status: str
    password_hash: str | None
    failed_attempts: int
    locked_until: datetime | None
    activation_code_hash: bytes | None
    activation_expires_at: datetime | None
    mfa_ciphertext: bytes | None
    mfa_key_id: str | None
    mfa_enrolled_at: datetime | None
    mfa_last_used_step: int | None
    mfa_pending_ciphertext: bytes | None
    mfa_pending_key_id: str | None
    mfa_challenge_jti: str | None
    mfa_challenge_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


def _row(mapping: Any) -> StaffRow | None:
    if mapping is None:
        return None
    data = dict(mapping)
    for name in ("activation_code_hash", "mfa_ciphertext", "mfa_pending_ciphertext"):
        if data[name] is not None:
            data[name] = bytes(data[name])
    return StaffRow(**data)


async def _read(conn: AsyncConnection, user_id: UUID, *, lock: bool = False) -> StaffRow | None:
    return _row((await conn.execute(_LOCK_USER if lock else _READ_USER, {"id": user_id})).mappings().first())


async def _update(conn: AsyncConnection, user_id: UUID, actor: str, **fields: object) -> int:
    allowed = {
        "status",
        "password_hash",
        "failed_attempts",
        "locked_until",
        "activation_code_hash",
        "activation_expires_at",
        "mfa_ciphertext",
        "mfa_key_id",
        "mfa_enrolled_at",
        "mfa_last_used_step",
        "mfa_pending_ciphertext",
        "mfa_pending_key_id",
        "mfa_challenge_jti",
        "mfa_challenge_expires_at",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not an updatable staff column: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = :{name}" for name in fields)
    statement = text(
        "UPDATE platform.platform_users SET "  # noqa: S608 - allow-listed columns
        + assignments
        + ", updated_at = now(), updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
    )
    return int((await conn.execute(statement, {**fields, "actor": actor, "id": user_id})).scalar_one())


# ================================================================================== results
@dataclass(frozen=True)
class StaffPrincipal:
    user_id: UUID
    session_id: UUID
    role: StaffRole
    display_name: str
    login_identifier: str
    email: str | None

    @property
    def actor(self) -> Actor:
        return Actor(f"platform_user:{self.user_id}")


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
class CreatedStaff:
    user: StaffRow
    activation_code: str
    activation_expires_at: datetime


# ================================================================================== service
class AccountsService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        codec: TokenCodec,
        box: SecretBox,
        hasher: PasswordHasher,
        clock: Clock,
        settings: AccountSettings | None = None,
    ) -> None:
        self._engine = engine
        self._codec = codec
        self._box = box
        self.hasher = hasher
        self._clock = clock
        self._settings = settings or AccountSettings()

    def _now(self) -> datetime:
        return self._clock.now()

    def _locked(self, user: StaffRow) -> bool:
        return user.locked_until is not None and user.locked_until > self._now()

    # ------------------------------------------------------------------------ token helpers
    def _issue(self, audience: str, user_id: UUID, ttl: timedelta, *, token_id: str, **claims: Any) -> str:
        return self._codec.encode(
            subject=str(user_id), audience=audience, ttl=ttl, claims=claims, token_id=token_id
        )

    def _decode(self, token: str, audience: str) -> dict[str, Any]:
        try:
            return self._codec.decode(token, audience=audience)
        except TokenError as exc:
            if exc.reason == "expired" and audience == AUDIENCE_CONSOLE:
                raise DomainError(ErrorCode.TOKEN_EXPIRED, headers={"WWW-Authenticate": "Bearer"}) from None
            raise _refused("Sign in again") from None

    # ----------------------------------------------------------------------- failure counting
    async def _record_failure(self, conn: AsyncConnection, user_id: UUID) -> None:
        user = await _read(conn, user_id, lock=True)
        if user is None:
            return
        attempts = user.failed_attempts + 1
        actor = f"platform_user:{user_id}"
        if attempts < self._settings.lockout_threshold:
            await _update(conn, user_id, actor, failed_attempts=attempts)
            return
        until = self._now() + timedelta(minutes=self._settings.lockout_minutes)
        await _update(
            conn,
            user_id,
            actor,
            failed_attempts=0,
            locked_until=until,
            mfa_challenge_jti=None,
            mfa_challenge_expires_at=None,
        )
        await audit_change(
            conn,
            Actor(actor),
            "platform.user.locked",
            "platform_user",
            user_id,
            None,
            after={"locked_until": until.isoformat(), "failed_attempts": attempts},
        )

    # ------------------------------------------------------------------------------ sign-in
    async def sign_in(self, identifier: str, password: str) -> SignInChallenge:
        """Password step. One Argon2id verification on every path, one generic failure (LD-80)."""
        try:
            normalised = normalise_login_identifier(identifier)
        except InvalidIdentifierError:
            normalised = None
        user = None
        if normalised is not None:
            async with self._engine.connect() as conn:
                user = _row((await conn.execute(_BY_LOGIN, {"login": normalised})).mappings().first())
        usable = user is not None and user.status == "active" and not self._locked(user)
        stored = user.password_hash if usable and user is not None else None
        matched = await self.hasher.verify(stored, password)  # the one verification (LD-80)
        if not usable or user is None:
            raise _refused()
        rehashed = (
            await self.hasher.hash(password) if matched and self.hasher.needs_rehash(stored or "") else None
        )

        challenge: SignInChallenge | None = None
        async with self._engine.begin() as conn:
            current = await _read(conn, user.id, lock=True)
            if current is None:
                pass
            elif not matched:
                await self._record_failure(conn, user.id)
            elif current.password_hash == stored and current.status == "active" and not self._locked(current):
                minutes = self._settings.mfa_challenge_minutes
                jti = str(uuid7())
                fields: dict[str, object] = {
                    "failed_attempts": 0,
                    "mfa_challenge_jti": jti,
                    "mfa_challenge_expires_at": self._now() + timedelta(minutes=minutes),
                }
                if rehashed is not None:
                    fields["password_hash"] = rehashed
                await _update(conn, user.id, f"platform_user:{user.id}", **fields)
                challenge = SignInChallenge(
                    challenge_token=self._issue(
                        AUDIENCE_MFA, user.id, timedelta(minutes=minutes), token_id=jti
                    ),
                    enrolment_required=current.mfa_enrolled_at is None,
                    expires_in=minutes * 60,
                )
        if challenge is None:
            raise _refused()
        return challenge

    def _check_challenge(self, user: StaffRow | None, claims: dict[str, Any]) -> StaffRow:
        if (
            user is None
            or user.status != "active"
            or self._locked(user)
            or user.mfa_challenge_jti is None
            or user.mfa_challenge_expires_at is None
            or user.mfa_challenge_expires_at <= self._now()
            or not hmac.compare_digest(user.mfa_challenge_jti, str(claims.get("jti", "")))
        ):
            raise _refused()
        return user

    async def begin_enrolment(self, challenge_token: str) -> Enrolment:
        """First sign-in: create the authenticator secret; the first code confirms it (LD-79)."""
        claims = self._decode(challenge_token, AUDIENCE_MFA)
        user_id = UUID(claims["sub"])
        async with self._engine.begin() as conn:
            user = self._check_challenge(await _read(conn, user_id, lock=True), claims)
            if user.mfa_enrolled_at is not None:
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION, "multi-factor authentication is already set up"
                )
            secret = auth_codes.new_totp_secret()
            sealed, key_id = self._box.seal(secret, context=_factor_context(user_id))
            await _update(
                conn,
                user_id,
                f"platform_user:{user_id}",
                mfa_pending_ciphertext=sealed,
                mfa_pending_key_id=key_id,
            )
            await audit_change(
                conn,
                Actor(f"platform_user:{user_id}"),
                "platform.mfa.enrolment_started",
                "platform_user",
                user_id,
                None,
            )
        return Enrolment(
            secret=auth_codes.base32_secret(secret),
            otpauth_uri=auth_codes.otpauth_uri(
                secret, account=user.login_identifier, issuer=self._settings.totp_issuer
            ),
        )

    async def complete_mfa(
        self, challenge_token: str, *, code: str | None, recovery_code: str | None
    ) -> SessionTokens:
        if (code is None) == (recovery_code is None):
            raise _invalid("code", "give either an authenticator code or a recovery code")
        claims = self._decode(challenge_token, AUDIENCE_MFA)
        user_id = UUID(claims["sub"])
        tokens: SessionTokens | None = None
        async with self._engine.begin() as conn:
            user = self._check_challenge(await _read(conn, user_id, lock=True), claims)
            if user.mfa_enrolled_at is None:
                if code is None:
                    raise _invalid("recovery_code", "recovery codes exist only after enrolment")
                tokens = await self._confirm_enrolment(conn, user, code)
            elif code is not None:
                tokens = await self._check_code(conn, user, code)
            else:
                tokens = await self._use_recovery_code(conn, user, recovery_code or "")
            if tokens is None:
                await self._record_failure(conn, user_id)
        if tokens is None:
            raise DomainError(ErrorCode.MFA_INVALID)
        return tokens

    async def _confirm_enrolment(
        self, conn: AsyncConnection, user: StaffRow, code: str
    ) -> SessionTokens | None:
        if user.mfa_pending_ciphertext is None or user.mfa_pending_key_id is None:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "start enrolment first")
        secret = self._box.open(
            user.mfa_pending_ciphertext, key_id=user.mfa_pending_key_id, context=_factor_context(user.id)
        )
        step = auth_codes.match_totp(secret, code, self._now(), last_used_step=None)
        if step is None:
            return None
        now = self._now()
        actor = f"platform_user:{user.id}"
        await _update(
            conn,
            user.id,
            actor,
            mfa_ciphertext=user.mfa_pending_ciphertext,
            mfa_key_id=user.mfa_pending_key_id,
            mfa_enrolled_at=now,
            mfa_last_used_step=step,
            mfa_pending_ciphertext=None,
            mfa_pending_key_id=None,
        )
        codes = auth_codes.new_recovery_codes()
        await conn.execute(
            text(
                "INSERT INTO platform.platform_recovery_codes (id, user_id, code_hash) VALUES (:id, "
                ":user, :hash)"
            ),
            [{"id": uuid7(), "user": user.id, "hash": auth_codes.hash_code(c)} for c in codes],
        )
        await audit_change(
            conn,
            Actor(actor),
            "platform.mfa.enrolled",
            "platform_user",
            user.id,
            None,
            after={"recovery_codes_issued": len(codes)},
        )
        return await self._open_session(conn, user.id, recovery_codes=codes)

    async def _check_code(self, conn: AsyncConnection, user: StaffRow, code: str) -> SessionTokens | None:
        if user.mfa_ciphertext is None or user.mfa_key_id is None:
            return None
        secret = self._box.open(user.mfa_ciphertext, key_id=user.mfa_key_id, context=_factor_context(user.id))
        step = auth_codes.match_totp(secret, code, self._now(), last_used_step=user.mfa_last_used_step)
        if step is None:
            return None
        await _update(conn, user.id, f"platform_user:{user.id}", mfa_last_used_step=step)
        return await self._open_session(conn, user.id, recovery_codes=None)

    async def _use_recovery_code(
        self, conn: AsyncConnection, user: StaffRow, recovery_code: str
    ) -> SessionTokens | None:
        used = await conn.execute(
            text(
                "UPDATE platform.platform_recovery_codes SET used_at = :at WHERE user_id = :user "
                "AND code_hash = :hash AND used_at IS NULL AND revoked_at IS NULL"
            ),
            {"at": self._now(), "user": user.id, "hash": auth_codes.hash_code(recovery_code)},
        )
        if not used.rowcount:
            return None
        await audit_change(
            conn,
            Actor(f"platform_user:{user.id}"),
            "platform.mfa.recovery_code_used",
            "platform_user",
            user.id,
            None,
        )
        return await self._open_session(conn, user.id, recovery_codes=None)

    async def _open_session(
        self, conn: AsyncConnection, user_id: UUID, *, recovery_codes: list[str] | None
    ) -> SessionTokens:
        now = self._now()
        actor = f"platform_user:{user_id}"
        await _update(
            conn, user_id, actor, failed_attempts=0, mfa_challenge_jti=None, mfa_challenge_expires_at=None
        )
        session_id = uuid7()
        refresh_jti = str(uuid7())
        absolute = now + timedelta(days=self._settings.session_absolute_days)
        idle = min(now + timedelta(hours=self._settings.session_idle_hours), absolute)
        await conn.execute(
            text(
                "INSERT INTO platform.platform_sessions (id, user_id, current_refresh_jti, mfa_verified_at, "
                "last_refreshed_at, idle_expires_at, absolute_expires_at) "
                "VALUES (:id, :user, :jti, :now, :now, :idle, :absolute)"
            ),
            {
                "id": session_id,
                "user": user_id,
                "jti": refresh_jti,
                "now": now,
                "idle": idle,
                "absolute": absolute,
            },
        )
        await audit_change(
            conn,
            Actor(actor),
            "platform.session.created",
            "platform_session",
            session_id,
            None,
            after={"user_id": str(user_id), "idle_expires_at": idle.isoformat()},
        )
        return self._tokens(user_id, session_id, refresh_jti, idle, recovery_codes)

    def _tokens(
        self,
        user_id: UUID,
        session_id: UUID,
        refresh_jti: str,
        idle_expires_at: datetime,
        recovery_codes: list[str] | None = None,
    ) -> SessionTokens:
        return SessionTokens(
            access_token=self._issue(
                AUDIENCE_CONSOLE, user_id, ACCESS_TTL, token_id=str(uuid7()), sid=str(session_id)
            ),
            refresh_token=self._issue(
                AUDIENCE_REFRESH,
                user_id,
                idle_expires_at - self._now(),
                token_id=refresh_jti,
                sid=str(session_id),
            ),
            expires_in=int(ACCESS_TTL.total_seconds()),
            refresh_expires_at=idle_expires_at,
            recovery_codes=recovery_codes,
        )

    # ------------------------------------------------------------------------------ sessions
    async def refresh(self, refresh_token: str) -> SessionTokens:
        """Rotate the refresh token; reusing an older one revokes the session (LD-26)."""
        claims = self._decode(refresh_token, AUDIENCE_REFRESH)
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
        tokens: SessionTokens | None = None
        revoked_for_reuse = False
        async with self._engine.begin() as conn:
            session = (
                (
                    await conn.execute(
                        text(
                            "SELECT s.user_id, s.current_refresh_jti, s.idle_expires_at, "
                            "s.absolute_expires_at, "
                            "s.revoked_at, u.status FROM platform.platform_sessions s "
                            "JOIN platform.platform_users u ON u.id = s.user_id WHERE s.id = :id FOR "
                            "UPDATE OF s"
                        ),
                        {"id": session_id},
                    )
                )
                .mappings()
                .first()
            )
            now = self._now()
            if session is None or session["user_id"] != user_id:
                raise _refused("Sign in again")
            if session["revoked_at"] is not None:
                raise DomainError(ErrorCode.SESSION_REVOKED)
            if now >= session["idle_expires_at"] or now >= session["absolute_expires_at"]:
                raise DomainError(ErrorCode.SESSION_REVOKED)
            if session["status"] != "active":
                raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
            if not hmac.compare_digest(session["current_refresh_jti"], str(claims.get("jti", ""))):
                await self._revoke(conn, session_id, "refresh token reused")
                revoked_for_reuse = True
            else:
                new_jti = str(uuid7())
                idle = min(
                    now + timedelta(hours=self._settings.session_idle_hours), session["absolute_expires_at"]
                )
                await conn.execute(
                    text(
                        "UPDATE platform.platform_sessions SET current_refresh_jti = :jti, "
                        "last_refreshed_at = :now, "
                        "idle_expires_at = :idle WHERE id = :id"
                    ),
                    {"jti": new_jti, "now": now, "idle": idle, "id": session_id},
                )
                tokens = self._tokens(user_id, session_id, new_jti, idle)
        if revoked_for_reuse or tokens is None:
            raise DomainError(ErrorCode.SESSION_REVOKED)
        return tokens

    async def _revoke(self, conn: AsyncConnection, session_id: UUID, reason: str) -> None:
        await conn.execute(
            text(
                "UPDATE platform.platform_sessions SET revoked_at = :at, revoke_reason = :reason "
                "WHERE id = :id AND revoked_at IS NULL"
            ),
            {"at": self._now(), "reason": reason, "id": session_id},
        )

    async def sign_out(self, refresh_token: str) -> None:
        try:
            claims = self._codec.decode(refresh_token, audience=AUDIENCE_REFRESH)
        except TokenError:
            return  # signing out with an unusable token changes nothing
        async with self._engine.begin() as conn:
            await self._revoke(conn, UUID(claims["sid"]), "signed out")

    async def authenticate(self, authorization: str | None) -> StaffPrincipal:
        """Every /platform/v1 request: a live platform access token, a live session, an active
        account (primary-key reads, LD-28)."""
        if not authorization or not authorization.lower().startswith("bearer "):
            raise _refused("Sign in")
        claims = self._decode(authorization[7:].strip(), AUDIENCE_CONSOLE)
        session_id = UUID(claims["sid"])
        async with self._engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            "SELECT s.user_id, s.revoked_at, s.idle_expires_at, s.absolute_expires_at, "
                            "u.status, "
                            "u.role, u.display_name, u.login_identifier, u.email FROM "
                            "platform.platform_sessions s "
                            "JOIN platform.platform_users u ON u.id = s.user_id WHERE s.id = :id"
                        ),
                        {"id": session_id},
                    )
                )
                .mappings()
                .first()
            )
        now = self._now()
        if (
            row is None
            or str(row["user_id"]) != claims["sub"]
            or row["revoked_at"] is not None
            or now >= row["idle_expires_at"]
            or now >= row["absolute_expires_at"]
        ):
            raise DomainError(ErrorCode.SESSION_REVOKED)
        if row["status"] != "active":
            raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
        return StaffPrincipal(
            user_id=row["user_id"],
            session_id=session_id,
            role=StaffRole(row["role"]),
            display_name=row["display_name"],
            login_identifier=row["login_identifier"],
            email=row["email"],
        )

    # ---------------------------------------------------------------------------- activation
    async def activate(self, identifier: str, activation_code: str, new_password: str) -> None:
        """Set a first password with the one-time activation code; failures count to lockout."""
        problems = auth_codes.password_problems(new_password)
        if problems:
            raise DomainError(
                ErrorCode.VALIDATION_FAILED,
                errors=[FieldError(field="new_password", message=p.message) for p in problems],
            )
        try:
            normalised = normalise_login_identifier(identifier)
        except InvalidIdentifierError:
            normalised = None
        code_hash = auth_codes.hash_code(activation_code)
        user = None
        if normalised is not None:
            async with self._engine.connect() as conn:
                user = _row((await conn.execute(_BY_LOGIN, {"login": normalised})).mappings().first())
        valid = (
            user is not None
            and user.status == "invited"
            and not self._locked(user)
            and user.activation_code_hash is not None
            and user.activation_expires_at is not None
            and user.activation_expires_at > self._now()
            and hmac.compare_digest(user.activation_code_hash, code_hash)
        )
        new_hash = await self.hasher.hash(new_password) if valid else None
        if not valid:
            await self.hasher.burn(new_password)
            if user is not None and user.status == "invited":
                async with self._engine.begin() as conn:
                    await self._record_failure(conn, user.id)
            raise _refused(ACTIVATION_FAILED)
        assert user is not None
        async with self._engine.begin() as conn:
            current = await _read(conn, user.id, lock=True)
            if current is None or current.status != "invited" or current.activation_code_hash != code_hash:
                raise _refused(ACTIVATION_FAILED)
            actor = f"platform_user:{user.id}"
            await _update(
                conn,
                user.id,
                actor,
                status="active",
                password_hash=new_hash,
                activation_code_hash=None,
                activation_expires_at=None,
                failed_attempts=0,
            )
            await audit_change(
                conn,
                Actor(actor),
                "platform.user.activated",
                "platform_user",
                user.id,
                None,
                after={"status": "active"},
            )

    # ------------------------------------------------------------------------------- staff
    async def list_users(self) -> list[StaffRow]:
        async with self._engine.connect() as conn:
            return [
                r for r in (_row(m) for m in (await conn.execute(_LIST_USERS)).mappings()) if r is not None
            ]

    async def get_user(self, user_id: UUID) -> StaffRow:
        async with self._engine.connect() as conn:
            user = await _read(conn, user_id)
        if user is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return user

    async def create_user(
        self, actor: Actor, *, login_identifier: str, display_name: str, email: str | None, role: StaffRole
    ) -> CreatedStaff:
        """A staff account, invited with a one-time activation code shown once (LLD 6.2, #21)."""
        try:
            normalised = normalise_login_identifier(login_identifier)
        except InvalidIdentifierError as exc:
            raise _invalid("login_identifier", str(exc)) from None
        name = display_name.strip()
        if not name:
            raise _invalid("display_name", "is required")
        code = auth_codes.new_activation_code()
        expires = self._now() + timedelta(hours=self._settings.activation_code_hours)
        user_id = uuid7()
        async with self._engine.begin() as conn:
            taken = (await conn.execute(_BY_LOGIN, {"login": normalised})).first()
            if taken is not None:
                raise _invalid("login_identifier", "is already in use")
            await conn.execute(
                text(
                    "INSERT INTO platform.platform_users (id, login_identifier, display_name, email, role, "
                    "activation_code_hash, activation_expires_at, created_by, updated_by) "
                    "VALUES (:id, :login, :name, :email, :role, :code, :expires, :actor, :actor)"
                ),
                {
                    "id": user_id,
                    "login": normalised,
                    "name": name,
                    "email": email,
                    "role": role.value,
                    "code": auth_codes.hash_code(code),
                    "expires": expires,
                    "actor": actor.ref,
                },
            )
            await audit_change(
                conn,
                actor,
                "platform.user.created",
                "platform_user",
                user_id,
                None,
                after={
                    "login_identifier": normalised,
                    "display_name": name,
                    "role": role.value,
                    "status": "invited",
                },
            )
            user = await _read(conn, user_id)
        assert user is not None
        return CreatedStaff(user=user, activation_code=code, activation_expires_at=expires)

    async def deactivate_user(self, actor: Actor, user_id: UUID, *, reason: str | None) -> StaffRow:
        """Ends the person's sessions at once. Accounts are never deleted."""
        async with self._engine.begin() as conn:
            user = await _read(conn, user_id, lock=True)
            if user is None:
                raise DomainError(ErrorCode.NOT_FOUND)
            if user.status == "deactivated":
                raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "the account is already deactivated")
            await _update(
                conn,
                user_id,
                actor.ref,
                status="deactivated",
                activation_code_hash=None,
                activation_expires_at=None,
                mfa_challenge_jti=None,
                mfa_challenge_expires_at=None,
            )
            await conn.execute(
                text(
                    "UPDATE platform.platform_sessions SET revoked_at = :at, revoke_reason = 'account "
                    "deactivated' "
                    "WHERE user_id = :user AND revoked_at IS NULL"
                ),
                {"at": self._now(), "user": user_id},
            )
            await audit_change(
                conn,
                actor,
                "platform.user.deactivated",
                "platform_user",
                user_id,
                None,
                before={"status": user.status},
                after={"status": "deactivated"},
                reason=reason,
            )
            updated = await _read(conn, user_id)
        assert updated is not None
        return updated

    async def has_system_admin(self) -> bool:
        async with self._engine.connect() as conn:
            return bool(
                (
                    await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM platform.platform_users "
                            "WHERE role = 'system_admin' AND status IN ('invited', 'active'))"
                        )
                    )
                ).scalar_one()
            )
