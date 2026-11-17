"""Provisioning DDL: databases and roles (LLD 6.6 steps 2 and 3; AD-16, AD-18, AD-62).

Every step is safe to retry: an interrupted run resumes without touching other customers.
A new customer is a new database plus its own roles; nothing existing is altered.

Roles per customer database (LLD section 3):
  ims_app_<code>         application role: DML only, per-customer timeouts as role defaults
  ims_mig_<code>         owner of the database; used only by this pipeline
  ims_breakglass_<code>  may only execute the break-glass function (granted by its migration)
"""

from __future__ import annotations

import re
import secrets as token_source
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ims_common.ddl import quote_ident
from ims_common.secrets import SecretNotFoundError, SecretsStore, db_secret_ref
from ims_db_pipeline.cluster import ClusterAdmin

CUSTOMER_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")

CONTROL_PLANE_DATABASE = "ims_control_plane"
PLATFORM_APP_ROLE = "platform_app"
PLATFORM_MIGRATOR_ROLE = "platform_migrator"
PLATFORM_APP_SECRET_REF = "platform/db-app"  # noqa: S105 - a reference, not a secret
PLATFORM_MIGRATION_SECRET_REF = "platform/db-migration"  # noqa: S105

#: LD-08 / AD-84: per-customer limits applied as role defaults, so they hold through the pooler.
#: An empty search_path forces schema-qualified SQL and removes any object-shadowing risk.
APP_ROLE_DEFAULTS: dict[str, str] = {
    "statement_timeout": "15s",
    "lock_timeout": "5s",
    "idle_in_transaction_session_timeout": "30s",
    "search_path": "",
}

_ROLE_ATTRIBUTES = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
_PASSWORD_RE = re.compile(r"^[A-Za-z0-9_-]{32,}$")


@dataclass(frozen=True)
class CustomerDatabase:
    """Names and secret references of one customer's database."""

    customer_code: str
    database_name: str
    app_role: str
    migration_role: str
    breakglass_role: str
    app_secret_ref: str
    migration_secret_ref: str
    breakglass_secret_ref: str

    @classmethod
    def for_customer(cls, customer_code: str) -> CustomerDatabase:
        if not CUSTOMER_CODE_RE.fullmatch(customer_code):
            raise ValueError(f"invalid customer code: {customer_code!r}")
        return cls(
            customer_code=customer_code,
            database_name=f"ims_c_{customer_code}",
            app_role=f"ims_app_{customer_code}",
            migration_role=f"ims_mig_{customer_code}",
            breakglass_role=f"ims_breakglass_{customer_code}",
            app_secret_ref=db_secret_ref(customer_code, "app"),
            migration_secret_ref=db_secret_ref(customer_code, "migration"),
            breakglass_secret_ref=db_secret_ref(customer_code, "breakglass"),
        )


async def _ensure_role(conn: AsyncConnection, secrets: SecretsStore, role: str, secret_ref: str) -> None:
    """Create the role with a generated password stored in the secrets store.

    Retry-safe: an existing role whose secret is present is left alone; an existing role whose
    secret was never stored (a run interrupted between the two steps) gets a fresh password.
    """
    exists = (
        await conn.execute(text("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :r"), {"r": role})
    ).scalar_one_or_none() is not None
    try:
        await secrets.get(secret_ref)
        has_secret = True
    except SecretNotFoundError:
        has_secret = False
    if exists and has_secret:
        return
    password = token_source.token_urlsafe(36)
    if not _PASSWORD_RE.fullmatch(password):  # pragma: no cover - guards the literal below
        raise RuntimeError("generated password has unexpected characters")
    verb = "ALTER" if exists else "CREATE"
    # Utility statements take no bind parameters; the password alphabet is checked above.
    await conn.execute(text(f"{verb} ROLE {quote_ident(role)} WITH {_ROLE_ATTRIBUTES} PASSWORD '{password}'"))
    await secrets.put(secret_ref, {"username": role, "password": password})


