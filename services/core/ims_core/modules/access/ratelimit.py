"""Pipeline step 7: rate limits (LD-88, AD-84; LLD 6.1, 12, 16).

Token buckets per user (300 requests per minute), per API client (its own
``rate_limit_per_minute``, 600 by default) and per customer (6,000 across both APIs). A bucket
holds one minute's allowance and refills continuously, so short bursts pass and a sustained rate
above the limit is refused with 429 RATE_LIMITED and Retry-After.

The buckets live in each Core process: the LLD keeps no shared cache (section 16). With several
instances behind the load balancer the effective ceiling is the per-process limit times the
number of instances; the per-customer database limits (pool size, statement timeout) still hold
whatever the request rate (decision I-28).
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from ims_common.problem import DomainError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode
from ims_core.kernel.authn import AccessClaims
from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.identity.public import api_client_rate_limit


class TokenBucket:
    __slots__ = ("capacity", "per_second", "tokens", "updated")

    def __init__(self, per_minute: int, now: float) -> None:
        self.capacity = float(per_minute)
        self.per_second = per_minute / 60.0
        self.tokens = float(per_minute)
        self.updated = now

    def resize(self, per_minute: int) -> None:
        if per_minute != self.capacity:
            self.capacity = float(per_minute)
            self.per_second = per_minute / 60.0
            self.tokens = min(self.tokens, self.capacity)

    def refill(self, now: float) -> None:
        if now > self.updated:
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.per_second)
            self.updated = now

    def seconds_until_one(self) -> float:
        return 0.0 if self.tokens >= 1 else (1 - self.tokens) / self.per_second


@dataclass(frozen=True)
class RateLimits:
    user_per_minute: int = 300
    api_client_default_per_minute: int = 600
    customer_per_minute: int = 6_000


class RateLimiter:
    """The rate-limit stage. Buckets are kept for the most recently active principals only; a
    bucket evicted for space starts full again, which errs on the side of serving."""

    def __init__(
        self,
        limits: RateLimits | None = None,
        *,
        max_buckets: int = 100_000,
        client_limit_ttl_seconds: float = 60.0,
    ) -> None:
        self.limits = limits or RateLimits()
        self._max = max_buckets
        self._buckets: OrderedDict[tuple[object, ...], TokenBucket] = OrderedDict()
        self._client_limits: dict[tuple[UUID, UUID], tuple[int, float]] = {}
        self._client_ttl = client_limit_ttl_seconds

    def _bucket(self, key: tuple[object, ...], per_minute: int, now: float) -> TokenBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(per_minute, now)
            self._buckets[key] = bucket
            while len(self._buckets) > self._max:
                self._buckets.popitem(last=False)
        else:
            bucket.resize(per_minute)
            self._buckets.move_to_end(key)
        bucket.refill(now)
        return bucket

    async def _client_limit(self, uow: UnitOfWork, client_id: UUID, now: float) -> int:
        key = (uow.ctx.customer_id, client_id)
        cached = self._client_limits.get(key)
        if cached is not None and now - cached[1] < self._client_ttl:
            return cached[0]
        limit = await api_client_rate_limit(uow, client_id) or self.limits.api_client_default_per_minute
        self._client_limits[key] = (limit, now)
        return limit

    async def check(self, uow: UnitOfWork, claims: AccessClaims) -> None:
        now = uow.clock.monotonic()
        customer_id = uow.ctx.customer_id
        if claims.principal_type is PrincipalType.API_CLIENT:
            principal_limit = await self._client_limit(uow, claims.subject, now)
        else:
            principal_limit = self.limits.user_per_minute
        principal = self._bucket(
            ("principal", customer_id, claims.principal_type.value, claims.subject), principal_limit, now
        )
        customer = self._bucket(("customer", customer_id), self.limits.customer_per_minute, now)
        if principal.tokens < 1 or customer.tokens < 1:
            wait = max(principal.seconds_until_one(), customer.seconds_until_one())
            raise DomainError(ErrorCode.RATE_LIMITED, headers={"Retry-After": str(max(1, math.ceil(wait)))})
        principal.tokens -= 1
        customer.tokens -= 1
