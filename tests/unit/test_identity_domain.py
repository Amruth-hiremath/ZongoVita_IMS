"""Identity rules without I/O: TOTP, codes, passwords, identifiers, secret encryption (LLD 6.2)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from ims_common import auth_codes as domain
from ims_common.credentials import PasswordHasher, SecretBox
from ims_common.identifiers import (
    InvalidIdentifierError,
    key_from_secret,
    keyed_hash,
    new_key_secret,
    normalise_login_identifier,
)

RFC_SECRET = b"12345678901234567890"


# ------------------------------------------------------------------------------------- TOTP
@pytest.mark.parametrize(
    ("unix_time", "expected"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_totp_matches_the_rfc_6238_sha1_vectors(unix_time: int, expected: str) -> None:
    assert domain.totp_code(RFC_SECRET, unix_time // 30, digits=8) == expected


def test_a_code_is_accepted_one_step_either_side_and_not_beyond() -> None:
    secret = domain.new_totp_secret()
    now = datetime(2026, 11, 17, 10, 0, 15, tzinfo=UTC)
    step = domain.totp_step(now)
    for offset in (-1, 0, 1):
        assert (
            domain.match_totp(secret, domain.totp_code(secret, step + offset), now, last_used_step=None)
            == step + offset
        )
    for offset in (-2, 2):
        assert (
            domain.match_totp(secret, domain.totp_code(secret, step + offset), now, last_used_step=None)
            is None
        )


def test_a_step_is_accepted_only_once() -> None:
    """LD-79: a time step is accepted once per factor, so an observed code cannot be replayed."""
    secret = domain.new_totp_secret()
    now = datetime(2026, 11, 17, 10, 0, 0, tzinfo=UTC)
    step = domain.totp_step(now)
    code = domain.totp_code(secret, step)
    assert domain.match_totp(secret, code, now, last_used_step=step - 1) == step
    assert domain.match_totp(secret, code, now, last_used_step=step) is None
    # The previous step's code is refused once a later step has been used.
    earlier = domain.totp_code(secret, step - 1)
    assert domain.match_totp(secret, earlier, now, last_used_step=step) is None
    later = domain.totp_code(secret, step + 1)
    assert domain.match_totp(secret, later, now + timedelta(seconds=30), last_used_step=step) == step + 1


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 34 5", "١٢٣٤٥٦"])
def test_malformed_codes_never_match(code: str) -> None:
    assert domain.match_totp(domain.new_totp_secret(), code, datetime.now(UTC), last_used_step=None) is None


def test_otpauth_uri_carries_what_authenticator_apps_need() -> None:
    secret = domain.new_totp_secret()
    uri = urlparse(domain.otpauth_uri(secret, account="priya.sharma@zongovita.in", issuer="ZongoVita IMS"))
    assert (uri.scheme, uri.netloc) == ("otpauth", "totp")
    assert uri.path == "/ZongoVita%20IMS:priya.sharma@zongovita.in"
    query = parse_qs(uri.query)
    padded = query["secret"][0] + "=" * (-len(query["secret"][0]) % 8)
    assert base64.b32decode(padded) == secret
    assert (query["issuer"], query["digits"], query["period"], query["algorithm"]) == (
        ["ZongoVita IMS"],
        ["6"],
        ["30"],
        ["SHA1"],
    )


# ------------------------------------------------------------------------- one-time codes
def test_recovery_codes_are_ten_distinct_unambiguous_codes() -> None:
    codes = domain.new_recovery_codes()
    assert len(codes) == len(set(codes)) == 10
    for code in codes:
        assert len(code) == 11 and code[5] == "-"
        assert not set(code.replace("-", "")) & set("01ILO")


def test_codes_are_compared_regardless_of_case_and_spacing() -> None:
    code = domain.new_activation_code()
    variants = [code, code.lower(), code.replace("-", ""), " ".join(code), f"  {code}  "]
    assert {domain.hash_code(v) for v in variants} == {domain.hash_code(code)}
    assert domain.hash_code(code) != domain.hash_code(domain.new_activation_code())


# ------------------------------------------------------------------------------ passwords
@pytest.mark.parametrize(
    ("password", "problems"),
    [
        ("correct horse battery staple", []),
        ("short", ["must be at least 12 characters"]),
        ("Password1234", ["is too common"]),  # compared case-insensitively
        ("zongovita@123", ["is too common"]),
        ("x" * 257, ["must be at most 256 characters"]),
    ],
)
def test_password_policy(password: str, problems: list[str]) -> None:
    assert [p.message for p in domain.password_problems(password)] == problems


def test_common_password_list_holds_only_passwords_the_length_rule_lets_through() -> None:
    assert all(len(p) >= domain.PASSWORD_MIN_LENGTH for p in domain.common_passwords())


async def test_password_hasher_counts_every_verification_and_uses_the_dummy_for_nothing() -> None:
    hasher = PasswordHasher(time_cost=1, memory_kib=1024, parallelism=1)
    stored = await hasher.hash("correct horse battery staple")
    assert stored.startswith("$argon2id$")
    assert await hasher.verify(stored, "correct horse battery staple")
    assert not await hasher.verify(stored, "wrong horse battery staple")
    assert not await hasher.verify(None, "correct horse battery staple"), "no hash never matches"
    await hasher.burn("anything at all")
    assert hasher.verifications == 4
    assert not await hasher.verify("not-a-hash", "x")


# --------------------------------------------------------------------------- identifiers
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Priya.Sharma@ZongoVita.in", "priya.sharma@zongovita.in"),
        ("  priya.sharma@zongovita.in\t", "priya.sharma@zongovita.in"),
        ("\uff50\uff52\uff49\uff59\uff41@zongovita.in", "priya@zongovita.in"),  # full-width letters, NFKC
    ],
)
def test_identifiers_are_normalised(raw: str, expected: str) -> None:
    assert normalise_login_identifier(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "two words@x.in", "tab\tinside", "nul\x00", "a" * 255])
def test_invalid_identifiers_are_refused(raw: str) -> None:
    with pytest.raises(InvalidIdentifierError):
        normalise_login_identifier(raw)


def test_keyed_hashes_depend_on_key_and_normalised_identifier() -> None:
    pepper, lookup = key_from_secret(new_key_secret()), key_from_secret(new_key_secret())
    assert keyed_hash(pepper, "A@B.IN") == keyed_hash(pepper, " a@b.in ")
    assert keyed_hash(pepper, "a@b.in") != keyed_hash(lookup, "a@b.in"), (
        "the bundle hash reveals nothing of the pepper's"
    )
    assert len(keyed_hash(pepper, "a@b.in")) == 32
    with pytest.raises(ValueError, match="too short"):
        keyed_hash(b"short", "a@b.in")


# ------------------------------------------------------------------------- secret storage
def test_mfa_secrets_are_sealed_per_user_and_survive_key_rotation() -> None:
    ring = SecretBox.new_ring("mfa-1")
    box = SecretBox(ring)
    secret = domain.new_totp_secret()
    sealed, key_id = box.seal(secret, context="iam.mfa_factors:user-a")
    assert secret not in sealed
    assert box.open(sealed, key_id=key_id, context="iam.mfa_factors:user-a") == secret
    with pytest.raises(Exception):  # noqa: B017 - InvalidTag: the copy belongs to another user
        box.open(sealed, key_id=key_id, context="iam.mfa_factors:user-b")

    rotated = SecretBox({"current": "mfa-2", "keys": {**ring["keys"], **SecretBox.new_ring("mfa-2")["keys"]}})
    assert rotated.open(sealed, key_id="mfa-1", context="iam.mfa_factors:user-a") == secret
    _, new_key = rotated.seal(secret, context="iam.mfa_factors:user-a")
    assert new_key == "mfa-2"
