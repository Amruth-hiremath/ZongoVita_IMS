"""Platform Service application."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, Response
from sqlalchemy import text

from ims_common.logging import configure_logging
from ims_common.pg import use_selector_event_loop_on_windows
from ims_common.problem import install_problem_handlers
from ims_platform import api_internal
from ims_platform.runtime import PlatformRuntime, build_runtime
from ims_platform.settings import PlatformSettings


def create_app(
    settings: PlatformSettings | None = None,
    *,
    runtime: PlatformRuntime | None = None,
    run_bundle_publisher: bool = True,
) -> FastAPI:
    """Build the app. Tests pass a prepared ``runtime``; otherwise it is built at startup."""
    settings = settings or (runtime.settings if runtime else PlatformSettings())

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = runtime is None
        app.state.runtime = runtime or await build_runtime(settings)
        publisher: asyncio.Task[None] | None = None
        if run_bundle_publisher:
            publisher = asyncio.create_task(
                app.state.runtime.bundle_publisher.run(settings.bundle_interval_seconds),
                name="snapshot-bundle-publisher",
            )
        try:
            yield
        finally:
            if publisher is not None:
                publisher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await publisher
            if owned:
                await app.state.runtime.aclose()

    app = FastAPI(
        title="ZongoVita Platform Service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    if runtime is not None:
        app.state.runtime = runtime
    install_problem_handlers(app)
    app.include_router(api_internal.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(response: Response) -> dict[str, str]:
        try:
            async with app.state.runtime.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            response.status_code = 503
            return {"status": "control-plane database unreachable"}
        return {"status": "ready"}

    return app


def run() -> None:  # pragma: no cover - process entry point
    import uvicorn  # noqa: PLC0415

    use_selector_event_loop_on_windows()
    settings = PlatformSettings()
    configure_logging("ims-platform", settings.instance, settings.log_level)
    uvicorn.run(create_app(settings), host=settings.bind_host, port=settings.bind_port, log_config=None)


if __name__ == "__main__":  # pragma: no cover
    run()
