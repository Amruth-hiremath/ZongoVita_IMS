"""SQL for the iam schema's identity tables. Nothing here decides anything; service.py does."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class UserRow:
    id: UUID
    login_identifier: str
    display_name: str
    status: str
    password_hash: str | None
    failed_attempts: int
    locked_until: datetime | None
    mfa_enrolled_at: datetime | None
    mfa_challenge_jti: str | None
    mfa_challenge_expires_at: datetime | None
    activation_code_hash: bytes | None
    activation_expires_at: datetime | None
    version: int


_USER_COLUMNS = (
    "id, login_identifier, display_name, status, password_hash, failed_attempts, locked_until, "
    "mfa_enrolled_at, mfa_challenge_jti, mfa_challenge_expires_at, activation_code_hash, "
    "activation_expires_at, version"
)
_LOCK_USER = text("SELECT " + _USER_COLUMNS + " FROM iam.users WHERE id = :id FOR UPDATE")  # noqa: S608 - fixed columns


async def lock_user(conn: AsyncConnection, user_id: UUID) -> UserRow | None:
    row = (await conn.execute(_LOCK_USER, {"id": user_id})).mappings().first()
    if row is None:
        return None
    data = dict(row)
    if data["activation_code_hash"] is not None:
        data["activation_code_hash"] = bytes(data["activation_code_hash"])
    return UserRow(**data)


async def count_licensed_users(conn: AsyncConnection) -> int:
    """Invited and active users count against the licence user limit (LLD 5.1)."""
    return int(
        (
            await conn.execute(text("SELECT count(*) FROM iam.users WHERE status IN ('invited', 'active')"))
        ).scalar_one()
    )


async def insert_user(
    conn: AsyncConnection,
    *,
    user_id: UUID,
    login_identifier: str,
    display_name: str,
    email: str | None,
    activation_code_hash: bytes,
    activation_expires_at: datetime,
    actor: UUID | None,
    department_id: UUID | None = None,
    home_site_id: UUID | None = None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO iam.users (id, login_identifier, display_name, email, department_id, home_site_id, "
            "status, activation_code_hash, activation_expires_at, created_by, updated_by) "
            "VALUES (:id, :login, :name, :email, :department, :home_site, 'invited', :code, :expires, "
            ":actor, :actor)"
        ),
        {
            "id": user_id,
            "login": login_identifier,
            "name": display_name,
            "email": email,
            "department": department_id,
            "home_site": home_site_id,
            "code": activation_code_hash,
            "expires": activation_expires_at,
            "actor": actor,
        },
    )


async def update_user(conn: AsyncConnection, user_id: UUID, *, actor: UUID | None, **fields: object) -> int:
    """Set the given columns, bump the version; returns the new version."""
    allowed = {
        "status",
        "password_hash",
        "failed_attempts",
        "locked_until",
        "mfa_enrolled_at",
        "mfa_challenge_jti",
        "mfa_challenge_expires_at",
        "activation_code_hash",
        "activation_expires_at",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not an updatable user column: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = :{name}" for name in fields)
    # Column names come from the allow-list above, values are bound parameters.
    statement = text(
        "UPDATE iam.users SET "  # noqa: S608 - allow-listed columns
        + assignments
        + ", updated_at = now(), updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
    )
    return int((await conn.execute(statement, {**fields, "actor": actor, "id": user_id})).scalar_one())


# ------------------------------------------------------------------------------ MFA factors
@dataclass(frozen=True)
class FactorRow:
    id: UUID
    secret_ciphertext: bytes
    secret_key_id: str
    enrolled_at: datetime | None
    last_used_step: int | None


def _factor(row: object) -> FactorRow | None:
    if row is None:
        return None
    data = dict(row)  # type: ignore[call-overload]
    data["secret_ciphertext"] = bytes(data["secret_ciphertext"])
    return FactorRow(**data)


async def lock_active_factor(conn: AsyncConnection, user_id: UUID) -> FactorRow | None:
    row = (
        (
            await conn.execute(
                text(
                    "SELECT id, secret_ciphertext, secret_key_id, enrolled_at, "
                    "last_used_step FROM iam.mfa_factors "
                    "WHERE user_id = :u AND enrolled_at IS NOT NULL AND revoked_at IS NULL FOR UPDATE"
                ),
                {"u": user_id},
            )
        )
        .mappings()
        .first()
    )
    return _factor(row)


async def lock_pending_factor(conn: AsyncConnection, user_id: UUID) -> FactorRow | None:
    row = (
        (
            await conn.execute(
                text(
                    "SELECT id, secret_ciphertext, secret_key_id, enrolled_at, "
                    "last_used_step FROM iam.mfa_factors "
                    "WHERE user_id = :u AND enrolled_at IS NULL AND revoked_at IS NULL FOR UPDATE"
                ),
                {"u": user_id},
            )
        )
        .mappings()
        .first()
    )
    return _factor(row)


async def revoke_pending_factors(conn: AsyncConnection, user_id: UUID, at: datetime) -> None:
    await conn.execute(
        text(
            "UPDATE iam.mfa_factors SET revoked_at = :at "
            "WHERE user_id = :u AND enrolled_at IS NULL AND revoked_at IS NULL"
        ),
        {"u": user_id, "at": at},
    )


async def insert_factor(
    conn: AsyncConnection, *, factor_id: UUID, user_id: UUID, ciphertext: bytes, key_id: str
) -> None:
    await conn.execute(
        text(
            "INSERT INTO iam.mfa_factors (id, user_id, kind, secret_ciphertext, secret_key_id) "
            "VALUES (:id, :u, 'totp', :c, :k)"
        ),
        {"id": factor_id, "u": user_id, "c": ciphertext, "k": key_id},
    )


async def confirm_factor(conn: AsyncConnection, factor_id: UUID, *, at: datetime, step: int) -> None:
    await conn.execute(
        text("UPDATE iam.mfa_factors SET enrolled_at = :at, last_used_step = :step WHERE id = :id"),
        {"id": factor_id, "at": at, "step": step},
    )


async def record_factor_step(conn: AsyncConnection, factor_id: UUID, step: int) -> None:
    await conn.execute(
        text("UPDATE iam.mfa_factors SET last_used_step = :step WHERE id = :id"),
        {"id": factor_id, "step": step},
    )


# --------------------------------------------------------------------------- recovery codes
async def insert_recovery_codes(conn: AsyncConnection, rows: list[tuple[UUID, UUID, bytes]]) -> None:
    await conn.execute(
        text("INSERT INTO iam.mfa_recovery_codes (id, user_id, code_hash) VALUES (:id, :u, :h)"),
        [{"id": code_id, "u": user_id, "h": code_hash} for code_id, user_id, code_hash in rows],
    )


async def use_recovery_code(conn: AsyncConnection, user_id: UUID, code_hash: bytes, at: datetime) -> bool:
    """Mark an unused code as used; False if there is no such unused code."""
    used = (
        await conn.execute(
            text(
                "UPDATE iam.mfa_recovery_codes SET used_at = :at "
                "WHERE user_id = :u AND code_hash = :h AND used_at IS NULL AND "
                "revoked_at IS NULL RETURNING id"
            ),
            {"u": user_id, "h": code_hash, "at": at},
        )
    ).scalar_one_or_none()
    return used is not None


async def remaining_recovery_codes(conn: AsyncConnection, user_id: UUID) -> int:
    return int(
        (
            await conn.execute(
                text(
                    "SELECT count(*) FROM iam.mfa_recovery_codes "
                    "WHERE user_id = :u AND used_at IS NULL AND revoked_at IS NULL"
                ),
                {"u": user_id},
            )
        ).scalar_one()
    )


# --------------------------------------------------------------------------------- sessions
@dataclass(frozen=True)
class SessionRow:
    id: UUID
    user_id: UUID
    principal_type: str
    current_refresh_jti: str
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


async def insert_session(
    conn: AsyncConnection,
    *,
    session_id: UUID,
    user_id: UUID,
    refresh_jti: str,
    at: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO iam.sessions (id, user_id, principal_type, current_refresh_jti, mfa_verified_at, "
            "last_refreshed_at, idle_expires_at, absolute_expires_at) "
            "VALUES (:id, :u, 'user', :jti, :at, :at, :idle, :absolute)"
        ),
        {
            "id": session_id,
            "u": user_id,
            "jti": refresh_jti,
            "at": at,
            "idle": idle_expires_at,
            "absolute": absolute_expires_at,
        },
    )


async def lock_session(conn: AsyncConnection, session_id: UUID) -> SessionRow | None:
    row = (
        (
            await conn.execute(
                text(
                    "SELECT id, user_id, principal_type, current_refresh_jti, "
                    "idle_expires_at, absolute_expires_at, "
                    "revoked_at FROM iam.sessions WHERE id = :id FOR UPDATE"
                ),
                {"id": session_id},
            )
        )
        .mappings()
        .first()
    )
    return SessionRow(**row) if row else None


async def rotate_session(
    conn: AsyncConnection, session_id: UUID, *, refresh_jti: str, at: datetime, idle_expires_at: datetime
) -> None:
    await conn.execute(
        text(
            "UPDATE iam.sessions SET current_refresh_jti = :jti, last_refreshed_at = :at, "
            "idle_expires_at = :idle WHERE id = :id"
        ),
        {"id": session_id, "jti": refresh_jti, "at": at, "idle": idle_expires_at},
    )


async def revoke_session(conn: AsyncConnection, session_id: UUID, *, at: datetime, reason: str) -> None:
    await conn.execute(
        text(
            "UPDATE iam.sessions SET revoked_at = :at, revoke_reason = :reason "
            "WHERE id = :id AND revoked_at IS NULL"
        ),
        {"id": session_id, "at": at, "reason": reason},
    )


async def revoke_user_sessions(conn: AsyncConnection, user_id: UUID, *, at: datetime, reason: str) -> int:
    result = await conn.execute(
        text(
            "UPDATE iam.sessions SET revoked_at = :at, revoke_reason = :reason "
            "WHERE user_id = :u AND principal_type = 'user' AND revoked_at IS NULL"
        ),
        {"u": user_id, "at": at, "reason": reason},
    )
    return result.rowcount or 0


@dataclass(frozen=True)
class SessionPrincipal:
    """What pipeline step 6 needs about a user session, in one primary-key read (LD-28)."""

    user_id: UUID
    principal_type: str
    revoked_at: datetime | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
    user_status: str | None


async def session_principal(conn: AsyncConnection, session_id: UUID) -> SessionPrincipal | None:
    row = (
        (
            await conn.execute(
                text(
                    "SELECT s.user_id, s.principal_type, s.revoked_at, "
                    "s.idle_expires_at, s.absolute_expires_at, "
                    "u.status AS user_status "
                    "FROM iam.sessions s LEFT JOIN iam.users u ON u.id = s.user_id WHERE s.id = :id"
                ),
                {"id": session_id},
            )
        )
        .mappings()
        .first()
    )
    return SessionPrincipal(**row) if row else None


# ------------------------------------------------------------------------------ API clients
@dataclass(frozen=True)
class ApiClientRow:
    id: UUID
    secret_hash: bytes
    status: str
    rate_limit_per_minute: int


async def insert_api_client(
    conn: AsyncConnection,
    *,
    client_id: UUID,
    name: str,
    secret_hash: bytes,
    rate_limit_per_minute: int,
    actor: UUID | None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO iam.api_clients (id, name, secret_hash, "
            "rate_limit_per_minute, created_by, updated_by) "
            "VALUES (:id, :name, :hash, :limit, :actor, :actor)"
        ),
        {"id": client_id, "name": name, "hash": secret_hash, "limit": rate_limit_per_minute, "actor": actor},
    )


async def get_api_client(conn: AsyncConnection, client_id: UUID) -> ApiClientRow | None:
    row = (
        (
            await conn.execute(
                text(
                    "SELECT id, secret_hash, status, rate_limit_per_minute "
                    "FROM iam.api_clients WHERE id = :id"
                ),
                {"id": client_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ApiClientRow(
        id=row["id"],
        secret_hash=bytes(row["secret_hash"]),
        status=row["status"],
        rate_limit_per_minute=row["rate_limit_per_minute"],
    )


_READ_USER = text("SELECT " + _USER_COLUMNS + " FROM iam.users WHERE id = :id")  # noqa: S608 - fixed columns


async def read_user(conn: AsyncConnection, user_id: UUID) -> UserRow | None:
    """Plain read, no lock: used where a slow step (Argon2) runs between two transactions."""
    row = (await conn.execute(_READ_USER, {"id": user_id})).mappings().first()
    if row is None:
        return None
    data = dict(row)
    if data["activation_code_hash"] is not None:
        data["activation_code_hash"] = bytes(data["activation_code_hash"])
    return UserRow(**data)


# ------------------------------------------------------------------------ user management
@dataclass(frozen=True)
class UserProfile:
    """A user as administrators see it: no credential material."""

    id: UUID
    login_identifier: str
    display_name: str
    email: str | None
    department_id: UUID | None
    home_site_id: UUID | None
    status: str
    mfa_enrolled_at: datetime | None
    locked_until: datetime | None
    activation_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    #: Latest sign-in or token refresh; not read when the row is locked for a change.
    last_active_at: datetime | None = None


#: Sessions refresh every few minutes while someone works, so the latest refresh is their last
#: activity (F22 "Last active").
_LAST_ACTIVE = (
    ", (SELECT max(s.last_refreshed_at) FROM iam.sessions s WHERE s.user_id = iam.users.id) AS last_active_at"
)
_PROFILE_COLUMNS = (
    "id, login_identifier, display_name, email, department_id, home_site_id, status, mfa_enrolled_at, "
    "locked_until, "
    "activation_expires_at, created_at, updated_at, version"
)
_READ_PROFILE = text("SELECT " + _PROFILE_COLUMNS + _LAST_ACTIVE + " FROM iam.users WHERE id = :id")  # noqa: S608
_LOCK_PROFILE = text("SELECT " + _PROFILE_COLUMNS + " FROM iam.users WHERE id = :id FOR UPDATE")  # noqa: S608
_READ_PROFILES = text(
    "SELECT " + _PROFILE_COLUMNS + _LAST_ACTIVE + " FROM iam.users WHERE id = ANY(:ids)"  # noqa: S608
)
#: Keyset pagination in creation order (UUIDv7 ids sort by creation time).
_LIST_PROFILES = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _PROFILE_COLUMNS
    + _LAST_ACTIVE
    + " FROM iam.users"
    " WHERE (CAST(:status AS text) IS NULL OR status = :status)"
    " AND (CAST(:after AS uuid) IS NULL OR id > :after)"
    " AND (CAST(:q AS text) IS NULL OR display_name ILIKE :q OR login_identifier ILIKE :q"
    " OR email ILIKE :q)"
    " ORDER BY id LIMIT :limit"
)


async def read_profile(conn: AsyncConnection, user_id: UUID, *, lock: bool = False) -> UserProfile | None:
    row = (await conn.execute(_LOCK_PROFILE if lock else _READ_PROFILE, {"id": user_id})).mappings().first()
    return UserProfile(**row) if row else None


async def read_profiles(conn: AsyncConnection, user_ids: list[UUID]) -> dict[UUID, UserProfile]:
    if not user_ids:
        return {}
    rows = (await conn.execute(_READ_PROFILES, {"ids": user_ids})).mappings().all()
    return {row["id"]: UserProfile(**row) for row in rows}


def _like(term: str | None) -> str | None:
    if term is None or not term.strip():
        return None
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def list_profiles(
    conn: AsyncConnection, *, status: str | None, query: str | None, after: UUID | None, limit: int
) -> list[UserProfile]:
    rows = (
        await conn.execute(
            _LIST_PROFILES, {"status": status, "q": _like(query), "after": after, "limit": limit}
        )
    ).mappings()
    return [UserProfile(**row) for row in rows]


async def update_profile(
    conn: AsyncConnection,
    user_id: UUID,
    *,
    display_name: str,
    email: str | None,
    department_id: UUID | None,
    home_site_id: UUID | None,
    actor: UUID | None,
) -> int:
    return int(
        (
            await conn.execute(
                text(
                    "UPDATE iam.users SET display_name = :name, email = :email, "
                    "department_id = :department, home_site_id = :home_site, updated_at = now(), "
                    "updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
                ),
                {
                    "id": user_id,
                    "name": display_name,
                    "email": email,
                    "department": department_id,
                    "home_site": home_site_id,
                    "actor": actor,
                },
            )
        ).scalar_one()
    )


# ------------------------------------------------------------------- API client management
@dataclass(frozen=True)
class ApiClientProfile:
    id: UUID
    name: str
    rate_limit_per_minute: int
    status: str
    created_at: datetime
    updated_at: datetime
    version: int


_CLIENT_COLUMNS = "id, name, rate_limit_per_minute, status, created_at, updated_at, version"


async def read_api_client_profile(
    conn: AsyncConnection, client_id: UUID, *, lock: bool = False
) -> ApiClientProfile | None:
    statement = text(
        "SELECT "  # noqa: S608 - fixed columns
        + _CLIENT_COLUMNS
        + " FROM iam.api_clients WHERE id = :id"
        + (" FOR UPDATE" if lock else "")
    )
    row = (await conn.execute(statement, {"id": client_id})).mappings().first()
    return ApiClientProfile(**row) if row else None


async def list_api_client_profiles(conn: AsyncConnection) -> list[ApiClientProfile]:
    rows = (
        await conn.execute(text("SELECT " + _CLIENT_COLUMNS + " FROM iam.api_clients ORDER BY id"))  # noqa: S608
    ).mappings()
    return [ApiClientProfile(**row) for row in rows]


async def update_api_client(
    conn: AsyncConnection, client_id: UUID, *, actor: UUID | None, **fields: object
) -> int:
    allowed = {"status", "secret_hash", "name", "rate_limit_per_minute"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not an updatable API client column: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = :{name}" for name in fields)
    statement = text(
        "UPDATE iam.api_clients SET "  # noqa: S608 - allow-listed columns
        + assignments
        + ", updated_at = now(), updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
    )
    return int((await conn.execute(statement, {**fields, "actor": actor, "id": client_id})).scalar_one())
