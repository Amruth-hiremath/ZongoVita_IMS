"""Cursor pagination for list endpoints (LLD 12: "limit 50, maximum 200, next_cursor").

Lists are ordered by id (UUIDv7, so creation order) and the cursor is the last id of the page.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode, FieldError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _cursor(cursor: Annotated[str | None, Query(max_length=64)] = None) -> UUID | None:
    if cursor is None:
        return None
    try:
        return UUID(cursor)
    except ValueError:
        raise DomainError(
            ErrorCode.VALIDATION_FAILED, errors=[FieldError(field="cursor", message="is not a valid cursor")]
        ) from None


def _limit(limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT) -> int:
    return limit


After = Annotated[UUID | None, Depends(_cursor)]
Limit = Annotated[int, Depends(_limit)]


def page[T](rows: Sequence[T], limit: int, id_of: Callable[[T], UUID]) -> tuple[list[T], str | None]:
    """Rows were read with ``limit + 1``: the extra row only says there is a next page."""
    items = list(rows[:limit])
    more = len(rows) > limit
    return items, (str(id_of(items[-1])) if more and items else None)
