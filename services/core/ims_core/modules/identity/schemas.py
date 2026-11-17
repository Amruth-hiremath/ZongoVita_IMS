"""Request and response bodies of the identity endpoints (LLD 6.2, section 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    """Password accepted; the second factor is next. The challenge token is single use."""

    status: Literal["mfa_required", "mfa_enrolment_required"]
    challenge_token: str
    challenge_expires_in: int


class EnrolRequest(_Body):
    challenge_token: str = Field(min_length=1, max_length=4096)


class EnrolResponse(BaseModel):
    """The new TOTP secret, shown once: as text and as a key URI for a QR code."""

    secret: str
    otpauth_uri: str


class MfaRequest(_Body):
    challenge_token: str = Field(min_length=1, max_length=4096)
    code: str | None = Field(default=None, max_length=16)
    recovery_code: str | None = Field(default=None, max_length=32)


class SessionResponse(BaseModel):
    """Tokens for the BFF, which keeps them in HttpOnly cookies (LD-49). ``recovery_codes`` is
    present once, when MFA has just been set up."""

    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 - an OAuth token type, not a secret
    expires_in: int
    refresh_expires_at: datetime
    recovery_codes: list[str] | None = None


class RefreshRequest(_Body):
    refresh_token: str = Field(min_length=1, max_length=4096)


class ActivateRequest(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    activation_code: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=1, max_length=256)


class ClientTokenResponse(BaseModel):
    """RFC 6749 section 5.1 access token response."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 - an OAuth token type, not a secret
    expires_in: int
