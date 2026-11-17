"""Object-storage port (AD-19; snapshot bundles LD-78).

Which object storage ZongoVita cloud offers is an open item (#31), so services depend on this
port. ``FileObjectStore`` is the adapter for local development and tests.
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Protocol

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)*$")


class ObjectNotFoundError(LookupError):
    def __init__(self, key: str) -> None:
        super().__init__(f"object not found: {key}")
        self.key = key


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes:
        """Return the object's bytes or raise ObjectNotFoundError."""
        ...


def validate_key(key: str) -> str:
    if not _KEY_RE.fullmatch(key) or ".." in key:
        raise ValueError(f"invalid object key: {key!r}")
    return key


class FileObjectStore:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        return self._root.joinpath(*validate_key(key).split("/"))

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # atomic: readers see the old or the new object, never a partial one

        await asyncio.to_thread(_write)

    async def get(self, key: str) -> bytes:
        path = self._path(key)

        def _read() -> bytes:
            try:
                return path.read_bytes()
            except FileNotFoundError:
                raise ObjectNotFoundError(key) from None

        return await asyncio.to_thread(_read)
