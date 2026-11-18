"""Organisation module (LLD 5.1, 12): sites, locations, departments and the licence site limit."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

if TYPE_CHECKING:
    from ims_core.kernel.runtime import CoreRuntime


class OrganisationModule:
    @property
    def routers(self) -> Sequence[APIRouter]:
        from ims_core.modules.organisation import api_public, api_ui  # noqa: PLC0415

        return (api_ui.router, api_public.router)

    def attach(self, app: FastAPI, runtime: CoreRuntime) -> None:
        from ims_core.modules.organisation.service import OrganisationService  # noqa: PLC0415

        del runtime
        app.state.organisation = OrganisationService()
