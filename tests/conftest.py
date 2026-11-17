"""Fixtures shared by the database and kernel suites."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.pg import create_pooler_engine
from ims_core.kernel.runtime import CoreRuntime, build_runtime
from ims_core.kernel.settings import CoreSettings
from ims_core.kernel.tenant_settings import TenantSettings
from ims_core.main import create_app as create_core_app
from ims_platform.main import create_app as create_platform_app
from ims_platform.registry import RegistryService
from ims_platform.runtime import PlatformRuntime
from ims_platform.runtime import build_runtime as build_platform_runtime
from ims_platform.settings import PlatformSettings
from tests.support import probe
from tests.support.stack import PG_HOST, POOLER_PORT, Customer, Stack, bootstrap, onboard_customer


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> dict[str, object]:
    # The async PostgreSQL driver needs a selector loop; Windows defaults to proactor.
    return {"selector": asyncio.SelectorEventLoop}


# --------------------------------------------------------------------------------- the stack
@pytest_asyncio.fixture(scope="session")
async def stack(tmp_path_factory: pytest.TempPathFactory) -> Stack:
    """Wiped test cluster with a migrated Control-Plane database and all service keys."""
    return await bootstrap(Path(tmp_path_factory.mktemp("ims-stack")))


@pytest_asyncio.fixture(scope="session")
async def session_registry(stack: Stack) -> AsyncIterator[RegistryService]:
    """Registry commands for test setup, on the Platform Service's own role and the wall clock."""
    credential = await stack.platform_secrets.get("platform/db-app")
    engine = create_pooler_engine(
        host=PG_HOST,
        port=POOLER_PORT,
        database="ims_control_plane",
        user="platform_app",
        password=credential["password"],
        application_name="ims-tests-setup",
        pool_size=2,
        max_overflow=2,
        pool_timeout_s=10,
        sslmode="disable",
    )
    yield RegistryService(engine)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def customer_a(stack: Stack, session_registry: RegistryService) -> Customer:
    return await onboard_customer(stack, session_registry, "alpha", now=datetime.now(UTC))


@pytest_asyncio.fixture(scope="session")
async def customer_b(stack: Stack, session_registry: RegistryService) -> Customer:
    return await onboard_customer(stack, session_registry, "bravo", now=datetime.now(UTC))


@pytest_asyncio.fixture(scope="session")
async def customer_gxp(stack: Stack, session_registry: RegistryService) -> Customer:
    return await onboard_customer(stack, session_registry, "gxp_one", now=datetime.now(UTC), gxp_mode=True)


_code_counter = 0


@pytest.fixture
def fresh_code() -> str:
    """A customer code no other test in this run has used."""
    global _code_counter  # noqa: PLW0603
    _code_counter += 1
    return f"t{_code_counter:03d}"


# ------------------------------------------------------------------ per-test service wiring
@pytest.fixture
def clock() -> ManualClock:
    """Starts at the real time, then moves only when a test advances it."""
    return ManualClock(datetime.now(UTC))


class SwitchableTransport(httpx.AsyncBaseTransport):
    """Carries Core's calls to the in-process Platform Service; can simulate its outage."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner
        self.down = False
        self.requests = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        if self.down:
            raise httpx.ConnectError("simulated Platform Service outage", request=request)
        return await self._inner.handle_async_request(request)


@pytest_asyncio.fixture
async def platform(stack: Stack, clock: ManualClock) -> AsyncIterator[PlatformRuntime]:
    settings = PlatformSettings(
        environment="test",
        db_pooler_host=PG_HOST,
        db_pooler_port=POOLER_PORT,
        db_sslmode="disable",
        db_pool_size=2,
        db_max_overflow=2,
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
    )
    runtime = await build_platform_runtime(
        settings, secrets=stack.platform_secrets, object_store=stack.object_store, clock=clock
    )
    yield runtime
    await runtime.aclose()


@pytest.fixture
def platform_app(platform: PlatformRuntime) -> FastAPI:
    return create_platform_app(runtime=platform, run_bundle_publisher=False)


@pytest.fixture
def registry_link(platform_app: FastAPI) -> SwitchableTransport:
    return SwitchableTransport(httpx.ASGITransport(app=platform_app))


def core_settings(stack: Stack) -> CoreSettings:
    return CoreSettings(
        environment="test",
        instance="test-core",
        platform_base_url="http://platform.internal",
        db_sslmode="disable",
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
    )


async def new_core_runtime(stack: Stack, clock: ManualClock, link: httpx.AsyncBaseTransport) -> CoreRuntime:
    return await build_runtime(
        core_settings(stack),
        secrets=stack.core_secrets,
        object_store=stack.object_store,
        clock=clock,
        registry_transport=link,
    )


@pytest_asyncio.fixture
async def core(
    stack: Stack, clock: ManualClock, registry_link: SwitchableTransport
) -> AsyncIterator[CoreRuntime]:
    runtime = await new_core_runtime(stack, clock, registry_link)
    yield runtime
    await runtime.aclose()


@dataclass
class CoreApp:
    app: FastAPI
    runtime: CoreRuntime
    state: probe.ProbeState
    client: httpx.AsyncClient

    def user_token(self, customer: Customer | UUID, user_id: UUID | None = None) -> str:
        customer_id = customer.id if isinstance(customer, Customer) else customer
        return self.runtime.authenticator.issue_user_access(
            customer_id=customer_id, user_id=user_id or uuid7(), session_id=uuid7()
        )

    def api_token(self, customer: Customer) -> str:
        return self.runtime.authenticator.issue_api_client_access(customer_id=customer.id, client_id=uuid7())

    @staticmethod
    def auth(token: str, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", **extra}

    @staticmethod
    def key() -> str:
        return f"test-{uuid7()}"


def build_core_app(runtime: CoreRuntime) -> tuple[FastAPI, probe.ProbeState]:
    state = probe.ProbeState()
    app = create_core_app(
        runtime=runtime, stages=probe.stages(state), routers=probe.build_routers(), run_change_feed=False
    )
    app.state.probe = state
    app.state.tenant_settings = TenantSettings(probe.REGISTRY, runtime.clock)
    return app, state


@pytest_asyncio.fixture
async def core_app(core: CoreRuntime) -> AsyncIterator[CoreApp]:
    app, state = build_core_app(core)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
        yield CoreApp(app=app, runtime=core, state=state, client=client)
