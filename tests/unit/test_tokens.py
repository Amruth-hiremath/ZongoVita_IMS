"""Token signing and verification (LLD 6.2; AD-21, AD-63, AD-64)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_common.service_auth import ServiceTokenIssuer, ServiceTokenVerifier
from ims_common.tokens import KeySet, TokenCodec, TokenError
from ims_contracts.errors import ErrorCode
from ims_core.kernel.authn import AUDIENCE_API, AUDIENCE_UI, Authenticator

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(NOW)


@pytest.fixture
def keys() -> KeySet:
    return KeySet.generate("k1")


@pytest.fixture
def codec(keys: KeySet, clock: ManualClock) -> TokenCodec:
    return TokenCodec(keys, "ims-core", clock)


def _swap_payload(token: str, **changes: object) -> str:
    """Change claims but keep the original signature, as an attacker without the key would."""
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims.update(changes)
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{forged}.{signature}"


def test_round_trip_carries_the_claims(codec: TokenCodec) -> None:
    token = codec.encode(subject="u1", audience="ims-ui", ttl=timedelta(minutes=15), claims={"cid": "c1"})
    claims = codec.decode(token, audience="ims-ui")
    assert claims["sub"] == "u1"
    assert claims["cid"] == "c1"
    assert claims["iss"] == "ims-core"
    assert claims["exp"] - claims["iat"] == 900
    assert jwt.get_unverified_header(token) == {"alg": "EdDSA", "kid": "k1", "typ": "JWT"}


def test_token_expires_on_the_injected_clock(codec: TokenCodec, clock: ManualClock) -> None:
    token = codec.encode(subject="u1", audience="ims-ui", ttl=timedelta(minutes=15))
    clock.advance(seconds=899)
    codec.decode(token, audience="ims-ui")
    clock.advance(seconds=1)
    with pytest.raises(TokenError) as excinfo:
        codec.decode(token, audience="ims-ui")
    assert excinfo.value.reason == "expired"


def test_wrong_audience_is_rejected(codec: TokenCodec) -> None:
    token = codec.encode(subject="u1", audience="ims-refresh", ttl=timedelta(minutes=15))
    with pytest.raises(TokenError) as excinfo:
        codec.decode(token, audience="ims-ui")
    assert excinfo.value.reason == "invalid"


def test_wrong_issuer_is_rejected(keys: KeySet, clock: ManualClock) -> None:
    # The Platform Service issues with a different issuer; Core must reject its tokens.
    platform_token = TokenCodec(keys, "ims-platform", clock).encode(
        subject="staff", audience="ims-ui", ttl=timedelta(minutes=15)
    )
    with pytest.raises(TokenError):
        TokenCodec(keys, "ims-core", clock).decode(platform_token, audience="ims-ui")


def test_tampered_customer_claim_fails_the_signature(codec: TokenCodec) -> None:
    token = codec.encode(subject="u1", audience="ims-ui", ttl=timedelta(minutes=15), claims={"cid": "A"})
    with pytest.raises(TokenError) as excinfo:
        codec.decode(_swap_payload(token, cid="B"), audience="ims-ui")
    assert excinfo.value.reason == "invalid"


def test_token_signed_with_another_key_is_rejected(codec: TokenCodec, clock: ManualClock) -> None:
    attacker = TokenCodec(KeySet.generate("k1"), "ims-core", clock)  # same key id, different key
    token = attacker.encode(subject="u1", audience="ims-ui", ttl=timedelta(minutes=15))
    with pytest.raises(TokenError):
        codec.decode(token, audience="ims-ui")


@pytest.mark.parametrize("alg", ["none", "HS256"])
def test_other_algorithms_are_rejected(codec: TokenCodec, alg: str) -> None:
    claims = {"iss": "ims-core", "aud": "ims-ui", "sub": "u1", "iat": 1, "exp": 9999999999, "jti": "x"}
    forged = jwt.encode(
        claims, key="" if alg == "none" else "secret" * 8, algorithm=alg, headers={"kid": "k1"}
    )
    with pytest.raises(TokenError):
        codec.decode(forged, audience="ims-ui")


def test_garbage_is_rejected(codec: TokenCodec) -> None:
    for value in ("", "abc", "a.b.c", "....."):
        with pytest.raises(TokenError):
            codec.decode(value, audience="ims-ui")


def test_rotation_keeps_the_previous_key_valid_and_drops_older_ones(clock: ManualClock) -> None:
    k1 = KeySet.generate("k1")
    old_token = TokenCodec(k1, "ims-core", clock).encode(subject="u", audience="a", ttl=timedelta(hours=1))
    k2 = k1.rotated("k2")
    assert set(k2.public) == {"k1", "k2"}
    assert set(k2.private) == {"k2"}  # the outgoing private key is gone
    assert TokenCodec(k2, "ims-core", clock).decode(old_token, audience="a")["sub"] == "u"
    new_token = TokenCodec(k2, "ims-core", clock).encode(subject="u", audience="a", ttl=timedelta(hours=1))
    assert jwt.get_unverified_header(new_token)["kid"] == "k2"
    k3 = k2.rotated("k3")
    assert set(k3.public) == {"k2", "k3"}
    with pytest.raises(TokenError):
        TokenCodec(k3, "ims-core", clock).decode(old_token, audience="a")


def test_key_set_survives_the_secrets_store_and_public_view_cannot_sign(
    keys: KeySet, clock: ManualClock
) -> None:
    restored = KeySet.from_secret(json.loads(json.dumps(keys.to_secret())))
    token = TokenCodec(restored, "svc", clock).encode(subject="s", audience="a", ttl=timedelta(minutes=1))
    verify_only = KeySet.from_secret(keys.public_secret())
    assert "private_pem" not in json.dumps(keys.public_secret())
    assert TokenCodec(verify_only, "svc", clock).decode(token, audience="a")["sub"] == "s"
    with pytest.raises(RuntimeError):
        TokenCodec(verify_only, "svc", clock).encode(subject="s", audience="a", ttl=timedelta(minutes=1))
    with pytest.raises(RuntimeError):
        verify_only.sign(b"payload")


# ------------------------------------------------------------------------------ service tokens
def test_service_tokens_are_accepted_only_from_trusted_allowed_callers(clock: ManualClock) -> None:
    core, worker, stranger = KeySet.generate("c"), KeySet.generate("w"), KeySet.generate("s")
    verifier = ServiceTokenVerifier(
        "platform-internal",
        {
            "ims-core": KeySet.from_secret(core.public_secret()),
            "ims-worker": KeySet.from_secret(worker.public_secret()),
        },
        clock,
    )
    core_token = ServiceTokenIssuer("ims-core", core, clock).token_for("platform-internal")
    assert verifier.verify(core_token).name == "ims-core"
    # A trusted service that this endpoint does not allow.
    with pytest.raises(TokenError):
        verifier.verify(core_token, allowed=frozenset({"ims-worker"}))
    # An unknown service, and a known name signed with the wrong key.
    with pytest.raises(TokenError):
        verifier.verify(ServiceTokenIssuer("ims-other", stranger, clock).token_for("platform-internal"))
    with pytest.raises(TokenError):
        verifier.verify(ServiceTokenIssuer("ims-core", stranger, clock).token_for("platform-internal"))
    # Right service, token minted for a different audience.
    with pytest.raises(TokenError):
        verifier.verify(ServiceTokenIssuer("ims-core", core, clock).token_for("ims-core-internal"))


def test_service_token_is_reused_then_renewed_before_it_expires(clock: ManualClock) -> None:
    keys = KeySet.generate("c")
    issuer = ServiceTokenIssuer("ims-core", keys, clock)
    verifier = ServiceTokenVerifier("aud", {"ims-core": keys}, clock)
    first = issuer.token_for("aud")
    assert issuer.token_for("aud") is first
    clock.advance(seconds=50)
    second = issuer.token_for("aud")
    assert second != first
    clock.advance(seconds=30)  # the first would be expired now; the renewed one is not
    verifier.verify(second)
    with pytest.raises(TokenError):
        verifier.verify(first)


# --------------------------------------------------------------------------- access-token rules
def test_authenticator_enforces_audience_per_principal_type(codec: TokenCodec) -> None:
    auth = Authenticator(codec)
    customer, user, session, client = uuid7(), uuid7(), uuid7(), uuid7()
    user_token = auth.issue_user_access(customer_id=customer, user_id=user, session_id=session)
    api_token = auth.issue_api_client_access(customer_id=customer, client_id=client)

    claims = auth.authenticate(f"Bearer {user_token}", audience=AUDIENCE_UI)
    assert (claims.customer_id, claims.subject, claims.session_id) == (customer, user, session)
    assert auth.authenticate(f"bearer {api_token}", audience=AUDIENCE_API).subject == client

    for header, audience in [
        (f"Bearer {user_token}", AUDIENCE_API),
        (f"Bearer {api_token}", AUDIENCE_UI),
        (None, AUDIENCE_UI),
        ("", AUDIENCE_UI),
        (f"Basic {user_token}", AUDIENCE_UI),
        ("Bearer ", AUDIENCE_UI),
    ]:
        with pytest.raises(DomainError) as excinfo:
            auth.authenticate(header, audience=audience)
        assert excinfo.value.code is ErrorCode.AUTH_REQUIRED
        assert excinfo.value.status == 401


def test_authenticator_rejects_structurally_wrong_claims(codec: TokenCodec) -> None:
    auth = Authenticator(codec)
    ttl = timedelta(minutes=5)
    bad = [
        codec.encode(subject=str(uuid7()), audience=AUDIENCE_UI, ttl=ttl, claims={"ptype": "user"}),  # no cid
        codec.encode(
            subject=str(uuid7()), audience=AUDIENCE_UI, ttl=ttl, claims={"ptype": "user", "cid": "not-a-uuid"}
        ),
        codec.encode(  # a user token without a session
            subject=str(uuid7()), audience=AUDIENCE_UI, ttl=ttl, claims={"ptype": "user", "cid": str(uuid7())}
        ),
        codec.encode(  # support without a grant
            subject=str(uuid7()),
            audience=AUDIENCE_UI,
            ttl=ttl,
            claims={"ptype": "support", "cid": str(uuid7()), "sid": str(uuid7())},
        ),
        codec.encode(
            subject=str(uuid7()), audience=AUDIENCE_UI, ttl=ttl, claims={"ptype": "root", "cid": str(uuid7())}
        ),
    ]
    for token in bad:
        with pytest.raises(DomainError) as excinfo:
            auth.authenticate(f"Bearer {token}", audience=AUDIENCE_UI)
        assert excinfo.value.code is ErrorCode.AUTH_REQUIRED


def test_expired_access_token_reports_token_expired(codec: TokenCodec, clock: ManualClock) -> None:
    auth = Authenticator(codec)
    token = auth.issue_user_access(customer_id=uuid7(), user_id=uuid7(), session_id=uuid7())
    clock.advance(seconds=15 * 60)
    with pytest.raises(DomainError) as excinfo:
        auth.authenticate(f"Bearer {token}", audience=AUDIENCE_UI)
    assert excinfo.value.code is ErrorCode.TOKEN_EXPIRED
