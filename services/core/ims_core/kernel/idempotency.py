"""Idempotency keys (AD-34; LLD section 12, LD-61).

The key, scoped to the principal and bound to a hash of method, path and body, is inserted as
the first write of the business transaction. Key, effect and stored response therefore commit
together, and a double scan or a client retry acts exactly once.

A concurrent duplicate waits on the unique index. If the first request commits, the duplicate
returns the stored response with ``Idempotent-Replay: true``. If the first rolls back, the
duplicate proceeds. A wait beyond ``lock_timeout`` is 409 REQUEST_IN_PROGRESS; the same key with
a different request is 422 IDEMPOTENCY_KEY_REUSED. Failed requests store nothing. Keys expire
after 72 hours.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from ims_common.pg import SQLSTATE_LOCK_NOT_AVAILABLE, sqlstate_of
from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode, FieldError

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAY_HEADER = "Idempotent-Replay"
RETENTION_HOURS = 72

_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

_CLAIM = text(
    """
    INSERT INTO integration.idempotency_keys AS k (principal_id, key, endpoint, request_hash, expires_at)
    VALUES (:principal_id, :key, :endpoint, :request_hash, now() + make_interval(hours => :retention_hours))
    ON CONFLICT (principal_id, key) DO UPDATE
       SET endpoint = EXCLUDED.endpoint,
           request_hash = EXCLUDED.request_hash,
           status_code = NULL,
           response_body = NULL,
           created_at = now(),
           expires_at = EXCLUDED.expires_at
     WHERE k.expires_at <= now()
    RETURNING 1
    """
)
_READ = text(
    "SELECT request_hash, status_code, response_body FROM integration.idempotency_keys "
    "WHERE principal_id = :principal_id AND key = :key"
)
_COMPLETE = text(
    "UPDATE integration.idempotency_keys SET status_code = :status_code, response_body = :response_body "
    "WHERE principal_id = :principal_id AND key = :key"
)


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: str


def validate_key(value: str | None) -> str:
    if value is None or not _KEY_RE.fullmatch(value):
        raise DomainError(
            ErrorCode.VALIDATION_FAILED,
            status=400,
            errors=[
                FieldError(
                    field=IDEMPOTENCY_HEADER,
                    message=(
                        "required on every POST, PUT, PATCH and DELETE: "
                        "8 to 128 characters of A-Z a-z 0-9 . _ : -"
                    ),
                )
            ],
        )
    return value


def request_hash(method: str, path_and_query: str, body: bytes) -> bytes:
    digest = hashlib.sha256()
    digest.update(method.upper().encode("ascii"))
    digest.update(b"\n")
    digest.update(path_and_query.encode("utf-8"))
    digest.update(b"\n")
    digest.update(body)
    return digest.digest()


async def claim(
    conn: AsyncConnection, *, principal_id: UUID, key: str, endpoint: str, digest: bytes
) -> StoredResponse | None:
    """Take the key for this transaction, or return the response stored by an earlier request.

    Returns None when this request owns the key and must run.
    """
    params = {"principal_id": principal_id, "key": key}
    try:
        owned = (
            await conn.execute(
                _CLAIM,
                {**params, "endpoint": endpoint, "request_hash": digest, "retention_hours": RETENTION_HOURS},
            )
        ).scalar_one_or_none()
    except DBAPIError as exc:
        if sqlstate_of(exc) == SQLSTATE_LOCK_NOT_AVAILABLE:
            raise DomainError(ErrorCode.REQUEST_IN_PROGRESS, headers={"Retry-After": "1"}) from None
        raise
    if owned is not None:
        return None
    existing = (await conn.execute(_READ, params)).first()
    if existing is None or existing.status_code is None:
        # The earlier request finished between our two statements and its key was removed, or
        # it is in a state we cannot interpret: the client retries.
        raise DomainError(ErrorCode.REQUEST_IN_PROGRESS, headers={"Retry-After": "1"})
    if bytes(existing.request_hash) != digest:
        raise DomainError(ErrorCode.IDEMPOTENCY_KEY_REUSED)
    return StoredResponse(status_code=existing.status_code, body=existing.response_body)


async def complete(
    conn: AsyncConnection, *, principal_id: UUID, key: str, status_code: int, body: str
) -> None:
    """Store the response next to the key, in the same transaction as the effect."""
    await conn.execute(
        _COMPLETE,
        {"principal_id": principal_id, "key": key, "status_code": status_code, "response_body": body},
    )
