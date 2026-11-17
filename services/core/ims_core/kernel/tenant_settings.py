"""Customer-configurable settings (LD-25: typed settings registry with defaults).

A setting is defined in code, with a type and a default, by the module that owns it. A customer
overrides it by storing a value in ``config.settings``; absence means the default. Every value
the LLD "assumes" for an open item is such a setting unless it is a code rule, so a later
ZongoVita decision changes a default or a customer's value, not the code path.

Reads go through a per-process cache (60 seconds, LLD section 16). Writes take a row lock,
check the caller's expected version (optimistic locking via If-Match), and are audited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import text

from ims_common.clock import Clock
from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode, FieldError
from ims_core.kernel import jsonutil
from ims_core.kernel.uow import UnitOfWork

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
CACHE_SECONDS = 60.0

#: Version reported for a setting that has no stored row (its default is in effect).
DEFAULT_VERSION = 0


@dataclass(frozen=True)
class SettingDefinition[T]:
    key: str
    type: Any
    default: T
    description: str

    def __post_init__(self) -> None:
        if not _KEY_RE.fullmatch(self.key):
            raise ValueError(f"invalid setting key: {self.key!r}")
        # The default must itself be valid, so a missing row can never yield a bad value.
        object.__setattr__(self, "_adapter", TypeAdapter(self.type))
        self.parse(self.default)

    def parse(self, raw: Any) -> T:
        return self._adapter.validate_python(raw)  # type: ignore[attr-defined]

    def dump(self, value: T) -> Any:
        return self._adapter.dump_python(value, mode="json")  # type: ignore[attr-defined]


class SettingsRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SettingDefinition[Any]] = {}

    def register[T](self, definition: SettingDefinition[T]) -> SettingDefinition[T]:
        if definition.key in self._definitions:
            raise ValueError(f"setting already defined: {definition.key}")
        self._definitions[definition.key] = definition
        return definition

    def get(self, key: str) -> SettingDefinition[Any]:
        try:
            return self._definitions[key]
        except KeyError:
            raise DomainError(ErrorCode.NOT_FOUND, f"unknown setting: {key}") from None

    def all(self) -> list[SettingDefinition[Any]]:
        return sorted(self._definitions.values(), key=lambda d: d.key)


@dataclass(frozen=True)
class SettingValue[T]:
    key: str
    value: T
    version: int
    is_default: bool


class TenantSettings:
    def __init__(
        self, registry: SettingsRegistry, clock: Clock, *, cache_seconds: float = CACHE_SECONDS
    ) -> None:
        self._registry = registry
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._cache: dict[UUID, tuple[float, dict[str, tuple[Any, int]]]] = {}

    async def _stored(self, uow: UnitOfWork) -> dict[str, tuple[Any, int]]:
        cached = self._cache.get(uow.ctx.customer_id)
        now = self._clock.monotonic()
        if cached and now - cached[0] < self._cache_seconds:
            return cached[1]
        rows = (await uow.db.execute(text("SELECT key, value, version FROM config.settings"))).all()
        stored = {row.key: (row.value, row.version) for row in rows}
        self._cache[uow.ctx.customer_id] = (now, stored)
        return stored

    def _evict(self, customer_id: UUID) -> None:
        self._cache.pop(customer_id, None)

    def _resolve[T](
        self, definition: SettingDefinition[T], stored: tuple[Any, int] | None
    ) -> SettingValue[T]:
        if stored is None:
            return SettingValue(definition.key, definition.default, DEFAULT_VERSION, True)
        try:
            return SettingValue(definition.key, definition.parse(stored[0]), stored[1], False)
        except ValidationError:
            # A stored value the current definition no longer accepts must not break requests.
            return SettingValue(definition.key, definition.default, stored[1], True)

    async def get[T](self, uow: UnitOfWork, definition: SettingDefinition[T]) -> T:
        return self._resolve(definition, (await self._stored(uow)).get(definition.key)).value

    async def describe[T](self, uow: UnitOfWork, definition: SettingDefinition[T]) -> SettingValue[T]:
        return self._resolve(definition, (await self._stored(uow)).get(definition.key))

    async def list_effective(self, uow: UnitOfWork) -> list[SettingValue[Any]]:
        stored = await self._stored(uow)
        return [self._resolve(definition, stored.get(definition.key)) for definition in self._registry.all()]

    async def set[T](
        self,
        uow: UnitOfWork,
        definition: SettingDefinition[T],
        raw_value: Any,
        *,
        expected_version: int,
        reason: str | None = None,
    ) -> SettingValue[T]:
        """Change a setting for this customer.

        ``expected_version`` is the version the caller last read (0 while the default applies).
        A mismatch is 412 VERSION_CONFLICT: someone else changed it first.
        """
        try:
            value = definition.parse(raw_value)
        except ValidationError as exc:
            raise DomainError(
                ErrorCode.VALIDATION_FAILED,
                errors=[FieldError(field=definition.key, message=str(err["msg"])) for err in exc.errors()],
            ) from None
        encoded = jsonutil.dumps(definition.dump(value))
        actor = uow.ctx.principal.id if uow.ctx.principal else None
        current = (
            await uow.db.execute(
                text("SELECT value, version FROM config.settings WHERE key = :key FOR UPDATE"),
                {"key": definition.key},
            )
        ).first()
        if current is None:
            if expected_version != DEFAULT_VERSION:
                raise DomainError(ErrorCode.VERSION_CONFLICT)
            inserted = (
                await uow.db.execute(
                    text(
                        "INSERT INTO config.settings (key, value, created_by, updated_by) "
                        "VALUES (:key, CAST(:value AS jsonb), :actor, :actor) "
                        "ON CONFLICT (key) DO NOTHING RETURNING version"
                    ),
                    {"key": definition.key, "value": encoded, "actor": actor},
                )
            ).scalar_one_or_none()
            if inserted is None:  # a concurrent first write won
                raise DomainError(ErrorCode.VERSION_CONFLICT)
            before: Any = None
            new_version = int(inserted)
        else:
            if current.version != expected_version:
                raise DomainError(ErrorCode.VERSION_CONFLICT)
            before = current.value
            new_version = int(
                (
                    await uow.db.execute(
                        text(
                            "UPDATE config.settings SET value = CAST(:value AS jsonb), "
                            "version = version + 1, updated_at = now(), updated_by = :actor "
                            "WHERE key = :key RETURNING version"
                        ),
                        {"key": definition.key, "value": encoded, "actor": actor},
                    )
                ).scalar_one()
            )
        await uow.audit.record(
            action="config.setting.changed",
            entity_type="config.setting",
            entity_id=definition.key,
            before={"value": before, "default": definition.dump(definition.default)},
            after={"value": definition.dump(value), "version": new_version},
            reason=reason,
        )
        customer_id = uow.ctx.customer_id

        async def _evict() -> None:
            self._evict(customer_id)

        uow.on_commit(_evict)
        return SettingValue(definition.key, value, new_version, False)
