"""Route declarations (LLD section 7, LD-62, LD-72, LD-77).

Every tenant route states three things, and the application refuses to start without them:

* its access rule: exactly one permission, or one of the three written rules (no permission
  for credential endpoints, authenticated, or the gate's approver selector);
* its licensable module tag;
* whether it may run while the licence is in read-only state.

    router = ImsRouter(prefix="/ui/v1", audience=AUDIENCE_UI, module=LicenceModule.CORE)

    @router.get("/sites")
    @declare(access=Authenticated(), read_only_ok=True)
    async def list_sites(uow: Uow) -> ...:
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.routing import APIRoute, iter_route_contexts

from ims_core.kernel.context import TenantContext
from ims_core.kernel.uow import UnitOfWork

SAFE_METHODS = frozenset({"GET", "HEAD"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PERMISSION_RE = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z_]+$")
_META_ATTR = "__ims_route_meta__"


# ------------------------------------------------------------------------------- access rules
@dataclass(frozen=True)
class Access:
    """Base of the four access rules."""


@dataclass(frozen=True)
class NoPermission(Access):
    """Credential endpoints: the caller proves itself with a password, a challenge token, a
    signed token or a one-time code inside the handler. No access token, hence no tenant
    context from the pipeline."""


@dataclass(frozen=True)
class Authenticated(Access):
    """Any active principal of the customer: reference data and the caller's own records."""


@dataclass(frozen=True)
class Permission(Access):
    """Exactly one permission from the code-defined catalogue (module.resource.action)."""

    code: str

    def __post_init__(self) -> None:
        if not _PERMISSION_RE.fullmatch(self.code):
            raise ValueError(f"invalid permission code: {self.code!r}")


@dataclass(frozen=True)
class GateApprover(Access):
    """Approval decisions: eligibility comes from the gate's approver selector (section 8)."""


@dataclass(frozen=True)
class RouteMeta:
    access: Access
    read_only_ok: bool
    module: str = ""
    audience: str = ""
    #: Whether Idempotency-Key is required. Derived: every mutating route except credential ones.
    idempotent: bool = False
    method: str = ""
    template: str = ""

    @property
    def endpoint_label(self) -> str:
        return f"{self.method} {self.template}"


def declare(*, access: Access, read_only_ok: bool, module: str | None = None) -> Callable[[Any], Any]:
    """Attach the access rule, read-only flag and (optionally) a module tag to an endpoint."""
    if not isinstance(access, Access) or type(access) is Access:
        raise TypeError("access must be NoPermission, Authenticated, Permission or GateApprover")
    if not isinstance(read_only_ok, bool):
        raise TypeError("read_only_ok must be stated explicitly as True or False")

    def decorator(endpoint: Any) -> Any:
        setattr(
            endpoint, _META_ATTR, RouteMeta(access=access, read_only_ok=read_only_ok, module=module or "")
        )
        return endpoint

    return decorator


class RouteDeclarationError(RuntimeError):
    """A tenant route is missing part of its declaration. Raised at import time."""


class ImsRoute(APIRoute):
    """Runs the handler inside the request pipeline (LLD 6.1)."""

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        meta: RouteMeta | None = getattr(endpoint, _META_ATTR, None)
        if meta is None or not meta.module or not meta.audience or not meta.method:
            raise RouteDeclarationError(
                f"route {path!r} ({endpoint.__name__}) must be added through an ImsRouter and "
                "carry @declare(access=..., read_only_ok=...)"
            )
        # The base class builds the handler during its own initialisation, so the declaration
        # has to be in place first; the final path template is known only afterwards.
        self.ims_meta = replace(meta, template=path)
        super().__init__(path, endpoint, **kwargs)
        self.ims_meta = replace(meta, template=self.path_format)

    def get_route_handler(self) -> Callable[[Request], Any]:
        inner = super().get_route_handler()

        async def handler(request: Request) -> Response:
            return await request.app.state.pipeline.handle(request, self.ims_meta, inner)

        return handler


class ImsRouter(APIRouter):
    """Router for tenant routes of one API (audience) with a default licence module."""

    def __init__(self, *, audience: str, module: str, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", ImsRoute)
        super().__init__(**kwargs)
        self._audience = audience
        self._module = str(module)

    def add_api_route(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        declared: RouteMeta | None = getattr(endpoint, _META_ATTR, None)
        if declared is None:
            raise RouteDeclarationError(
                f"route {path!r} ({endpoint.__name__}) has no @declare(access=..., read_only_ok=...)"
            )
        methods = {m.upper() for m in (kwargs.get("methods") or ["GET"])}
        if len(methods) != 1:
            raise RouteDeclarationError(f"route {path!r} must handle exactly one HTTP method")
        method = next(iter(methods))
        if method not in SAFE_METHODS | MUTATING_METHODS:
            raise RouteDeclarationError(f"route {path!r}: unsupported method {method}")
        credential = isinstance(declared.access, NoPermission)
        if method in SAFE_METHODS and not declared.read_only_ok:
            raise RouteDeclarationError(f"route {path!r}: read routes are always read_only_ok (LD-77)")
        setattr(
            endpoint,
            _META_ATTR,
            replace(
                declared,
                module=declared.module or self._module,
                audience=self._audience,
                method=method,
                idempotent=method in MUTATING_METHODS and not credential,
            ),
        )
        super().add_api_route(path, endpoint, **kwargs)


def iter_tenant_routes(app: Any) -> list[ImsRoute]:
    """Every tenant route of an application, including those inside included routers."""
    found: list[ImsRoute] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if isinstance(route, ImsRoute):
            found.append(route)
    return found


def iter_route_meta(app: Any) -> list[RouteMeta]:
    """Every tenant route's declaration, for static checks and documentation."""
    return [route.ims_meta for route in iter_tenant_routes(app)]


# ------------------------------------------------------------------------- handler dependencies
def get_uow(request: Request) -> UnitOfWork:
    uow = getattr(request.state, "uow", None)
    if uow is None:
        raise RuntimeError("no unit of work: the route is not a tenant route with an access token")
    return uow


def get_context(request: Request) -> TenantContext:
    return get_uow(request).ctx


Uow = Annotated[UnitOfWork, Depends(get_uow)]
Ctx = Annotated[TenantContext, Depends(get_context)]