async def _set_role_defaults(conn: AsyncConnection, role: str, defaults: dict[str, str]) -> None:
    for setting, value in defaults.items():
        if not re.fullmatch(r"[a-z_]+", setting) or not re.fullmatch(r"[A-Za-z0-9_ ]*", value):
            raise ValueError(f"unsafe role default: {setting}={value!r}")
        await conn.execute(text(f"ALTER ROLE {quote_ident(role)} SET {setting} = '{value}'"))


async def _ensure_owner_membership(conn: AsyncConnection, owner_role: str) -> None:
    """A non-superuser admin must be able to act as the owner role to create its database."""
    is_superuser = (
        await conn.execute(text("SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user"))
    ).scalar_one()
    if not is_superuser:
        await conn.execute(text(f"GRANT {quote_ident(owner_role)} TO CURRENT_USER"))


async def _ensure_database(
    conn: AsyncConnection, database: str, owner_role: str, connect_roles: list[str]
) -> bool:
    """Create the database if absent and restrict who may connect. Returns True if created."""
    exists = (
        await conn.execute(text("SELECT 1 FROM pg_catalog.pg_database WHERE datname = :d"), {"d": database})
    ).scalar_one_or_none() is not None
    if not exists:
        await conn.execute(
            text(
                f"CREATE DATABASE {quote_ident(database)} OWNER {quote_ident(owner_role)} "
                "TEMPLATE template0 ENCODING 'UTF8'"
            )
        )
    # Only this database's own roles may connect: another customer's credential is refused
    # before any table privilege is even considered.
    await conn.execute(text(f"REVOKE ALL ON DATABASE {quote_ident(database)} FROM PUBLIC"))
    for role in connect_roles:
        await conn.execute(text(f"GRANT CONNECT ON DATABASE {quote_ident(database)} TO {quote_ident(role)}"))
    return not exists


async def provision_customer_database(
    cluster: ClusterAdmin, secrets: SecretsStore, customer_code: str
) -> CustomerDatabase:
    """Create one customer's database and its three roles. Idempotent."""
    target = CustomerDatabase.for_customer(customer_code)
    engine = cluster.admin_engine()
    try:
        async with engine.connect() as raw:
            conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
            await _ensure_role(conn, secrets, target.app_role, target.app_secret_ref)
            await _ensure_role(conn, secrets, target.migration_role, target.migration_secret_ref)
            await _ensure_role(conn, secrets, target.breakglass_role, target.breakglass_secret_ref)
            await _set_role_defaults(conn, target.app_role, APP_ROLE_DEFAULTS)
            await _set_role_defaults(conn, target.breakglass_role, APP_ROLE_DEFAULTS)
            await _ensure_owner_membership(conn, target.migration_role)
            await _ensure_database(
                conn, target.database_name, target.migration_role, [target.app_role, target.breakglass_role]
            )
    finally:
        await engine.dispose()
    return target


async def provision_control_plane(cluster: ClusterAdmin, secrets: SecretsStore) -> None:
    """Create the Control-Plane database with its application and migration roles. Idempotent."""
    engine = cluster.admin_engine()
    try:
        async with engine.connect() as raw:
            conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
            await _ensure_role(conn, secrets, PLATFORM_APP_ROLE, PLATFORM_APP_SECRET_REF)
            await _ensure_role(conn, secrets, PLATFORM_MIGRATOR_ROLE, PLATFORM_MIGRATION_SECRET_REF)
            await _set_role_defaults(conn, PLATFORM_APP_ROLE, APP_ROLE_DEFAULTS)
            await _ensure_owner_membership(conn, PLATFORM_MIGRATOR_ROLE)
            await _ensure_database(conn, CONTROL_PLANE_DATABASE, PLATFORM_MIGRATOR_ROLE, [PLATFORM_APP_ROLE])
    finally:
        await engine.dispose()
