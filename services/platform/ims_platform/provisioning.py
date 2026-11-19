"""Customer provisioning runs (LLD 6.6, 4 provisioning_runs; AD-28, AD-13, LD-85).

One run per customer, executed as the LLD's step sequence. Every step is safe to repeat, so a
failed run resumes from the step that failed and never touches other customers:

    register           customer (status provisioning) and its draft licence
    database           CREATE DATABASE and the three roles            (database pipeline job)
    register_database  the database's location in the Registry (a secret reference only, LD-12)
    migrate            schema head, permission catalogue, seeded roles (database pipeline job)
    initial_users      the super admin, created by IMS Core in the customer's database
    activate           licence and customer active; change-feed rows

The Platform Service holds no DDL or customer-data credential (AD-13): database work runs as a
pipeline job (``PipelinePort``) and the super admin is created by Core (``CorePort``), which
reaches the customer's database itself. The super admin's one-time activation code is sealed
on the run until a system admin reveals it once (#21: no email channel yet).

Recovery approvers, also designated in LLD 6.6 step 6, need the break-glass tables of unit 12
(open issue U-16).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.clock import Clock
from ims_common.credentials import SecretBox
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_common.service_auth import ServiceTokenIssuer
from ims_contracts.enums import CustomerStatus, DatabaseStatus, Placement
from ims_contracts.errors import ErrorCode, FieldError
from ims_platform.registry import Actor, RegistryService, audit_change

log = logging.getLogger("ims.provisioning")

STEPS: tuple[str, ...] = ("register", "database", "register_database", "migrate", "initial_users", "activate")
SERVICE_AUDIENCE_CORE_INTERNAL = "ims-core-internal"
SYSTEM = Actor("system:provisioning")


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


# ===================================================================================== ports
@dataclass(frozen=True)
class DatabaseLocation:
    cluster_ref: str
    pooler_endpoint: str
    database_name: str
    app_role: str
    secret_ref: str


class PipelinePort(Protocol):
    """The CI/CD database pipeline (LD-85): the only executor of provisioning DDL and migrations."""

    async def provision_database(self, customer_code: str, placement: Placement) -> DatabaseLocation: ...

    async def migrate_database(self, customer_code: str, placement: Placement) -> str:
        """Returns the schema version the database is now at."""
        ...


@dataclass(frozen=True)
class SuperAdminCreated:
    user_id: UUID
    activation_code: str | None
    activation_expires_at: datetime | None


class CorePort(Protocol):
    async def create_super_admin(
        self, customer_id: UUID, run_id: UUID, *, login_identifier: str, display_name: str, email: str | None
    ) -> SuperAdminCreated: ...


class PipelineJobError(RuntimeError):
    """A pipeline job failed; the message is its error output, kept on the run."""


class SubprocessPipeline:
    """Runs the database pipeline CLI as a separate process with the pipeline's own identity.

    For local development and tests. In ZongoVita cloud this port is a CI/CD job trigger that
    waits for the job's result (LD-85; the CI/CD system is open item U-04). The Platform Service
    process itself never reads the migration or cluster credentials: the child process does.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        cluster_refs: dict[Placement, str],
        env: dict[str, str] | None = None,
        timeout_seconds: float = 600,
    ) -> None:
        self._command = list(command)
        self._clusters = cluster_refs
        self._env = env
        self._timeout = timeout_seconds

    def _cluster(self, placement: Placement) -> str:
        if placement not in self._clusters:
            raise PipelineJobError(f"no cluster is configured for {placement.value} placement")
        return self._clusters[placement]

    async def _run(self, *args: str) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            *self._command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **(self._env or {})},
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            raise PipelineJobError(f"pipeline job {args[0]} timed out") from None
        if process.returncode != 0:
            tail = err.decode("utf-8", "replace").strip().splitlines()[-5:]
            raise PipelineJobError(f"pipeline job {args[0]} failed: {' | '.join(tail)}")
        lines = [line for line in out.decode("utf-8").splitlines() if line.strip()]
        return json.loads(lines[-1])

    async def provision_database(self, customer_code: str, placement: Placement) -> DatabaseLocation:
        result = await self._run(
            "provision-customer-db", "--cluster", self._cluster(placement), "--customer", customer_code
        )
        return DatabaseLocation(
            cluster_ref=result["cluster_ref"],
            pooler_endpoint=result["pooler_endpoint"],
            database_name=result["database_name"],
            app_role=result["app_role"],
            secret_ref=result["secret_ref"],
        )

    async def migrate_database(self, customer_code: str, placement: Placement) -> str:
        result = await self._run(
            "migrate-customer-db", "--cluster", self._cluster(placement), "--customer", customer_code
        )
        return str(result["to"])


