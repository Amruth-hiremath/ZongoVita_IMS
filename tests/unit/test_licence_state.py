"""Licence state machine (AD-78; LLD 6.4): derived from the snapshot and the local clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ims_common.ids import uuid7
from ims_contracts.enums import CustomerStatus, DatabaseStatus, Placement
from ims_contracts.licence import DatabaseLocation, LicenceSnapshot, LicenceState, derive_state

VALID_UNTIL = datetime(2027, 1, 1, tzinfo=UTC)


def snapshot(*, status: CustomerStatus = CustomerStatus.ACTIVE, grace_days: int = 14) -> LicenceSnapshot:
    return LicenceSnapshot(
        customer_id=uuid7(),
        customer_code="acme",
        customer_status=status,
        valid_from=VALID_UNTIL - timedelta(days=365),
        valid_until=VALID_UNTIL,
        grace_days=grace_days,
        modules=frozenset({"ims.core"}),
        max_sites=5,
        max_users=200,
        gxp_mode=False,
        gxp_locked=False,
        placement=Placement.SHARED,
        db=DatabaseLocation(
            cluster_ref="c1",
            pooler_endpoint="pooler:6432",
            database_name="ims_c_acme",
            app_role="ims_app_acme",
            secret_ref="customers/acme/db-app",
            schema_version="0001",
            status=DatabaseStatus.READY,
        ),
        fetched_at=VALID_UNTIL,
        feed_seq=1,
    )


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(days=-30), LicenceState.ACTIVE),
        (timedelta(microseconds=-1), LicenceState.ACTIVE),
        # Grace starts exactly when the end date is reached.
        (timedelta(0), LicenceState.GRACE),
        (timedelta(days=13, hours=23, minutes=59), LicenceState.GRACE),
        # Read-only starts exactly when the grace period ends.
        (timedelta(days=14), LicenceState.READ_ONLY),
        (timedelta(days=4000), LicenceState.READ_ONLY),
    ],
)
def test_state_follows_the_validity_dates(offset: timedelta, expected: LicenceState) -> None:
    assert derive_state(snapshot(), VALID_UNTIL + offset) is expected


def test_grace_period_is_per_contract() -> None:
    assert derive_state(snapshot(grace_days=30), VALID_UNTIL + timedelta(days=20)) is LicenceState.GRACE
    assert derive_state(snapshot(grace_days=0), VALID_UNTIL) is LicenceState.READ_ONLY


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CustomerStatus.SUSPENDED, LicenceState.SUSPENDED),
        (CustomerStatus.TERMINATED, LicenceState.TERMINATED),
    ],
)
@pytest.mark.parametrize("offset_days", [-100, 0, 5, 500])
def test_suspension_and_termination_override_the_dates(
    status: CustomerStatus, expected: LicenceState, offset_days: int
) -> None:
    assert derive_state(snapshot(status=status), VALID_UNTIL + timedelta(days=offset_days)) is expected


def test_naive_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        derive_state(snapshot(), datetime(2027, 1, 1))  # noqa: DTZ001 - the point of the test


def test_time_zone_of_now_does_not_matter() -> None:
    ist = timedelta(hours=5, minutes=30)
    from datetime import timezone  # noqa: PLC0415

    local = (VALID_UNTIL - timedelta(seconds=1)).astimezone(timezone(ist))
    assert derive_state(snapshot(), local) is LicenceState.ACTIVE


_ORDER = [LicenceState.ACTIVE, LicenceState.GRACE, LicenceState.READ_ONLY]


@given(
    grace_days=st.integers(min_value=0, max_value=366),
    first=st.integers(min_value=-10_000_000, max_value=40_000_000),
    later=st.integers(min_value=0, max_value=40_000_000),
)
def test_an_unrenewed_licence_only_ever_moves_forward(grace_days: int, first: int, later: int) -> None:
    """With no Registry change, time alone takes a customer active -> grace -> read-only, never back."""
    snap = snapshot(grace_days=grace_days)
    earlier_state = derive_state(snap, VALID_UNTIL + timedelta(seconds=first))
    later_state = derive_state(snap, VALID_UNTIL + timedelta(seconds=first + later))
    assert _ORDER.index(later_state) >= _ORDER.index(earlier_state)
