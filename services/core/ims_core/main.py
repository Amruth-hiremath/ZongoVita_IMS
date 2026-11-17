"""IMS Core API application (UI API /ui/v1 and public API /api/v1 from one service, AD-06)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from fastapi import APIRouter, FastAPI, Response

from ims_common.logging import configure_logging
from ims_common.pg import use_selector_event_loop_on_windows
from ims_common.problem import install_problem_handlers
from ims_core.kernel.routes import ImsRoute, NoPermission
from ims_core.kernel.runtime import CoreRuntime, build_runtime
from ims_core.kernel.settings import CoreSettings
from ims_core.kernel.stages import PipelineStages


class CoreModule(Protocol):
    """A business module as the application mounts it: its routers, and how it attaches its
    services to the app once the kernel runtime exists."""

    @property
    def routers(self) -> Sequence[APIRouter]: ...

    def attach(self, app: FastAPI, runtime: CoreRuntime) -> None: ...


def _needs_stages(routers: Sequence[APIRouter]) -> bool:
    """Whether any route needs pipeline steps 6 to 8; credential routes do not."""
    return any(
        isinstance(route, ImsRoute) and not isinstance(route.ims_meta.access, NoPermission)
        for router in routers
        for route in router.routes
    )


def create_app(
    settings: CoreSettings | None = None,
    *,
    runtime: CoreRuntime | None = None,
    stages: PipelineStages | None = None,
    routers: Sequence[APIRouter] = (),
    modules: Sequence[CoreModule] = (),
    run_change_feed: bool = True,
) -> FastAPI:
    """Build the API application.

    ``routers`` are the modules' ``ImsRouter`` instances. Tenant routes cannot be mounted without
    the identity and access stages (pipeline steps 6 to 8): serving them unauthorised is not a
    configuration this function allows.
    """
    settings = settings or (runtime.settings if runtime else CoreSettings())
    all_routers = [*routers, *(router for module in modules for router in module.routers)]
    if stages is None and _needs_stages(all_routers):
        raise RuntimeError("tenant routes need the principal, rate-limit and authorise stages")

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = runtime is None
        active = runtime or await build_runtime(settings)
        app.state.runtime = active
        for module in modules:
            module.attach(app, active)
        if stages is not None:
            app.state.pipeline = active.pipeline(stages)
        feed: asyncio.Task[None] | None = None
        if run_change_feed:
            feed = asyncio.create_task(
                active.snapshots.run_change_feed(settings.change_feed_poll_seconds),
                name="licence-change-feed",
            )
        try:
            yield
        finally:
            if feed is not None:
                feed.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await feed
            if owned:
                await active.aclose()

    app = FastAPI(
        title="ZongoVita IMS Core",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    if runtime is not None:
        app.state.runtime = runtime
        for module in modules:
            module.attach(app, runtime)
        if stages is not None:
            app.state.pipeline = runtime.pipeline(stages)
    install_problem_handlers(app)
    for router in all_routers:
        app.include_router(router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(response: Response) -> dict[str, object]:
        # Ready even when the Registry is unreachable: last known-good keeps customers working
        # (AD-25). The flag is reported for operators, not used to take the instance out.
        active: CoreRuntime | None = getattr(app.state, "runtime", None)
        if active is None:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "ready", "registry_reachable": active.snapshots.registry_reachable}

    return app


def run() -> None:  # pragma: no cover - process entry point
    import uvicorn  # noqa: PLC0415

    use_selector_event_loop_on_windows()
    settings = CoreSettings()
    configure_logging(settings.service_name, settings.instance, settings.log_level)
    from ims_core.modules.identity import IdentityModule  # noqa: PLC0415

    # Credential routes need no access stages; tenant routes arrive with the access module (unit 3).
    app = create_app(settings, modules=[IdentityModule()])
    uvicorn.run(app, host="0.0.0.0", port=8080, log_config=None)  # noqa: S104


if __name__ == "__main__":  # pragma: no cover
    run()
