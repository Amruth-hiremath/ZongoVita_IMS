"""Login Directory in the Platform Service (AD-20, AD-79; LLD 4, 6.3, 6.8)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text

from ims_common.clock import ManualClock
from ims_common.identifiers import key_from_secret, keyed_hash
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_common.secrets import SecretAccessDeniedError
from ims_common.service_auth import ServiceTokenIssuer
from ims_common.snapshot_bundle import BUNDLE_OBJECT_KEY, unseal
from ims_common.tokens import KeySet
from ims_contracts.enums import ChangeType
from ims_contracts.errors import ErrorCode
from ims_platform.directory import DirectoryService
from ims_platform.registry import Actor, RegistryService
from ims_platform.runtime import PlatformRuntime
from tests.support.stack import Stack, onboard_customer

pytestmark = pytest.mark.db

ACTOR = Actor("service:test")


@pytest.fixture
def directory(platform: PlatformRuntime) -> DirectoryService:
    return platform.directory


async def _customer(registry: RegistryService, code: str) -> UUID:
    return await registry.register_customer(code=code, legal_name=f"Directory test {code}", actor=ACTOR)


async def _refused(awaitable) -> ErrorCode:
    with pytest.raises(DomainError) as excinfo:
        await awaitable
    return excinfo.value.code


async def test_an_entry_resolves_only_once_active(
    directory: DirectoryService, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await _customer(session_registry, fresh_code)
    user = uuid7()
    identifier = f"{fresh_code}.priya@zongovita.in"
    reserved = await directory.reserve(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    assert reserved.status == "reserved"
    assert await directory.resolve(identifier) is None, (
        "a reservation is not a principal anyone can sign in as"
    )

    await directory.activate(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    await directory.activate(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    entry = await directory.resolve(identifier.upper())
    assert entry is not None
    assert (entry.customer_id, entry.principal_type, entry.principal_id, entry.status) == (
        customer,
        "user",
        user,
        "active",
    )
    again = await directory.reserve(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    assert (again.status, again.reserved_until) == ("active", None), (
        "reserving one's own active identifier is a no-op"
    )

    await directory.disable(customer_id=customer, principal_type="user", principal_id=user, actor=ACTOR)
    await directory.disable(customer_id=customer, principal_type="user", principal_id=user, actor=ACTOR)
    disabled = await directory.resolve(identifier)
    assert disabled is not None
    assert disabled.status == "disabled"
    assert [e.status for e in await directory.list_for_customer(customer)] == ["disabled"]
    assert (
        await _refused(
            directory.activate(
                customer_id=customer,
                principal_type="user",
                principal_id=user,
                identifier=identifier,
                actor=ACTOR,
            )
        )
        is ErrorCode.INVALID_STATE_TRANSITION
    )


async def test_an_identifier_belongs_to_one_principal_of_one_customer(
    directory: DirectoryService, session_registry: RegistryService, fresh_code: str
) -> None:
    first = await _customer(session_registry, fresh_code)
    second = await _customer(session_registry, f"{fresh_code}b")
    identifier = f"{fresh_code}.shared@zongovita.in"
    await directory.reserve(
        customer_id=first, principal_type="user", principal_id=uuid7(), identifier=identifier, actor=ACTOR
    )
    for variant in (identifier, identifier.upper(), f"  {identifier} "):
        code = await _refused(
            directory.reserve(
                customer_id=second,
                principal_type="user",
                principal_id=uuid7(),
                identifier=variant,
                actor=ACTOR,
            )
        )
        assert code is ErrorCode.LOGIN_IDENTIFIER_TAKEN
    # Same customer, another principal: equally taken.
    code = await _refused(
        directory.reserve(
            customer_id=first, principal_type="user", principal_id=uuid7(), identifier=identifier, actor=ACTOR
        )
    )
    assert code is ErrorCode.LOGIN_IDENTIFIER_TAKEN


async def test_a_principal_has_one_identifier(
    directory: DirectoryService, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await _customer(session_registry, fresh_code)
    user = uuid7()
    await directory.reserve(
        customer_id=customer,
        principal_type="user",
        principal_id=user,
        identifier=f"{fresh_code}.one@x.in",
        actor=ACTOR,
    )
    code = await _refused(
        directory.reserve(
            customer_id=customer,
            principal_type="user",
            principal_id=user,
            identifier=f"{fresh_code}.two@x.in",
            actor=ACTOR,
        )
    )
    assert code is ErrorCode.INVALID_STATE_TRANSITION


async def test_an_expired_reservation_can_be_taken_and_the_loser_cannot_activate(
    directory: DirectoryService, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> None:
    """LLD 6.3: "Another customer took the identifier meanwhile" -> the late activation fails."""
    first = await _customer(session_registry, fresh_code)
    second = await _customer(session_registry, f"{fresh_code}b")
    identifier = f"{fresh_code}.race@zongovita.in"
    late, winner = uuid7(), uuid7()
    await directory.reserve(
        customer_id=first, principal_type="user", principal_id=late, identifier=identifier, actor=ACTOR
    )
    clock.advance(seconds=15 * 60 - 1)
    assert (
        await _refused(
            directory.reserve(
                customer_id=second,
                principal_type="user",
                principal_id=winner,
                identifier=identifier,
                actor=ACTOR,
            )
        )
        is ErrorCode.LOGIN_IDENTIFIER_TAKEN
    ), "held for the full 15 minutes"
    clock.advance(seconds=1)
    await directory.reserve(
        customer_id=second, principal_type="user", principal_id=winner, identifier=identifier, actor=ACTOR
    )
    assert (
        await _refused(
            directory.activate(
                customer_id=first,
                principal_type="user",
                principal_id=late,
                identifier=identifier,
                actor=ACTOR,
            )
        )
        is ErrorCode.LOGIN_IDENTIFIER_TAKEN
    )
    await directory.activate(
        customer_id=second, principal_type="user", principal_id=winner, identifier=identifier, actor=ACTOR
    )
    entry = await directory.resolve(identifier)
    assert entry is not None
    assert (entry.customer_id, entry.principal_id) == (second, winner)


async def test_activation_succeeds_after_the_reservation_lapsed_if_nobody_took_it(
    directory: DirectoryService, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> None:
    """Activate-or-re-reserve (LLD 6.3), including an identifier that was never reserved."""
    customer = await _customer(session_registry, fresh_code)
    slow, unreserved = uuid7(), uuid7()
    await directory.reserve(
        customer_id=customer,
        principal_type="user",
        principal_id=slow,
        identifier=f"{fresh_code}.slow@x.in",
        actor=ACTOR,
    )
    clock.advance(seconds=3600)
    await directory.activate(
        customer_id=customer,
        principal_type="user",
        principal_id=slow,
        identifier=f"{fresh_code}.slow@x.in",
        actor=ACTOR,
    )
    await directory.activate(
        customer_id=customer,
        principal_type="api_client",
        principal_id=unreserved,
        identifier=str(unreserved),
        actor=ACTOR,
    )
    statuses = {
        e.principal_id: (e.principal_type, e.status) for e in await directory.list_for_customer(customer)
    }
    assert statuses == {slow: ("user", "active"), unreserved: ("api_client", "active")}


async def test_every_change_is_audited_and_announced_and_only_hashes_are_stored(
    stack: Stack, directory: DirectoryService, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await _customer(session_registry, fresh_code)
    user = uuid7()
    identifier = f"{fresh_code}.audit@zongovita.in"
    before = (await session_registry.changes(None)).head_seq
    await directory.reserve(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    await directory.activate(
        customer_id=customer, principal_type="user", principal_id=user, identifier=identifier, actor=ACTOR
    )
    await directory.disable(customer_id=customer, principal_type="user", principal_id=user, actor=ACTOR)
    changes = [c for c in (await session_registry.changes(before)).entries if c.customer_id == customer]
    assert [c.change_type for c in changes] == [ChangeType.DIRECTORY] * 3

    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.connect() as conn:
            actions = (
                (
                    await conn.execute(
                        text(
                            "SELECT action FROM platform.platform_audit WHERE customer_id = :c "
                            "AND entity_type = 'login_directory' ORDER BY seq"
                        ),
                        {"c": customer},
                    )
                )
                .scalars()
                .all()
            )
            row = (
                await conn.execute(
                    text(
                        "SELECT row_to_json(d)::text AS r, login_hash, lookup_hash FROM platform.login_directory d WHERE customer_id = :c"
                    ),
                    {"c": customer},
                )
            ).one()
            everything = "\n".join(
                (
                    await conn.execute(
                        text(
                            "SELECT row_to_json(a)::text FROM platform.platform_audit a WHERE customer_id = :c"
                        ),
                        {"c": customer},
                    )
                ).scalars()
            )
    finally:
        await engine.dispose()
    assert actions == ["directory.reserved", "directory.activated", "directory.disabled"]
    assert identifier not in row.r and identifier not in everything, (
        "the identifier itself is never stored (LD-10)"
    )
    assert len(bytes(row.login_hash)) == len(bytes(row.lookup_hash)) == 32
    assert bytes(row.login_hash) != bytes(row.lookup_hash)


async def test_the_bundle_carries_lookup_hashes_of_resolvable_entries_only(
    stack: Stack,
    platform: PlatformRuntime,
    session_registry: RegistryService,
    clock: ManualClock,
    fresh_code: str,
) -> None:
    customer = await onboard_customer(stack, session_registry, fresh_code, now=clock.now())
    directory = platform.directory
    active, reserved = uuid7(), uuid7()
    await directory.activate(
        customer_id=customer.id,
        principal_type="user",
        principal_id=active,
        identifier=f"{fresh_code}.on@x.in",
        actor=ACTOR,
    )
    await directory.reserve(
        customer_id=customer.id,
        principal_type="user",
        principal_id=reserved,
        identifier=f"{fresh_code}.held@x.in",
        actor=ACTOR,
    )
    await platform.bundle_publisher.publish_once()
    bundle = unseal(
        await stack.object_store.get(BUNDLE_OBJECT_KEY),
        KeySet.from_secret(await stack.core_secrets.get("platform/bundle-verify")),
    )
    mine = {e.principal_id: e for e in bundle.directory if e.customer_id == customer.id}
    assert set(mine) == {active}
    lookup_key = key_from_secret(await stack.core_secrets.get("shared/directory-lookup-key"))
    assert mine[active].lookup_hash == keyed_hash(lookup_key, f"{fresh_code}.ON@X.IN").hex()
    assert f"{fresh_code}.on@x.in" not in json.dumps(bundle.model_dump(mode="json"))


async def test_the_pepper_never_leaves_the_platform_service(stack: Stack) -> None:
    """LD-10: Core holds the lookup key (bundle lookups) but never the pepper."""
    await stack.platform_secrets.get("platform/login-pepper")
    await stack.platform_secrets.get("shared/directory-lookup-key")
    await stack.core_secrets.get("shared/directory-lookup-key")
    with pytest.raises(SecretAccessDeniedError):
        await stack.core_secrets.get("platform/login-pepper")


# --------------------------------------------------------------------------- internal API
@pytest_asyncio.fixture
async def client(platform_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=platform_app), base_url="http://platform"
    ) as c:
        yield c


def _as(stack: Stack, service: str, clock: ManualClock) -> dict[str, str]:
    token = ServiceTokenIssuer(service, stack.service_keys[service], clock).token_for("platform-internal")
    return {"Authorization": f"Bearer {token}"}


async def test_internal_directory_endpoints(
    stack: Stack,
    client: httpx.AsyncClient,
    clock: ManualClock,
    session_registry: RegistryService,
    fresh_code: str,
) -> None:
    customer = await _customer(session_registry, fresh_code)
    other = await _customer(session_registry, f"{fresh_code}b")
    core, worker = _as(stack, "ims-core", clock), _as(stack, "ims-worker", clock)
    user = uuid7()
    identifier = f"{fresh_code}.api@zongovita.in"
    body = {
        "customer_id": str(customer),
        "principal_type": "user",
        "principal_id": str(user),
        "identifier": identifier,
    }

    reserved = await client.post("/internal/v1/directory/reservations", json=body, headers=core)
    assert reserved.status_code == 201
    assert reserved.json()["status"] == "reserved"
    assert datetime.fromisoformat(reserved.json()["reserved_until"]) > datetime.now(UTC)
    taken = await client.post(
        "/internal/v1/directory/reservations",
        json={**body, "customer_id": str(other), "principal_id": str(uuid7())},
        headers=core,
    )
    assert (taken.status_code, taken.json()["code"]) == (409, "LOGIN_IDENTIFIER_TAKEN")
    assert (
        await client.post("/internal/v1/directory/resolve", json={"identifier": identifier}, headers=core)
    ).status_code == 404

    activation = {"customer_id": str(customer), "principal_type": "user", "identifier": identifier}
    assert (
        await client.post(f"/internal/v1/directory/{user}/activate", json=activation, headers=worker)
    ).status_code == 204
    resolved = await client.post(
        "/internal/v1/directory/resolve", json={"identifier": identifier.upper()}, headers=core
    )
    assert resolved.status_code == 200
    assert resolved.json() == {
        "customer_id": str(customer),
        "principal_type": "user",
        "principal_id": str(user),
        "status": "active",
    }

    listing = await client.get(
        "/internal/v1/directory", params={"customer_id": str(customer)}, headers=worker
    )
    assert [e["principal_id"] for e in listing.json()["entries"]] == [str(user)]
    disable = {"customer_id": str(customer), "principal_type": "user"}
    assert (
        await client.post(f"/internal/v1/directory/{user}/disable", json=disable, headers=worker)
    ).status_code == 204

    # Who may call what: resolving and reserving belong to Core alone; nobody else at all.
    assert (
        await client.post("/internal/v1/directory/resolve", json={"identifier": identifier}, headers=worker)
    ).status_code == 401
    assert (
        await client.post("/internal/v1/directory/reservations", json=body, headers=worker)
    ).status_code == 401
    assert (
        await client.post("/internal/v1/directory/resolve", json={"identifier": identifier})
    ).status_code == 401
    bff = _as(stack, "tenant-web-bff", clock)
    assert (
        await client.post("/internal/v1/directory/resolve", json={"identifier": identifier}, headers=bff)
    ).status_code == 401
    bad = await client.post(
        "/internal/v1/directory/reservations", json={**body, "identifier": "has space@x.in"}, headers=core
    )
    assert (bad.status_code, bad.json()["code"]) == (422, "VALIDATION_FAILED")
