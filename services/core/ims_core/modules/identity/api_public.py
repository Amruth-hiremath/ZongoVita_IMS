"""Client-credentials grant of the public API (LLD 6.2, 12: POST /api/v1/oauth/token; AD-22).

Accepts the client credentials either in an HTTP Basic header or in the form body, as RFC 6749
section 2.3.1 allows. Tagged with the integration module: a customer without it has no public API.
"""

from __future__ import annotations

import base64
import binascii
import json
from urllib.parse import parse_qs, unquote_plus

from fastapi import Request
from fastapi.responses import JSONResponse

from ims_common.problem import DomainError
from ims_contracts.enums import LicenceModule
from ims_contracts.errors import ErrorCode, FieldError
from ims_core.kernel.authn import AUDIENCE_API
from ims_core.kernel.routes import ImsRouter, NoPermission, declare
from ims_core.modules.identity.api_ui import NO_STORE, Identity
from ims_core.modules.identity.schemas import ClientTokenResponse

router = ImsRouter(
    prefix="/api/v1/oauth", audience=AUDIENCE_API, module=LicenceModule.INTEGRATION, tags=["oauth"]
)

_MAX_BODY_BYTES = 4096


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(
        ErrorCode.VALIDATION_FAILED, status=400, errors=[FieldError(field=field, message=message)]
    )


async def _parameters(request: Request) -> dict[str, str]:
    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        raise _invalid("body", "request body is too large")
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "application/x-www-form-urlencoded":
        parsed = parse_qs(body.decode("utf-8", errors="strict"), keep_blank_values=True)
        if any(len(values) > 1 for values in parsed.values()):
            raise _invalid("body", "a parameter was given more than once")
        return {key: values[0] for key, values in parsed.items()}
    if content_type == "application/json":
        data = json.loads(body or b"{}")
        if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
            raise _invalid("body", "expected an object of strings")
        return data
    raise _invalid("content-type", "use application/x-www-form-urlencoded")


def _basic_credentials(request: Request) -> tuple[str, str] | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise _invalid("authorization", "malformed Basic credentials") from None
    client_id, sep, secret = decoded.partition(":")
    if not sep:
        raise _invalid("authorization", "malformed Basic credentials")
    return unquote_plus(client_id), unquote_plus(secret)


@router.post("/token", response_model=ClientTokenResponse)
@declare(access=NoPermission(), read_only_ok=True)
async def token(request: Request, identity: Identity) -> JSONResponse:
    try:
        params = await _parameters(request)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _invalid("body", "the body could not be read") from None
    if params.get("grant_type") != "client_credentials":
        raise _invalid("grant_type", "only client_credentials is supported")
    basic = _basic_credentials(request)
    client_id, secret = basic if basic else (params.get("client_id", ""), params.get("client_secret", ""))
    if not client_id or not secret:
        raise _invalid("client_id", "client_id and client_secret are required")
    issued = await identity.client_token(client_id, secret, request_id=request.state.request_id)
    body = ClientTokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)
    return JSONResponse(body.model_dump(mode="json"), headers=NO_STORE)
