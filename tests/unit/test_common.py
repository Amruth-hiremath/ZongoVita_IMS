"""Shared runtime helpers: IDs, secrets store, snapshot bundle, JSON encoding, partition maths."""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ims_common.ddl import quote_ident
from ims_common.ids import uuid7, uuid7_timestamp_ms
from ims_common.secrets import (
    FileSecretsStore,
    SecretAccessDeniedError,
    SecretNotFoundError,
    db_secret_ref,
    validate_ref,
)
from ims_common.snapshot_bundle import BundleVerificationError, seal, unseal
from ims_common.tokens import KeySet
from ims_contracts.platform_api import SnapshotBundle
from ims_core.kernel import jsonutil
from ims_core.kernel.runtime import CORE_READABLE_SECRETS
from ims_core.schema.partitions import PARTITIONED_TABLES, add_months, months_to_ensure
from ims_platform.runtime import PLATFORM_READABLE_SECRETS
from tests.unit.test_licence_state import snapshot


# ------------------------------------------------------------------------------------- uuid7
def test_uuid7_is_version_7_and_time_ordered() -> None:
    before = time.time_ns() // 1_000_000
    values = [uuid7() for _ in range(20_000)]
    after = time.time_ns() // 1_000_000
    assert all(v.version == 7 and v.variant == "specified in RFC 4122" for v in values)
    assert len(set(values)) == len(values)
    assert values == sorted(values), "IDs generated later must sort later"
    # Bursts push the embedded timestamp ahead by at most a few milliseconds.
    assert before <= uuid7_timestamp_ms(values[0]) <= after + 50


# ------------------------------------------------------------------------------ secrets store
async def test_file_secrets_store_round_trip_and_missing(tmp_path: Path) -> None:
    store = FileSecretsStore(tmp_path, readable=("*",), writable=("*",))
    await store.put("customers/acme/db-app", {"username": "u", "password": "p"})
    assert await store.get("customers/acme/db-app") == {"username": "u", "password": "p"}
    with pytest.raises(SecretNotFoundError):
        await store.get("customers/acme/db-migration")


async def test_each_identity_reads_only_what_it_is_entitled_to(tmp_path: Path) -> None:
    pipeline = FileSecretsStore(tmp_path, readable=("*",), writable=("*",))
    for ref in (
        db_secret_ref("acme", "app"),
        db_secret_ref("acme", "migration"),
        db_secret_ref("acme", "breakglass"),
        "platform/db-app",
        "platform/db-migration",
        "platform/bundle-signing",
        "platform/bundle-verify",
        "core/token-signing",
        "clusters/shared-1/admin",
    ):
        await pipeline.put(ref, {"password": "x"})

    core = FileSecretsStore(tmp_path, readable=CORE_READABLE_SECRETS)
    await core.get(db_secret_ref("acme", "app"))
    await core.get("core/token-signing")
    await core.get("platform/bundle-verify")
    # Core never sees DDL credentials, break-glass credentials, platform keys or cluster admin.
    for denied in (
        db_secret_ref("acme", "migration"),
        db_secret_ref("acme", "breakglass"),
        "platform/db-app",
        "platform/bundle-signing",
        "clusters/shared-1/admin",
    ):
        with pytest.raises(SecretAccessDeniedError):
            await core.get(denied)

    platform = FileSecretsStore(tmp_path, readable=PLATFORM_READABLE_SECRETS)
    await platform.get("platform/db-app")
    await platform.get("platform/bundle-signing")
    # AD-13: the platform tier holds no credential that reads business data and no DDL credential.
    for denied in (
        db_secret_ref("acme", "app"),
        db_secret_ref("acme", "migration"),
        "clusters/shared-1/admin",
        "core/token-signing",
    ):
        with pytest.raises(SecretAccessDeniedError):
            await platform.get(denied)
    # Neither service identity can write secrets.
    with pytest.raises(SecretAccessDeniedError):
        await core.put("core/token-signing", {})
    with pytest.raises(SecretAccessDeniedError):
        await platform.put("platform/db-app", {})


@pytest.mark.parametrize(
    "ref", ["", "/abs", "a//b", "../etc/passwd", "a/../b", "A/b", "a b", "a/b.json", "a\\b"]
)
def test_secret_references_cannot_escape_the_store(ref: str) -> None:
    with pytest.raises(ValueError, match="invalid secret reference"):
        validate_ref(ref)


