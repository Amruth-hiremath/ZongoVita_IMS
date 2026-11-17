"""Credential endpoints of the UI API (LLD 6.2, 12: "auth/login, mfa, mfa/enrol, refresh, logout,
activate"). None takes an access token: each proves the caller another way, and the customer
comes from the Login Directory or a signed credential token (AD-21).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from ims_contracts.enums import LicenceModule
from ims_core.kernel.authn import AUDIENCE_UI
from ims_core.kernel.routes import ImsRouter, NoPermission, declare
from ims_core.modules.identity.schemas import (
    ActivateRequest,
    EnrolRequest,
    EnrolResponse,
    LoginRequest,
    LoginResponse,
    MfaRequest,
    RefreshRequest,
    SessionResponse,
)
from ims_core.modules.identity.service import IdentityService, SessionTokens

router = ImsRouter(prefix="/ui/v1/auth", audience=AUDIENCE_UI, module=LicenceModule.CORE, tags=["auth"])

#: Credentials must not be cached anywhere on the way (RFC 6749 section 5.1).
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def get_identity(request: Request) -> IdentityService:
    return request.app.state.identity


Identity = Annotated[IdentityService, Depends(get_identity)]


def _request_id(request: Request) -> str:
    return request.state.request_id


def _session(tokens: SessionTokens) -> JSONResponse:
    body = SessionResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        refresh_expires_at=tokens.refresh_expires_at,
        recovery_codes=tokens.recovery_codes,
    )
    return JSONResponse(body.model_dump(mode="json", exclude_none=True), headers=NO_STORE)


@router.post("/login", response_model=LoginResponse)
@declare(access=NoPermission(), read_only_ok=True)
async def login(body: LoginRequest, request: Request, identity: Identity) -> JSONResponse:
    """Password step. Every failure is the same 401, whatever the reason (LD-80)."""
    challenge = await identity.sign_in(body.login_identifier, body.password, request_id=_request_id(request))
    response = LoginResponse(
        status="mfa_enrolment_required" if challenge.enrolment_required else "mfa_required",
        challenge_token=challenge.challenge_token,
        challenge_expires_in=challenge.expires_in,
    )
    return JSONResponse(response.model_dump(mode="json"), headers=NO_STORE)


@router.post("/mfa/enrol", response_model=EnrolResponse)
@declare(access=NoPermission(), read_only_ok=True)
async def enrol(body: EnrolRequest, request: Request, identity: Identity) -> JSONResponse:
    """First sign-in: create the authenticator secret. Confirmed by the first code at /mfa."""
    enrolment = await identity.begin_enrolment(body.challenge_token, request_id=_request_id(request))
    response = EnrolResponse(secret=enrolment.secret, otpauth_uri=enrolment.otpauth_uri)
    return JSONResponse(response.model_dump(mode="json"), headers=NO_STORE)


@router.post("/mfa", response_model=SessionResponse)
@declare(access=NoPermission(), read_only_ok=True)
async def mfa(body: MfaRequest, request: Request, identity: Identity) -> JSONResponse:
    """Second factor: an authenticator code or a recovery code. Opens the session."""
    tokens = await identity.complete_mfa(
        body.challenge_token,
        code=body.code,
        recovery_code=body.recovery_code,
        request_id=_request_id(request),
    )
    return _session(tokens)


@router.post("/refresh", response_model=SessionResponse)
@declare(access=NoPermission(), read_only_ok=True)
async def refresh(body: RefreshRequest, request: Request, identity: Identity) -> JSONResponse:
    """Rotate the refresh token (LD-26); reusing an old one revokes the session."""
    return _session(await identity.refresh(body.refresh_token, request_id=_request_id(request)))


@router.post("/logout", status_code=204)
@declare(access=NoPermission(), read_only_ok=True)
async def logout(body: RefreshRequest, request: Request, identity: Identity) -> Response:
    await identity.sign_out(body.refresh_token, request_id=_request_id(request))
    return Response(status_code=204, headers=NO_STORE)


@router.post("/activate", status_code=204)
@declare(access=NoPermission(), read_only_ok=True)
async def activate(body: ActivateRequest, request: Request, identity: Identity) -> Response:
    """New user: set a password with the one-time activation code."""
    await identity.activate(
        body.login_identifier, body.activation_code, body.new_password, request_id=_request_id(request)
    )
    return Response(status_code=204, headers=NO_STORE)
