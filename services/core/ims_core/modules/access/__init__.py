"""Access Control module (LLD 5.1, section 7; AD-45, AD-46): permission catalogue, roles, user
types, site-scoped role assignments, the super admin, the authorise and rate-limit stages, and
GET /ui/v1/me."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

if TYPE_CHECKING:
    from ims_core.kernel.runtime import CoreRuntime
    from ims_core.kernel.stages import PipelineStages, PrincipalStage
    from ims_core.modules.access.public import Authoriser, RateLimiter, RateLimits


class AccessModule:
    """Mounts the access routes and supplies pipeline steps 7 and 8. Attach after the identity
    module, whose service it uses to create and change principals."""

    def __init__(self, *, limits: RateLimits | None = None) -> None:
        from ims_core.modules.access.public import Authoriser, RateLimiter  # noqa: PLC0415

        self.authoriser: Authoriser = Authoriser()
        self.rate_limiter: RateLimiter = RateLimiter(limits)

    @property
    def routers(self) -> Sequence[APIRouter]:
        from ims_core.modules.access import api_ui  # noqa: PLC0415

        return (api_ui.router,)

    def stages(self, principal: PrincipalStage) -> PipelineStages:
        from ims_core.kernel.stages import PipelineStages  # noqa: PLC0415

        return PipelineStages(principal=principal, rate_limit=self.rate_limiter, authorise=self.authoriser)

    def attach(self, app: FastAPI, runtime: CoreRuntime) -> None:
        from ims_core.modules.access.service import AccessService  # noqa: PLC0415

        identity = getattr(app.state, "identity", None)
        if identity is None:
            raise RuntimeError("attach the identity module before the access module")
        app.state.access = AccessService(identity, runtime.clock)