class HttpCore:
    """Calls IMS Core's internal provisioning endpoint with the Platform Service's own service
    token. The customer travels in the signed token's claims, never in the request (AD-21)."""

    def __init__(self, http: httpx.AsyncClient, tokens: ServiceTokenIssuer) -> None:
        self._http = http
        self._tokens = tokens

    async def create_super_admin(
        self, customer_id: UUID, run_id: UUID, *, login_identifier: str, display_name: str, email: str | None
    ) -> SuperAdminCreated:
        token = self._tokens.token_with(
            SERVICE_AUDIENCE_CORE_INTERNAL, {"cid": str(customer_id), "run": str(run_id)}
        )
        response = await self._http.post(
            "/internal/v1/provisioning/super-admin",
            headers={"Authorization": f"Bearer {token}"},
            json={"login_identifier": login_identifier, "display_name": display_name, "email": email},
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"IMS Core refused the super admin: {response.status_code} {response.text[:300]}"
            )
        body = response.json()
        expires = body.get("activation_expires_at")
        return SuperAdminCreated(
            user_id=UUID(body["user_id"]),
            activation_code=body.get("activation_code"),
            activation_expires_at=datetime.fromisoformat(expires) if expires else None,
        )


# ====================================================================================== runs
@dataclass(frozen=True)
class RunRow:
    id: UUID
    customer_id: UUID
    current_step: str
    status: str
    attempts: int
    last_error: str | None
    request: dict[str, Any]
    results: dict[str, Any]
    super_admin_user_id: UUID | None
    handover_available: bool
    requested_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    version: int


_RUN = (
    "id, customer_id, current_step, status, attempts, last_error, request, results, super_admin_user_id, "
    "handover_ciphertext IS NOT NULL AS handover_available, requested_by, created_at, updated_at, "
    "completed_at, version"
)
_READ_RUN = text("SELECT " + _RUN + " FROM platform.provisioning_runs WHERE id = :id")  # noqa: S608
_LIST_RUNS = text("SELECT " + _RUN + " FROM platform.provisioning_runs ORDER BY created_at DESC")  # noqa: S608
_RUN_OF_CUSTOMER = text("SELECT " + _RUN + " FROM platform.provisioning_runs WHERE customer_id = :id")  # noqa: S608


def _run(mapping: Any) -> RunRow | None:
    return RunRow(**mapping) if mapping else None


@dataclass(frozen=True)
class ProvisioningRequest:
    code: str
    legal_name: str
    gxp_mode: bool
    placement: Placement
    licence_no: str
    valid_from: datetime
    valid_until: datetime
    grace_days: int
    max_sites: int
    max_users: int
    modules: frozenset[str]
    super_admin_login: str
    super_admin_name: str
    super_admin_email: str | None

    def to_json(self) -> dict[str, Any]:
        return {
            "customer": {
                "code": self.code,
                "legal_name": self.legal_name,
                "gxp_mode": self.gxp_mode,
                "placement": self.placement.value,
            },
            "licence": {
                "licence_no": self.licence_no,
                "valid_from": self.valid_from.isoformat(),
                "valid_until": self.valid_until.isoformat(),
                "grace_days": self.grace_days,
                "max_sites": self.max_sites,
                "max_users": self.max_users,
                "modules": sorted(self.modules),
            },
            "super_admin": {
                "login_identifier": self.super_admin_login,
                "display_name": self.super_admin_name,
                "email": self.super_admin_email,
            },
        }


@dataclass(frozen=True)
class Handover:
    login_identifier: str
    activation_code: str
    activation_expires_at: str | None


