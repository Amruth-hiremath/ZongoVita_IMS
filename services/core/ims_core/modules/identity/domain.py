"""Pure identity rules: TOTP, password policy, one-time codes (LLD 6.2, section 16; LD-79).

No I/O here: everything is a function of its arguments, so it is tested directly.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from importlib import resources
from urllib.parse import quote, urlencode

# ------------------------------------------------------------------------------------- TOTP
TOTP_PERIOD_SECONDS = 30  # RFC 6238 time step (LD-79)
TOTP_DIGITS = 6
TOTP_WINDOW = 1  # one step of tolerance either side (LD-79)
TOTP_SECRET_BYTES = 20  # 160 bits, RFC 4226 recommendation for HMAC-SHA1


def new_totp_secret() -> bytes:
    return secrets.token_bytes(TOTP_SECRET_BYTES)


def totp_step(at: datetime) -> int:
    return int(at.timestamp()) // TOTP_PERIOD_SECONDS


def totp_code(secret: bytes, step: int, digits: int = TOTP_DIGITS) -> str:
    """HOTP (RFC 4226) of the time step with HMAC-SHA1, as RFC 6238 specifies by default."""
    digest = hmac.new(secret, step.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def match_totp(secret: bytes, code: str, at: datetime, *, last_used_step: int | None) -> int | None:
    """The time step ``code`` belongs to, or None.

    Accepts the current step and one either side, and never a step at or before the last one
    accepted for this factor, so a code cannot be replayed (LD-79).
    """
    code = code.strip().replace(" ", "")
    # ASCII digits only: str.isdigit() also accepts other scripts' digits.
    if len(code) != TOTP_DIGITS or not (code.isascii() and code.isdigit()):
        return None
    now = totp_step(at)
    matched = None
    for step in range(now - TOTP_WINDOW, now + TOTP_WINDOW + 1):
        # Compare every candidate so the time taken does not depend on which one matches.
        if hmac.compare_digest(totp_code(secret, step), code) and (
            last_used_step is None or step > last_used_step
        ):
            matched = step
    return matched


def base32_secret(secret: bytes) -> str:
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def otpauth_uri(secret: bytes, *, account: str, issuer: str) -> str:
    """Key URI for authenticator apps (the de facto Google Authenticator format)."""
    label = quote(f"{issuer}:{account}", safe="@:")
    query = urlencode(
        {
            "secret": base32_secret(secret),
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": TOTP_DIGITS,
            "period": TOTP_PERIOD_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


# --------------------------------------------------------------------------- one-time codes
RECOVERY_CODE_COUNT = 10  # LD-79
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
RECOVERY_CODE_LENGTH = 10  # about 49 bits each
ACTIVATION_CODE_LENGTH = 12  # about 59 bits


def _random_code(length: int) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def _group(code: str) -> str:
    half = len(code) // 2
    return f"{code[:half]}-{code[half:]}"


def normalise_code(value: str) -> str:
    """Codes are shown grouped ("ABCDE-FGHJK"); users may type them in any case or spacing."""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def hash_code(value: str) -> bytes:
    """SHA-256 of a normalised one-time code. Codes are random and long enough that a plain hash,
    not a password hash, is the right protection."""
    return hashlib.sha256(normalise_code(value).encode("ascii")).digest()


def new_recovery_codes() -> list[str]:
    return [_group(_random_code(RECOVERY_CODE_LENGTH)) for _ in range(RECOVERY_CODE_COUNT)]


def new_activation_code() -> str:
    return _group(_random_code(ACTIVATION_CODE_LENGTH))


# ------------------------------------------------------------------------- client secrets
CLIENT_SECRET_BYTES = 32  # LLD section 16: "32-byte secrets shown once, stored hashed"


def new_client_secret() -> str:
    return secrets.token_urlsafe(CLIENT_SECRET_BYTES)


def hash_client_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


# ---------------------------------------------------------------------------- passwords
PASSWORD_MIN_LENGTH = 12  # LLD section 16
PASSWORD_MAX_LENGTH = 256  # bounds the cost of hashing an attacker-supplied value


@cache
def common_passwords() -> frozenset[str]:
    text = resources.files(__package__).joinpath("common_passwords.txt").read_text(encoding="utf-8")
    return frozenset(
        line.strip().lower() for line in text.splitlines() if line.strip() and not line.startswith("#")
    )


@dataclass(frozen=True)
class PasswordProblem:
    message: str


def password_problems(password: str) -> list[PasswordProblem]:
    """LLD section 16: at least 12 characters, checked against a common-password list."""
    problems: list[PasswordProblem] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(PasswordProblem(f"must be at least {PASSWORD_MIN_LENGTH} characters"))
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(PasswordProblem(f"must be at most {PASSWORD_MAX_LENGTH} characters"))
    if password.strip().lower() in common_passwords():
        problems.append(PasswordProblem("is too common"))
    return problems
