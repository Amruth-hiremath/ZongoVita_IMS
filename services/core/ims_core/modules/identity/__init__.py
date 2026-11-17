"""Identity and Session module (LLD 5.1, 6.2, 6.3): users, MFA, sessions, API clients."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

if TYPE_CHECKING:
    from ims_core.kernel.runtime import CoreRuntime
    from ims_core.modules.identity.credentials import PasswordHasher


class IdentityModule:
    """Mounts the credential endpoints and attaches the identity service to the app."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher

    @property
    def routers(self) -> Sequence[APIRouter]:
        from ims_core.modules.identity import api_public, api_ui  # noqa: PLC0415

        return (api_ui.router, api_public.router)

    def attach(self, app: FastAPI, runtime: CoreRuntime) -> None:
        from ims_core.modules.identity.credentials import PasswordHasher  # noqa: PLC0415
        from ims_core.modules.identity.service import IdentityService  # noqa: PLC0415

        settings = runtime.settings
        hasher = self._hasher or PasswordHasher(
            time_cost=settings.password_time_cost,
            memory_kib=settings.password_memory_kib,
            parallelism=settings.password_parallelism,
        )
        app.state.identity = IdentityService(runtime, hasher)
