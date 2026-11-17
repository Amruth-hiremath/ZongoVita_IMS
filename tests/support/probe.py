"""A small set of tenant routes used to exercise the kernel through real HTTP requests.

They are declared exactly like module routes (ImsRouter + @declare) and use only kernel
services, so what the tests observe is the pipeline's behaviour, not a test shortcut.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import text

from ims_common.problem import DomainError
from ims_contracts.enums import LicenceModule
from ims_contracts.errors import ErrorCode
from ims_core.kernel.authn import AUDIENCE_API, AUDIENCE_UI, AccessClaims
from ims_core.kernel.routes import (
    Access,
    Authenticated,
    Ctx,
    ImsRouter,
    NoPermission,
    Permission,
    Uow,
    declare,
)
from ims_core.kernel.stages import PipelineStages
from ims_core.kernel.tenant_settings import SettingDefinition, SettingsRegistry
from ims_core.kernel.uow import UnitOfWork

PERMISSION_SETTINGS = "config.settings.manage"

REGISTRY = SettingsRegistry()
LOCK_TIMEOUT_HOURS = REGISTRY.register(
    SettingDefinition("probe.lock_timeout_hours", int, 72, "Reservation lock timeout in hours")
)
SECOND = REGISTRY.register(SettingDefinition("probe.second", int, 1, "A second setting"))
DEFINITIONS = {d.key: d for d in REGISTRY.all()}


class SetSetting(BaseModel):
    value: Any
    expected_version: int
    reason: str | None = None
    gmp_relevant: bool = False
    #: Raise after every write has been made, to prove the unit of work rolls back as a whole.
    fail_after_writes: bool = False


class LockPair(BaseModel):
    first: str
    second: str


@dataclass
class ProbeState:
    """Per-test knobs and observations."""

    granted: set[str] = field(default_factory=lambda: {PERMISSION_SETTINGS})
    inactive_principals: set[Any] = field(default_factory=set)
    handler_calls: int = 0
    lock_pair_attempts: int = 0
    #: Lets two lock-pair requests each take their first lock before either takes its second.
    barrier: asyncio.Barrier | None = None


class _Principal:
    def __init__(self, state: ProbeState) -> None:
        self._state = state

    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        if claims.subject in self._state.inactive_principals:
            raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)


class _RateLimit:
    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        pass


class _Authorise:
    def __init__(self, state: ProbeState) -> None:
        self._state = state

    async def authorise(self, uow: UnitOfWork, access: Access) -> None:
        if isinstance(access, Permission) and access.code not in self._state.granted:
            raise DomainError(ErrorCode.PERMISSION_DENIED)


def stages(state: ProbeState) -> PipelineStages:
    return PipelineStages(principal=_Principal(state), rate_limit=_RateLimit(), authorise=_Authorise(state))


def build_routers() -> list[ImsRouter]:
    ui = ImsRouter(prefix="/ui/v1", audience=AUDIENCE_UI, module=LicenceModule.CORE)
    api = ImsRouter(prefix="/api/v1", audience=AUDIENCE_API, module=LicenceModule.INTEGRATION)

    @ui.get("/probe/whoami")
    @declare(access=Authenticated(), read_only_ok=True)
    async def whoami(ctx: Ctx, uow: Uow) -> dict[str, Any]:
        row = (await uow.db.execute(text("SELECT current_database() AS db, current_user AS usr"))).one()
        return {
            "customer_id": str(ctx.customer_id),
            "customer_code": ctx.customer_code,
            "database": row.db,
            "db_user": row.usr,
            "licence_state": ctx.licence_state.value,
            "request_id": ctx.request_id,
            "principal_type": ctx.principal.type.value if ctx.principal else None,
        }

    @ui.get("/probe/settings/{key}")
    @declare(access=Authenticated(), read_only_ok=True)
    async def get_setting(key: str, request: Request, uow: Uow) -> dict[str, Any]:
        described = await request.app.state.tenant_settings.describe(uow, DEFINITIONS[key])
        return {"key": key, "value": described.value, "version": described.version}

    @ui.put("/probe/settings/{key}")
    @declare(access=Permission(PERMISSION_SETTINGS), read_only_ok=False)
    async def put_setting(key: str, body: SetSetting, request: Request, uow: Uow) -> dict[str, Any]:
        state: ProbeState = request.app.state.probe
        state.handler_calls += 1
        result = await request.app.state.tenant_settings.set(
            uow, DEFINITIONS[key], body.value, expected_version=body.expected_version, reason=body.reason
        )
        if body.gmp_relevant:
            await uow.audit.record(
                action="probe.gmp_change",
                entity_type="probe.setting",
                entity_id=key,
                reason=body.reason,
                gmp_relevant=True,
            )
        await uow.events.publish(
            event_type="probe.setting.changed",
            subject_type="probe.setting",
            subject_id=key,
            subject_version=result.version,
            data={"key": key, "value": result.value},
        )
        if body.fail_after_writes:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "probe failure after writes")
        return {"key": key, "value": result.value, "version": result.version}

    @ui.post("/probe/lock-pair")
    @declare(access=Permission(PERMISSION_SETTINGS), read_only_ok=False)
    async def lock_pair(body: LockPair, request: Request, uow: Uow) -> dict[str, Any]:
        """Lock two settings rows in the given order. Two opposite calls deadlock on purpose."""
        state: ProbeState = request.app.state.probe
        state.lock_pair_attempts += 1
        lock = text("SELECT 1 FROM config.settings WHERE key = :key FOR UPDATE")
        await uow.db.execute(lock, {"key": body.first})
        barrier = state.barrier
        if barrier is not None:
            # First attempt only: both requests hold their first lock before either goes on.
            with contextlib.suppress(TimeoutError, asyncio.BrokenBarrierError):
                await asyncio.wait_for(barrier.wait(), timeout=5)
            state.barrier = None
        await uow.db.execute(lock, {"key": body.second})
        return {"locked": [body.first, body.second]}

    @ui.post("/probe/emergency")
    @declare(access=Permission(PERMISSION_SETTINGS), read_only_ok=True)
    async def emergency(uow: Uow) -> dict[str, Any]:
        await uow.audit.record(action="probe.emergency", entity_type="probe", entity_id="1", reason="test")
        return {"recorded": True}

    @ui.post("/probe/replenishment")
    @declare(access=Authenticated(), read_only_ok=False, module=LicenceModule.REPLENISHMENT)
    async def replenishment() -> dict[str, Any]:
        return {"ok": True}

    @ui.get("/probe/write-in-read")
    @declare(access=Authenticated(), read_only_ok=True)
    async def write_in_read(uow: Uow) -> dict[str, Any]:
        await uow.audit.record(action="probe.sneaky", entity_type="probe", entity_id="1")
        return {"written": True}

    @ui.post("/probe/credential")
    @declare(access=NoPermission(), read_only_ok=True)
    async def credential(request: Request) -> dict[str, Any]:
        return {"has_uow": getattr(request.state, "uow", None) is not None}

    @api.get("/probe/whoami")
    @declare(access=Authenticated(), read_only_ok=True)
    async def api_whoami(ctx: Ctx) -> dict[str, Any]:
        return {"customer_code": ctx.customer_code, "principal_type": ctx.principal.type.value}

    return [ui, api]
