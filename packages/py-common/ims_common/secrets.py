"""Secrets-store port (AD-63: secrets live only in the secrets store; repositories and the
Registry hold references).

The production adapter depends on the secrets manager ZongoVita cloud provides, which is not yet
known (HLD section 4, "Required ZongoVita cloud capabilities"). ``FileSecretsStore`` is the
adapter for local development and tests. Both honour the same rule the design relies on: an
identity can only read the references it is entitled to. For the file adapter that entitlement
is the ``readable`` / ``writable`` pattern list given at construction, so a service that should
never see a class of secret (for example Core and migration credentials, AD-13/AD-62) fails
loudly if any code path tries.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Protocol

_REF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*$")


class SecretNotFoundError(LookupError):
    def __init__(self, ref: str) -> None:
        super().__init__(f"secret not found: {ref}")
        self.ref = ref


class SecretAccessDeniedError(PermissionError):
    def __init__(self, ref: str, action: str) -> None:
        super().__init__(f"this identity may not {action} secret: {ref}")
        self.ref = ref


class SecretsStore(Protocol):
    async def get(self, ref: str) -> dict[str, Any]:
        """Return the secret value, or raise SecretNotFoundError / SecretAccessDeniedError."""
        ...

    async def put(self, ref: str, value: dict[str, Any]) -> None:
        """Create or replace a secret."""
        ...


def validate_ref(ref: str) -> str:
    if not _REF_RE.fullmatch(ref):
        raise ValueError(f"invalid secret reference: {ref!r}")
    return ref


def db_secret_ref(customer_code: str, role_kind: str) -> str:
    """Reference of a customer-database credential; role_kind is app, migration or breakglass."""
    if role_kind not in {"app", "migration", "breakglass"}:
        raise ValueError(f"unknown role kind: {role_kind}")
    return validate_ref(f"customers/{customer_code.replace('_', '-')}/db-{role_kind}")


class FileSecretsStore:
    """Directory of JSON files, one per reference. Local development and tests only."""

    def __init__(
        self,
        root: Path | str,
        *,
        readable: tuple[str, ...] = ("*",),
        writable: tuple[str, ...] = (),
    ) -> None:
        self._root = Path(root)
        self._readable = readable
        self._writable = writable

    def _path(self, ref: str) -> Path:
        return self._root.joinpath(*validate_ref(ref).split("/")).with_suffix(".json")

    @staticmethod
    def _allowed(ref: str, patterns: tuple[str, ...]) -> bool:
        return any(fnmatchcase(ref, pattern) for pattern in patterns)

    async def get(self, ref: str) -> dict[str, Any]:
        path = self._path(ref)
        if not self._allowed(ref, self._readable):
            raise SecretAccessDeniedError(ref, "read")

        def _read() -> dict[str, Any]:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                raise SecretNotFoundError(ref) from None

        return await asyncio.to_thread(_read)

    async def put(self, ref: str, value: dict[str, Any]) -> None:
        path = self._path(ref)
        if not self._allowed(ref, self._writable):
            raise SecretAccessDeniedError(ref, "write")

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(value), encoding="utf-8")
            with contextlib.suppress(OSError):
                tmp.chmod(0o600)
            tmp.replace(path)

        await asyncio.to_thread(_write)
