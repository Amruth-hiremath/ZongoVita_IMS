"""Route declarations (LLD section 7, LD-62, LD-72, LD-77): undeclared routes cannot exist."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ims_contracts.enums import LicenceModule
from ims_core.kernel.authn import AUDIENCE_API, AUDIENCE_UI
from ims_core.kernel.routes import (
    Access,
    Authenticated,
    GateApprover,
    ImsRouter,
    NoPermission,
    Permission,
    RouteDeclarationError,
    declare,
    iter_route_meta,
)
from ims_core.kernel.settings import CoreSettings
from ims_core.main import create_app
from tests.support import probe


def router() -> ImsRouter:
    return ImsRouter(prefix="/ui/v1", audience=AUDIENCE_UI, module=LicenceModule.CORE)


def test_route_without_a_declaration_is_refused_at_import_time() -> None:
    r = router()
    with pytest.raises(RouteDeclarationError, match="no @declare"):

        @r.get("/things")
        async def things() -> dict:
            return {}


def test_read_only_flag_must_be_stated() -> None:
    with pytest.raises(TypeError):
        declare(access=Authenticated())  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="explicitly"):
        declare(access=Authenticated(), read_only_ok=None)  # type: ignore[arg-type]


def test_access_rule_must_be_one_of_the_four() -> None:
    with pytest.raises(TypeError):
        declare(access="catalog.item.view", read_only_ok=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        declare(access=Access(), read_only_ok=True)
    with pytest.raises(ValueError, match="invalid permission code"):
        Permission("catalog.item")
    with pytest.raises(ValueError, match="invalid permission code"):
        Permission("Catalog.Item.View")
    for rule in (NoPermission(), Authenticated(), Permission("catalog.item.view"), GateApprover()):
        declare(access=rule, read_only_ok=True)


def test_read_routes_are_always_read_only_ok() -> None:
    r = router()
    with pytest.raises(RouteDeclarationError, match="LD-77"):

        @r.get("/things")
        @declare(access=Authenticated(), read_only_ok=False)
        async def things() -> dict:
            return {}


def test_declared_routes_carry_module_audience_method_and_idempotency() -> None:
    r = router()

    @r.get("/things")
    @declare(access=Permission("catalog.item.view"), read_only_ok=True)
    async def list_things() -> dict:
        return {}

    @r.post("/things")
    @declare(access=Permission("catalog.item.create"), read_only_ok=False)
    async def create_thing() -> dict:
        return {}

    @r.post("/auth/login")
    @declare(access=NoPermission(), read_only_ok=True)
    async def login() -> dict:
        return {}

    @r.get("/planning")
    @declare(access=Authenticated(), read_only_ok=True, module=LicenceModule.REPLENISHMENT)
    async def planning() -> dict:
        return {}

    app = FastAPI()
    app.include_router(r)
    meta = {m.endpoint_label: m for m in iter_route_meta(app)}
    assert set(meta) == {
        "GET /ui/v1/things",
        "POST /ui/v1/things",
        "POST /ui/v1/auth/login",
        "GET /ui/v1/planning",
    }
    assert all(m.audience == AUDIENCE_UI for m in meta.values())
    assert meta["GET /ui/v1/things"].module == "ims.core"
    assert meta["GET /ui/v1/planning"].module == "ims.replenishment"
    # Idempotency-Key is required on every mutating route except credential endpoints.
    assert not meta["GET /ui/v1/things"].idempotent
    assert meta["POST /ui/v1/things"].idempotent
    assert not meta["POST /ui/v1/auth/login"].idempotent
    assert not meta["POST /ui/v1/things"].read_only_ok


def test_tenant_routes_cannot_be_mounted_without_the_access_stages() -> None:
    with pytest.raises(RuntimeError, match="stages"):
        create_app(CoreSettings(environment="test"), routers=probe.build_routers(), run_change_feed=False)


def test_every_probe_route_is_fully_declared() -> None:
    state = probe.ProbeState()
    app = create_app(
        CoreSettings(environment="test"),
        stages=probe.stages(state),
        routers=probe.build_routers(),
        run_change_feed=False,
    )
    metas = iter_route_meta(app)
    assert len(metas) >= 9
    for meta in metas:
        assert meta.module in {m.value for m in LicenceModule}
        assert meta.audience in {AUDIENCE_UI, AUDIENCE_API}
        assert meta.method and meta.template.startswith(("/ui/v1/", "/api/v1/"))


def test_file_adapters_are_refused_outside_local_and_test() -> None:
    with pytest.raises(ValueError, match="local development and tests only"):
        CoreSettings(environment="production")
    CoreSettings(environment="local")