def test_identifier_quoting() -> None:
    assert quote_ident("ims_app_acme") == '"ims_app_acme"'
    assert quote_ident('we"ird') == '"we""ird"'
    with pytest.raises(ValueError, match="NUL"):
        quote_ident("a\x00b")


# ---------------------------------------------------------------------------- snapshot bundle
def _bundle() -> SnapshotBundle:
    return SnapshotBundle(
        generated_at=datetime(2026, 11, 16, tzinfo=UTC), feed_seq=7, snapshots=[snapshot()], directory=[]
    )


def test_bundle_round_trip_with_the_verification_key_only() -> None:
    keys = KeySet.generate("b1")
    sealed = seal(_bundle(), keys)
    opened = unseal(sealed, KeySet.from_secret(keys.public_secret()))
    assert opened.feed_seq == 7
    assert opened.snapshots[0].customer_code == "acme"


def test_bundle_with_wrong_or_broken_signature_is_refused() -> None:
    keys = KeySet.generate("b1")
    envelope = json.loads(seal(_bundle(), keys))

    with pytest.raises(BundleVerificationError):  # signed by someone else under the same key id
        unseal(seal(_bundle(), KeySet.generate("b1")), keys)

    forged_bundle = _bundle().model_copy(update={"feed_seq": 999})
    tampered = dict(envelope, payload=json.loads(seal(forged_bundle, KeySet.generate("zz")))["payload"])
    with pytest.raises(BundleVerificationError):  # payload swapped, original signature kept
        unseal(json.dumps(tampered).encode(), keys)

    for broken in (
        b"",
        b"not json",
        json.dumps({**envelope, "alg": "none"}).encode(),
        json.dumps({**envelope, "kid": "unknown"}).encode(),
        json.dumps({k: v for k, v in envelope.items() if k != "signature"}).encode(),
    ):
        with pytest.raises(BundleVerificationError):
            unseal(broken, keys)


# -------------------------------------------------------------------------------------- json
def test_json_encoding_follows_the_api_conventions() -> None:
    encoded = json.loads(
        jsonutil.dumps(
            {
                "qty": Decimal("12.5000"),
                "tiny": Decimal("0.0000001"),
                "id": UUID("018f0000-0000-7000-8000-000000000001"),
                "at": datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
                "day": date(2026, 11, 16),
                "tags": frozenset({"b", "a"}),
                "nested": [{"n": 1, "ok": True, "none": None}],
            }
        )
    )
    assert encoded == {
        "qty": "12.5000",
        "tiny": "0.0000001",
        "id": "018f0000-0000-7000-8000-000000000001",
        "at": "2026-11-16T09:30:00Z",
        "day": "2026-11-16",
        "tags": ["a", "b"],
        "nested": [{"n": 1, "ok": True, "none": None}],
    }


def test_json_encoding_refuses_lossy_or_ambiguous_values() -> None:
    with pytest.raises(TypeError, match="floats"):
        jsonutil.dumps({"qty": 1.1})
    with pytest.raises(TypeError, match="naive"):
        jsonutil.dumps({"at": datetime(2026, 1, 1)})  # noqa: DTZ001
    with pytest.raises(TypeError):
        jsonutil.dumps({"x": object()})


# -------------------------------------------------------------------------------- partitions
def test_month_arithmetic_crosses_year_boundaries() -> None:
    assert add_months(date(2026, 11, 16), 1) == date(2026, 12, 1)
    assert add_months(date(2026, 11, 16), 2) == date(2027, 1, 1)
    assert add_months(date(2027, 1, 31), -1) == date(2026, 12, 1)
    assert add_months(date(2026, 1, 1), -13) == date(2024, 12, 1)
    assert months_to_ensure(date(2026, 11, 30)) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]


def test_partition_names_and_bounds() -> None:
    audit = next(t for t in PARTITIONED_TABLES if t.table == "audit_log")
    assert audit.retention_days is None, "audit is permanent (Q22)"
    assert audit.partition_name(date(2026, 12, 1)) == "audit_log_y2026m12"
    sql = audit.create_partition_sql(date(2026, 12, 15))
    assert "audit.audit_log_y2026m12" in sql
    assert "FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00')" in sql
    assert audit.month_of_partition("audit_log_y2026m12") == date(2026, 12, 1)
    assert audit.month_of_partition("audit_log_default") is None
    outbox = next(t for t in PARTITIONED_TABLES if t.table == "outbox_events")
    assert outbox.retention_days == 400
    assert outbox.keep_while == "status = 'pending'"
