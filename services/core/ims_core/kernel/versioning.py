"""Optimistic concurrency for master data (LLD 12): "Master-data edits require If-Match with the
ETag row version: 428 if missing, 412 VERSION_CONFLICT on mismatch."

Reads return ``ETag: "<version>"``; edits send it back as ``If-Match``. The version is the row's
``version`` column, which every update increments.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import Depends, Request, Response

from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode

_IF_MATCH = re.compile(r'^\s*"(\d{1,10})"\s*$')


def etag(version: int) -> str:
    return f'"{version}"'


def set_etag(response: Response, version: int) -> None:
    response.headers["ETag"] = etag(version)


def expected_version(request: Request) -> int:
    """The row version the client last saw. A list of ETags or ``*`` is not a version."""
    header = request.headers.get("if-match")
    if header is None or not header.strip():
        raise DomainError(ErrorCode.PRECONDITION_REQUIRED)
    match = _IF_MATCH.fullmatch(header)
    if match is None:
        raise DomainError(ErrorCode.VERSION_CONFLICT, 'If-Match must be one ETag such as "3"')
    return int(match.group(1))


IfMatch = Annotated[int, Depends(expected_version)]
