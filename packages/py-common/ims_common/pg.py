"""PostgreSQL engine construction shared by every service (LD-75, AD-80).

All application access goes through a transaction-mode pooler. That rules out anything tied to
a server session, so the rules are fixed here once instead of per service:

* the driver never prepares statements (``prepare_threshold=None``); nothing survives on a
  server connection between transactions;
* no session-level SET: settings are role defaults or ``SET LOCAL`` inside the transaction;
* advisory locks are transaction-scoped only; LISTEN/NOTIFY is not used;
* ``application_name`` travels as a startup parameter.

Migrations, provisioning DDL and monitoring connect directly (``create_direct_engine``).
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

# SQLSTATE codes the application reacts to.
SQLSTATE_UNIQUE_VIOLATION = "23505"
SQLSTATE_CHECK_VIOLATION = "23514"
SQLSTATE_SERIALIZATION_FAILURE = "40001"
SQLSTATE_DEADLOCK_DETECTED = "40P01"
SQLSTATE_LOCK_NOT_AVAILABLE = "55P03"
SQLSTATE_QUERY_CANCELED = "57014"
SQLSTATE_INSUFFICIENT_PRIVILEGE = "42501"
SQLSTATE_INVALID_PASSWORD = "28P01"  # noqa: S105 - a PostgreSQL error code
SQLSTATE_INVALID_AUTHORIZATION = "28000"
SQLSTATE_READ_ONLY_TRANSACTION = "25006"

RETRYABLE_SQLSTATES = frozenset({SQLSTATE_SERIALIZATION_FAILURE, SQLSTATE_DEADLOCK_DETECTED})
AUTH_FAILURE_SQLSTATES = frozenset({SQLSTATE_INVALID_PASSWORD, SQLSTATE_INVALID_AUTHORIZATION})


def _url(host: str, port: int, database: str, user: str, password: str) -> URL:
    return URL.create(
        "postgresql+psycopg", username=user, password=password, host=host, port=port, database=database
    )


def _connect_args(application_name: str, sslmode: str, connect_timeout_s: int) -> dict[str, object]:
    return {
        "prepare_threshold": None,
        "application_name": application_name,
        "connect_timeout": connect_timeout_s,
        "sslmode": sslmode,
    }


def create_pooler_engine(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    application_name: str,
    pool_size: int,
    max_overflow: int,
    pool_timeout_s: float,
    sslmode: str,
    connect_timeout_s: int = 5,
) -> AsyncEngine:
    """Client-side pool towards the cluster pooler. Client connections are cheap; the server-side
    connection budget is enforced by the pooler, not here."""
    return create_async_engine(
        _url(host, port, database, user, password),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout_s,
        pool_recycle=600,
        connect_args=_connect_args(application_name, sslmode, connect_timeout_s),
    )


def create_direct_engine(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    application_name: str,
    sslmode: str,
    connect_timeout_s: int = 5,
) -> AsyncEngine:
    """Unpooled direct connection for the CI/CD pipeline and tests' administrative work."""
    return create_async_engine(
        _url(host, port, database, user, password),
        poolclass=NullPool,
        connect_args=_connect_args(application_name, sslmode, connect_timeout_s),
    )


def sqlstate_of(exc: BaseException) -> str | None:
    """SQLSTATE of a database error, looking through SQLAlchemy's wrapper."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        state = getattr(current, "sqlstate", None)
        if isinstance(state, str):
            return state
        nested = current.orig if isinstance(current, DBAPIError) else current.__cause__
        current = nested if isinstance(nested, BaseException) else None
    return None


def is_disconnect(exc: BaseException) -> bool:
    return isinstance(exc, DBAPIError) and bool(exc.connection_invalidated)


def use_selector_event_loop_on_windows() -> None:
    """The async PostgreSQL driver needs a selector event loop; Windows defaults to proactor.

    Production runs on Linux containers, where this is a no-op. It matters for local development
    and tests on Windows.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
