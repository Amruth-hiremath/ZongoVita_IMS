"""Request pipeline (LLD 6.1).

    1 Context      assign the request ID (an inbound one is accepted only from the BFF)
    2 Authenticate verify the JWT: signature by key ID, issuer, audience for this API, expiry
    3 Customer     read the cid claim into the tenant context; no other input is consulted
    4 Licence gate derive the licence state; read-only routes; licensed module
    5 Route        connection from that customer's pool; schema version in the supported range
    6 Principal    principal active, session not revoked, support grant active
    7 Rate limit   token buckets per user, per API client and per customer
    8 Authorise    declared permission and site scope
    9 Idempotency  key written in the business transaction
   10 Handler      unit of work; commit; response

Steps 6 to 10 share one transaction on the customer's database. The response is built before
the commit so the idempotency record can store it, and is only sent once the commit succeeded.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DBAPIError

from ims_common.clock import Clock
from ims_common.ids import uuid7
from ims_common.logging import customer_code_var, principal_var, request_id_var, trace_id_var
from ims_common.pg import (
    RETRYABLE_SQLSTATES,
    SQLSTATE_LOCK_NOT_AVAILABLE,
    SQLSTATE_QUERY_CANCELED,
    is_disconnect,
    sqlstate_of,
)
from ims_common.problem import DomainError, problem_response, validation_error
from ims_common.service_auth import ServiceTokenVerifier
from ims_common.tokens import TokenError
from ims_contracts.errors import ErrorCode
from ims_core.kernel import idempotency
from ims_core.kernel.authn import AccessClaims, Authenticator
from ims_core.kernel.context import Principal, TenantContext
from ims_core.kernel.db import DatabaseRouter
from ims_core.kernel.licence import LicenceGate
from ims_core.kernel.routes import SAFE_METHODS, NoPermission, RouteMeta
from ims_core.kernel.settings import CoreSettings
from ims_core.kernel.stages import PipelineStages
from ims_core.kernel.uow import UnitOfWork

log = logging.getLogger("ims.access")

REQUEST_ID_HEADER = "X-Request-ID"
SERVICE_TOKEN_HEADER = "X-IMS-Service-Token"  # noqa: S105 - a header name
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")
_AUDIENCE_SOURCE = {"ims-ui": "ui", "ims-api": "api"}

Handler = Callable[[Request], Awaitable[Response]]


class RequestPipeline:
    def __init__(
        self,
        *,
        settings: CoreSettings,
        clock: Clock,
        authenticator: Authenticator,
        gate: LicenceGate,
        router: DatabaseRouter,
        stages: PipelineStages,
        bff_verifier: ServiceTokenVerifier | None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._authenticator = authenticator
        self._gate = gate
        self._router = router
        self._stages = stages
        self._bff_verifier = bff_verifier

    # ------------------------------------------------------------------------------- step 1
    def _request_id(self, request: Request) -> str:
        inbound = request.headers.get(REQUEST_ID_HEADER)
        token = request.headers.get(SERVICE_TOKEN_HEADER)
        if inbound and token and self._bff_verifier and _REQUEST_ID_RE.fullmatch(inbound):
            try:
                self._bff_verifier.verify(token, allowed=frozenset({self._settings.bff_service_name}))
            except TokenError:
                pass
            else:
                return inbound
        return str(uuid7())

    @staticmethod
    def _trace_id(request: Request) -> str | None:
        match = _TRACEPARENT_RE.fullmatch(request.headers.get("traceparent", ""))
        return match.group(1) if match else None

    # ------------------------------------------------------------------------------ entry
    async def handle(self, request: Request, meta: RouteMeta, handler: Handler) -> Response:
        started = self._clock.monotonic()
        request_id = self._request_id(request)
        trace_id = self._trace_id(request)
        request.state.request_id = request_id
        tokens = (
            request_id_var.set(request_id),
            trace_id_var.set(trace_id),
            customer_code_var.set(None),
            principal_var.set(None),
        )
        code: str | None = None
        try:
            try:
                response = await self._run(request, meta, handler, request_id, trace_id)
            except RequestValidationError as exc:
                error = validation_error(exc)
                code, response = error.code, problem_response(error, request_id)
            except DomainError as exc:
                code, response = exc.code, problem_response(exc, request_id)
            except Exception:
                log.exception("unhandled error", extra={"route": meta.template, "method": meta.method})
                error = DomainError(ErrorCode.INTERNAL_ERROR)
                code, response = error.code, problem_response(error, request_id)
            response.headers[REQUEST_ID_HEADER] = request_id
            log.info(
                "request",
                extra={
                    "route": meta.template,
                    "method": meta.method,
                    "status": response.status_code,
                    "duration_ms": round((self._clock.monotonic() - started) * 1000, 1),
                    **({"code": code} if code else {}),
                },
            )
            return response
        finally:
            for var, token in zip(
                (request_id_var, trace_id_var, customer_code_var, principal_var), tokens, strict=True
            ):
                var.reset(token)

    # ------------------------------------------------------------------------- steps 2 to 10
    async def _run(
        self, request: Request, meta: RouteMeta, handler: Handler, request_id: str, trace_id: str | None
    ) -> Response:
        if isinstance(meta.access, NoPermission):
            # Credential endpoints: the handler authenticates the caller itself and builds the
            # tenant context through the kernel's login path.
            return await handler(request)

        claims = self._authenticator.authenticate(
            request.headers.get("authorization"), audience=meta.audience
        )
        snapshot, state = await self._gate.check(
            claims.customer_id, module=meta.module, read_only_ok=meta.read_only_ok
        )
        ctx = TenantContext(
            customer_id=snapshot.customer_id,
            customer_code=snapshot.customer_code,
            snapshot=snapshot,
            licence_state=state,
            request_id=request_id,
            source=_AUDIENCE_SOURCE[meta.audience],  # type: ignore[arg-type]
            principal=Principal(
                type=claims.principal_type,
                id=claims.subject,
                session_id=claims.session_id,
                support_grant_id=claims.support_grant_id,
            ),
            trace_id=trace_id,
        )
        customer_code_var.set(ctx.customer_code)
        principal_var.set(f"{claims.principal_type.value}:{claims.subject}")

        key: str | None = None
        digest = b""
        if meta.idempotent:
            key = idempotency.validate_key(request.headers.get(idempotency.IDEMPOTENCY_HEADER))
            path_and_query = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            digest = idempotency.request_hash(meta.method, path_and_query, await request.body())

        attempt = 0
        while True:
            attempt += 1
            try:
                return await self._attempt(request, meta, handler, ctx, claims, key, digest)
            except DBAPIError as exc:
                state_code = sqlstate_of(exc)
                if state_code in RETRYABLE_SQLSTATES and attempt <= self._settings.uow_max_retries:
                    # Deadlock or serialisation failure: the whole unit of work is retried.
                    log.warning("unit of work retried", extra={"sqlstate": state_code, "attempt": attempt})
                    await asyncio.sleep(random.uniform(0.01, 0.05) * attempt)  # noqa: S311 - jitter
                    continue
                translated = self._translate(exc, state_code)
                if translated is exc:
                    raise
                raise translated from exc

    async def _attempt(
        self,
        request: Request,
        meta: RouteMeta,
        handler: Handler,
        ctx: TenantContext,
        claims: AccessClaims,
        key: str | None,
        digest: bytes,
    ) -> Response:
        read_only = meta.method in SAFE_METHODS
        try:
            async with self._router.transaction(ctx, read_only=read_only) as conn:
                uow = UnitOfWork(ctx, conn, self._clock)
                await self._stages.principal.check(uow, claims)
                await self._stages.rate_limit.check(uow, claims)
                await self._stages.authorise.authorise(uow, meta.access)
                if key is not None:
                    stored = await idempotency.claim(
                        conn,
                        principal_id=claims.subject,
                        key=key,
                        endpoint=meta.endpoint_label,
                        digest=digest,
                    )
                    if stored is not None:
                        return Response(
                            content=stored.body,
                            status_code=stored.status_code,
                            media_type="application/json",
                            headers={idempotency.REPLAY_HEADER: "true"},
                        )
                request.state.uow = uow
                try:
                    response = await handler(request)
                finally:
                    request.state.uow = None
                if response.status_code >= 400:
                    # Handlers signal failure by raising DomainError; a returned error response
                    # still must not commit anything, so leave the transaction by exception.
                    raise _ReturnedError(response)
                if key is not None:
                    body = getattr(response, "body", None)
                    if not isinstance(body, (bytes, bytearray)):
                        raise RuntimeError(
                            f"{meta.endpoint_label}: idempotent routes need a buffered response"
                        )
                    await idempotency.complete(
                        conn,
                        principal_id=claims.subject,
                        key=key,
                        status_code=response.status_code,
                        body=bytes(body).decode("utf-8"),
                    )
        except _ReturnedError as returned:
            return returned.response
        await uow.run_after_commit()
        return response

    def _translate(self, exc: DBAPIError, state_code: str | None) -> Exception:
        """Database failures that have a defined client-facing meaning (LLD 9.1, 6.5)."""
        if state_code == SQLSTATE_LOCK_NOT_AVAILABLE:
            return DomainError(ErrorCode.STOCK_BUSY, headers={"Retry-After": "1"})
        if state_code in RETRYABLE_SQLSTATES:
            return DomainError(ErrorCode.STOCK_BUSY, headers={"Retry-After": "1"})
        if state_code == SQLSTATE_QUERY_CANCELED:
            return self._router.busy("the statement exceeded its time limit")
        if is_disconnect(exc) or "query_wait_timeout" in str(exc):
            return self._router.busy("the database connection was lost")
        return exc


class _ReturnedError(Exception):
    """Internal: a handler returned an error response instead of raising."""

    def __init__(self, response: Response) -> None:
        super().__init__(f"handler returned HTTP {response.status_code}")
        self.response = response