class ProvisioningService:
    def __init__(
        self,
        engine: AsyncEngine,
        registry: RegistryService,
        *,
        pipeline: PipelinePort,
        core: CorePort,
        box: SecretBox,
        clock: Clock,
        stale_after: timedelta = timedelta(minutes=15),
    ) -> None:
        self._engine = engine
        self._registry = registry
        self._pipeline = pipeline
        self._core = core
        self._box = box
        self._clock = clock
        self._stale_after = stale_after
        self._tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------------------- reads
    async def list_runs(self) -> list[RunRow]:
        async with self._engine.connect() as conn:
            return [r for r in (_run(m) for m in (await conn.execute(_LIST_RUNS)).mappings()) if r]

    async def get_run(self, run_id: UUID) -> RunRow:
        async with self._engine.connect() as conn:
            run = _run((await conn.execute(_READ_RUN, {"id": run_id})).mappings().first())
        if run is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return run

    # ------------------------------------------------------------------------------- start
    async def start(self, actor: Actor, request: ProvisioningRequest) -> RunRow:
        """Step 1 (register) begins here: the customer, then its run, then the draft licence.
        If anything after the customer fails, the run is resumed rather than restarted."""
        if request.valid_until <= request.valid_from:
            raise _invalid("licence.valid_until", "must be after valid_from")
        if request.gxp_mode and request.placement is not Placement.DEDICATED:
            raise _invalid("customer.placement", "GxP customers are placed on a dedicated instance")
        async with self._engine.connect() as conn:
            existing = (
                (
                    await conn.execute(
                        text(
                            "SELECT c.id, c.status, r.id AS run_id FROM platform.customers c "
                            "LEFT JOIN platform.provisioning_runs r ON r.customer_id = c.id WHERE c.code "
                            "= :code"
                        ),
                        {"code": request.code},
                    )
                )
                .mappings()
                .first()
            )
        if existing is not None and existing["run_id"] is not None:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"customer {request.code} already has provisioning run {existing['run_id']}: resume it "
                f"instead",
            )
        if existing is not None and existing["status"] == CustomerStatus.PROVISIONING.value:
            # An earlier start registered the customer but stopped before its run existed.
            customer_id = existing["id"]
        else:
            customer_id = await self._registry.register_customer(
                code=request.code,
                legal_name=request.legal_name,
                actor=actor,
                gxp_mode=request.gxp_mode,
                placement=request.placement,
            )
        run_id = uuid7()
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO platform.provisioning_runs (id, customer_id, request, requested_by) "
                    "VALUES (:id, :customer, CAST(:request AS jsonb), :actor)"
                ),
                {
                    "id": run_id,
                    "customer": customer_id,
                    "request": json.dumps(request.to_json()),
                    "actor": actor.ref,
                },
            )
            await audit_change(
                conn,
                actor,
                "platform.provisioning.started",
                "provisioning_run",
                run_id,
                customer_id,
                after={"code": request.code, "steps": list(STEPS)},
            )
        return await self.get_run(run_id)

    # ----------------------------------------------------------------------------- resume
    async def claim_for_resume(self, actor: Actor, run_id: UUID) -> RunRow:
        """A failed run, or one whose executor died (no progress for ``stale_after``), may be
        resumed; two resumes cannot both win."""
        stale_before = self._clock.now() - self._stale_after
        async with self._engine.begin() as conn:
            claimed = (
                await conn.execute(
                    text(
                        "UPDATE platform.provisioning_runs SET status = 'running', last_error = NULL, "
                        "updated_at = now(), version = version + 1 WHERE id = :id AND (status = 'failed' "
                        "OR (status = 'running' AND updated_at < :stale)) RETURNING customer_id, current_step"
                    ),
                    {"id": run_id, "stale": stale_before},
                )
            ).first()
            if claimed is None:
                run = _run((await conn.execute(_READ_RUN, {"id": run_id})).mappings().first())
                if run is None:
                    raise DomainError(ErrorCode.NOT_FOUND)
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION,
                    "only a failed run, or a running one that has stopped making progress, can be resumed",
                )
            await audit_change(
                conn,
                actor,
                "platform.provisioning.resumed",
                "provisioning_run",
                run_id,
                claimed.customer_id,
                after={"from_step": claimed.current_step},
            )
        return await self.get_run(run_id)

    def execute_in_background(self, run_id: UUID) -> None:
        task = asyncio.create_task(self.execute(run_id), name=f"provisioning-{run_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_for_background(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    # ---------------------------------------------------------------------------- execute
    async def execute(self, run_id: UUID) -> RunRow:
        """Run the remaining steps in order. A failing step stops the run as failed, with the
        error kept on it; nothing after that step runs."""
        while True:
            run = await self.get_run(run_id)
            if run.status != "running" or run.current_step == "done":
                return run
            step = run.current_step
            try:
                result = await getattr(self, f"_step_{step}")(run)
            except Exception as exc:  # recorded on the run; resumed by an operator
                log.warning("provisioning step failed", extra={"run": str(run_id), "step": step})
                await self._fail(run, step, exc)
                return await self.get_run(run_id)
            await self._advance(run, step, result)

    async def _advance(self, run: RunRow, step: str, result: dict[str, Any]) -> None:
        position = STEPS.index(step)
        following = STEPS[position + 1] if position + 1 < len(STEPS) else "done"
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE platform.provisioning_runs SET current_step = :next, "
                    "results = results || CAST(:result AS jsonb), "
                    "status = CASE WHEN :next = 'done' THEN 'completed' ELSE status END, "
                    "completed_at = CASE WHEN :next = 'done' THEN now() ELSE completed_at END, "
                    "updated_at = now(), version = version + 1 WHERE id = :id AND current_step = :step"
                ),
                {"next": following, "result": json.dumps({step: result}), "id": run.id, "step": step},
            )
            await audit_change(
                conn,
                SYSTEM,
                "platform.provisioning.step_completed",
                "provisioning_run",
                run.id,
                run.customer_id,
                after={"step": step, "next": following},
            )

    async def _fail(self, run: RunRow, step: str, exc: BaseException) -> None:
        message = (exc.detail if isinstance(exc, DomainError) and exc.detail else str(exc)) or type(
            exc
        ).__name__
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE platform.provisioning_runs SET status = 'failed', last_error = :error, "
                    "attempts = attempts + 1, updated_at = now(), version = version + 1 WHERE id = :id"
                ),
                {"error": f"{step}: {message}"[:2000], "id": run.id},
            )
            await audit_change(
                conn,
                SYSTEM,
                "platform.provisioning.step_failed",
                "provisioning_run",
                run.id,
                run.customer_id,
                after={"step": step, "error": message[:500]},
            )

    # ------------------------------------------------------------------------------- steps
    async def _customer(self, conn: AsyncConnection, customer_id: UUID) -> dict[str, Any]:
        row = (
            (
                await conn.execute(
                    text("SELECT code, status, placement FROM platform.customers WHERE id = :id"),
                    {"id": customer_id},
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    async def _step_register(self, run: RunRow) -> dict[str, Any]:
        """The draft licence (the customer exists since start). Reused when already created."""
        licence = run.request["licence"]
        async with self._engine.connect() as conn:
            existing = (
                await conn.execute(
                    text("SELECT id FROM platform.licences WHERE customer_id = :c AND licence_no = :no"),
                    {"c": run.customer_id, "no": licence["licence_no"]},
                )
            ).scalar_one_or_none()
        if existing is None:
            existing = await self._registry.create_licence(
                customer_id=run.customer_id,
                licence_no=licence["licence_no"],
                valid_from=datetime.fromisoformat(licence["valid_from"]),
                valid_until=datetime.fromisoformat(licence["valid_until"]),
                grace_days=licence["grace_days"],
                max_sites=licence["max_sites"],
                max_users=licence["max_users"],
                modules=frozenset(licence["modules"]),
                actor=SYSTEM,
            )
        return {"licence_id": str(existing)}

    async def _step_database(self, run: RunRow) -> dict[str, Any]:
        customer = run.request["customer"]
        location = await self._pipeline.provision_database(customer["code"], Placement(customer["placement"]))
        return {
            "cluster_ref": location.cluster_ref,
            "pooler_endpoint": location.pooler_endpoint,
            "database_name": location.database_name,
            "app_role": location.app_role,
            "secret_ref": location.secret_ref,
        }

    async def _step_register_database(self, run: RunRow) -> dict[str, Any]:
        location = run.results["database"]
        async with self._engine.connect() as conn:
            registered = (
                await conn.execute(
                    text("SELECT 1 FROM platform.customer_databases WHERE customer_id = :c"),
                    {"c": run.customer_id},
                )
            ).first()
        if registered is None:
            await self._registry.register_database(
                customer_id=run.customer_id,
                cluster_ref=location["cluster_ref"],
                pooler_endpoint=location["pooler_endpoint"],
                database_name=location["database_name"],
                app_role=location["app_role"],
                secret_ref=location["secret_ref"],
                actor=SYSTEM,
            )
        return {"registered": True}

    async def _step_migrate(self, run: RunRow) -> dict[str, Any]:
        customer = run.request["customer"]
        version = await self._pipeline.migrate_database(customer["code"], Placement(customer["placement"]))
        await self._registry.record_database_state(
            run.customer_id, actor=SYSTEM, status=DatabaseStatus.READY, schema_version=version
        )
        return {"schema_version": version}

    async def _step_initial_users(self, run: RunRow) -> dict[str, Any]:
        admin = run.request["super_admin"]
        created = await self._core.create_super_admin(
            run.customer_id,
            run.id,
            login_identifier=admin["login_identifier"],
            display_name=admin["display_name"],
            email=admin["email"],
        )
        async with self._engine.begin() as conn:
            if created.activation_code is not None:
                sealed, key_id = self._box.seal(
                    json.dumps(
                        {
                            "activation_code": created.activation_code,
                            "activation_expires_at": created.activation_expires_at.isoformat()
                            if created.activation_expires_at
                            else None,
                        }
                    ).encode("utf-8"),
                    context=_handover_context(run.id),
                )
            else:
                sealed, key_id = None, None
            await conn.execute(
                text(
                    "UPDATE platform.provisioning_runs SET super_admin_user_id = :user, "
                    "handover_ciphertext = :sealed, handover_key_id = :key WHERE id = :id"
                ),
                {"user": created.user_id, "sealed": sealed, "key": key_id, "id": run.id},
            )
        return {
            "super_admin_user_id": str(created.user_id),
            "activation_code_issued": created.activation_code is not None,
        }

    async def _step_activate(self, run: RunRow) -> dict[str, Any]:
        licence_id = UUID(run.results["register"]["licence_id"])
        async with self._engine.connect() as conn:
            record_status = (
                await conn.execute(
                    text("SELECT record_status FROM platform.licences WHERE id = :id"), {"id": licence_id}
                )
            ).scalar_one()
            customer = await self._customer(conn, run.customer_id)
        if record_status == "draft":
            await self._registry.activate_licence(licence_id, actor=SYSTEM)
        if customer["status"] == CustomerStatus.PROVISIONING.value:
            await self._registry.activate_customer(run.customer_id, actor=SYSTEM)
        return {"activated": True}

    # ----------------------------------------------------------------------------- handover
    async def reveal_handover(self, actor: Actor, run_id: UUID) -> Handover:
        """The super admin's activation code, shown once to a system admin to hand over (#21)."""
        async with self._engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            "SELECT customer_id, request, handover_ciphertext, handover_key_id "
                            "FROM platform.provisioning_runs WHERE id = :id FOR UPDATE"
                        ),
                        {"id": run_id},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DomainError(ErrorCode.NOT_FOUND)
            if row["handover_ciphertext"] is None:
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION,
                    "there is no activation code to show: it was shown already or the super admin is not "
                    "created yet",
                )
            opened = json.loads(
                self._box.open(
                    bytes(row["handover_ciphertext"]),
                    key_id=row["handover_key_id"],
                    context=_handover_context(run_id),
                ).decode("utf-8")
            )
            await conn.execute(
                text(
                    "UPDATE platform.provisioning_runs SET handover_ciphertext = NULL, handover_key_id = "
                    "NULL, "
                    "updated_at = now(), version = version + 1 WHERE id = :id"
                ),
                {"id": run_id},
            )
            await audit_change(
                conn,
                actor,
                "platform.provisioning.handover_revealed",
                "provisioning_run",
                run_id,
                row["customer_id"],
            )
        return Handover(
            login_identifier=row["request"]["super_admin"]["login_identifier"],
            activation_code=opened["activation_code"],
            activation_expires_at=opened["activation_expires_at"],
        )


def _handover_context(run_id: UUID) -> str:
    return f"platform.provisioning_runs:handover:{run_id}"
