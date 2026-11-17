"""Access-control rules that need no database (LLD 5.1, section 7, LD-88)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from starlette.requests import Request

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode
from ims_contracts.permissions import (
    ACCESS_PERMISSIONS,
    ALL_CODES,
    CATALOGUE,
    RESERVED_TO_SUPER_ADMIN,
    SEEDED_BY_CODE,
    VIEW_PERMISSIONS,
    RoleKind,
)
from ims_core.kernel.authn import AccessClaims
from ims_core.kernel.grants import Grants
from ims_core.kernel.routes import Permission
from ims_core.kernel.versioning import expected_version
from ims_core.modules.access.evaluation import PermissionCache, grants_from
from ims_core.modules.access.ratelimit import RateLimiter, RateLimits
from ims_core.modules.access.repository import RoleRow
from ims_core.modules.access.service import role_code_from_name, role_label

A = UUID("018f6f2a-0000-7000-8000-0000000000a1")
B = UUID("018f6f2a-0000-7000-8000-0000000000b2")


# --------------------------------------------------------------------------- catalogue
def test_catalogue_is_the_lld_table() -> None:
    assert len(CATALOGUE) == len(ALL_CODES) == 62
    reserved = {"access.super_admin.transfer", "access.support.grant", "access.recovery_approver.manage"}
    assert reserved == RESERVED_TO_SUPER_ADMIN
    assert RESERVED_TO_SUPER_ADMIN < ACCESS_PERMISSIONS


def test_seeded_roles_follow_lld_5_1() -> None:
    assert SEEDED_BY_CODE["super_admin"].permissions == ALL_CODES
    assert SEEDED_BY_CODE["super_admin"].kind is RoleKind.SUPER_ADMIN
    assert SEEDED_BY_CODE["user_type_1"].permissions == ALL_CODES - RESERVED_TO_SUPER_ADMIN
    type2 = SEEDED_BY_CODE["user_type_2"].permissions
    assert type2 >= VIEW_PERMISSIONS, "Type 2 views all"
    assert {"issuance.request.approve", "transfers.transfer.approve", "counts.adjustment.approve"} <= type2
    assert {"returns.verdict.decide", "catalog.taxonomy.approve", "replenishment.threshold.approve"} <= type2
    assert {"purchasing.vendor.manage", "replenishment.formula.manage"} <= type2
    assert not {"catalog.item.create", "issuance.issue.fulfil", "reporting.export.run"} & type2
    type3 = SEEDED_BY_CODE["user_type_3"].permissions
    assert {"inventory.stock.view", "issuance.issue.fulfil", "returns.return.validate"} <= type3
    assert not {"audit.log.view", "returns.verdict.decide", "issuance.request.approve"} & type3
    assert SEEDED_BY_CODE["user_type_4"].permissions == {"issuance.request.create", "returns.return.create"}
    for code in ("user_type_1", "user_type_2", "user_type_3", "user_type_4"):
        assert not SEEDED_BY_CODE[code].permissions & RESERVED_TO_SUPER_ADMIN


def test_a_route_cannot_declare_a_permission_outside_the_catalogue() -> None:
    with pytest.raises(ValueError, match="not in the permission catalogue"):
        Permission("catalog.item.teleport")
    assert Permission("catalog.item.view").code == "catalog.item.view"


# -------------------------------------------------------------------------- evaluation
def test_effective_permissions_are_the_union_over_assignments_with_sites() -> None:
    grants = grants_from(
        [
            (A, "inventory.stock.view"),
            (B, "inventory.stock.view"),
            (A, "catalog.item.view"),  # not site-scoped: held everywhere
            (None, "issuance.request.create"),
            (A, "issuance.request.create"),  # every site already covers site A
            (A, None),  # a role without permissions
            (A, "legacy.removed.code"),  # unknown to this release: grants nothing
        ],
        super_admin=False,
    )
    assert grants.by_code == {
        "catalog.item.view": None,
        "issuance.request.create": None,
        "inventory.stock.view": frozenset({A, B}),
    }
    assert grants.holds_at("inventory.stock.view", A)
    assert not grants.holds_at("inventory.stock.view", uuid7())
    assert not grants.holds_at("inventory.stock.view", None)
    assert grants.sites("audit.log.view") == frozenset()
    assert grants.sites("issuance.request.create") is None
    assert not grants.is_super_admin


def test_the_super_admin_holds_everything_everywhere() -> None:
    grants = grants_from([(A, None)], super_admin=True)
    assert grants.is_super_admin
    assert set(grants.by_code) == ALL_CODES
    assert all(scope is None for scope in grants.by_code.values())


def test_site_checks_raise_the_lld_codes() -> None:
    grants = Grants(by_code={"transfers.transfer.dispatch": frozenset({A})})
    grants.require_site("transfers.transfer.dispatch", A)
    with pytest.raises(DomainError) as scope:
        grants.require_site("transfers.transfer.dispatch", B)
    assert scope.value.code is ErrorCode.SITE_SCOPE_DENIED
    with pytest.raises(DomainError) as missing:
        grants.require_site("transfers.transfer.receive", A)
    assert missing.value.code is ErrorCode.PERMISSION_DENIED


def test_permission_cache_is_keyed_by_access_version_and_expires() -> None:
    cache = PermissionCache(ttl_seconds=60, max_entries=2)
    customer, user = uuid7(), uuid7()
    grants = Grants(by_code={"catalog.item.view": None})
    cache.put(customer, "user", user, 7, 0.0, grants)
    assert cache.get(customer, "user", user, 7, 59.0) is grants
    assert cache.get(customer, "user", user, 8, 1.0) is None, "a new access version misses"
    assert cache.get(customer, "user", user, 7, 60.0) is None, "at most 60 seconds"
    for _ in range(3):
        cache.put(customer, "user", uuid7(), 1, 0.0, grants)
    assert len(cache._entries) == 2, "bounded"


# ------------------------------------------------------------------------------ labels
def _role(code: str, kind: RoleKind, user_type_no: int | None, name: str) -> RoleRow:
    now = datetime.now(UTC)
    return RoleRow(
        uuid7(), code, name, None, kind.value, user_type_no, kind is RoleKind.SUPER_ADMIN, now, now, 1
    )


def test_role_labels() -> None:
    type1 = _role("user_type_1", RoleKind.USER_TYPE, 1, "User Type 1")
    type2 = _role("user_type_2", RoleKind.USER_TYPE, 2, "User Type 2")
    auditor = _role("auditor", RoleKind.CUSTOM, None, "Auditor")
    assert role_label([type1], super_admin=True) == "Super Admin · Type 1"
    assert role_label([type2], super_admin=False) == "User Type 2"
    assert role_label([type2, auditor], super_admin=False) == "Type 2 · Auditor"
    assert role_label([auditor], super_admin=False) == "Auditor"
    assert role_label([], super_admin=False) == "No role assigned"


def test_custom_role_codes_are_derived_from_names() -> None:
    assert role_code_from_name("Site user admin") == "site_user_admin"
    assert role_code_from_name("Qualité / QA (Pune)") == "qualite_qa_pune"
    assert role_code_from_name("2nd shift") == "role_2nd_shift"


# --------------------------------------------------------------------------- If-Match
def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "PATCH", "headers": raw, "path": "/"})


def test_if_match_is_required_and_must_be_one_version() -> None:
    assert expected_version(_request({"If-Match": '"12"'})) == 12
    with pytest.raises(DomainError) as missing:
        expected_version(_request({}))
    assert missing.value.code is ErrorCode.PRECONDITION_REQUIRED
    for bad in ("*", '"1", "2"', 'W/"3"', "abc"):
        with pytest.raises(DomainError) as wrong:
            expected_version(_request({"If-Match": bad}))
        assert wrong.value.code is ErrorCode.VERSION_CONFLICT


# -------------------------------------------------------------------------- rate limits
@dataclass
class _Uow:
    clock: ManualClock
    ctx: SimpleNamespace


def _claims(principal_type: PrincipalType, subject: UUID) -> AccessClaims:
    return AccessClaims(
        subject=subject,
        principal_type=principal_type,
        customer_id=uuid7(),
        session_id=None,
        support_grant_id=None,
        token_id="t",
        expires_at=0,
    )


async def test_token_buckets_refill_continuously_and_answer_retry_after() -> None:
    clock = ManualClock(datetime.now(UTC))
    uow = _Uow(clock, SimpleNamespace(customer_id=uuid7()))
    limiter = RateLimiter(RateLimits(user_per_minute=3, customer_per_minute=100))
    user = _claims(PrincipalType.USER, uuid7())
    for _ in range(3):
        await limiter.check(uow, user)  # type: ignore[arg-type]
    with pytest.raises(DomainError) as limited:
        await limiter.check(uow, user)  # type: ignore[arg-type]
    assert limited.value.code is ErrorCode.RATE_LIMITED
    assert limited.value.headers == {"Retry-After": "20"}, "one token every 20 s at 3 per minute"
    clock.advance(seconds=20)
    await limiter.check(uow, user)  # type: ignore[arg-type]


async def test_a_refused_request_does_not_spend_the_other_bucket() -> None:
    clock = ManualClock(datetime.now(UTC))
    uow = _Uow(clock, SimpleNamespace(customer_id=uuid7()))
    limiter = RateLimiter(RateLimits(user_per_minute=2, customer_per_minute=3))
    first, second = _claims(PrincipalType.USER, uuid7()), _claims(PrincipalType.USER, uuid7())
    await limiter.check(uow, first)  # type: ignore[arg-type]
    await limiter.check(uow, first)  # type: ignore[arg-type]
    for _ in range(3):
        with pytest.raises(DomainError):
            await limiter.check(uow, first)  # type: ignore[arg-type]
    await limiter.check(uow, second)  # type: ignore[arg-type]  # the customer bucket still had one
    with pytest.raises(DomainError):
        await limiter.check(uow, second)  # type: ignore[arg-type]
