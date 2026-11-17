"""Application-generated UUIDv7 keys (LLD section 3, column rules).

UUIDv7 (RFC 9562) puts a millisecond timestamp in the high bits, so keys generated close in
time sit close in B-tree indexes. Within one process, IDs are strictly increasing: when several
are generated in the same millisecond the 12-bit ``rand_a`` field is used as a counter, and the
timestamp is nudged forward if the counter overflows or the clock steps back.
"""

from __future__ import annotations

import os
import threading
import time
from uuid import UUID

_lock = threading.Lock()
_last_ms = 0
_counter = 0

_MAX_COUNTER = 0xFFF


def uuid7() -> UUID:
    global _last_ms, _counter  # noqa: PLW0603 - process-wide monotonic state by design
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            _last_ms = now_ms
            _counter = int.from_bytes(os.urandom(2)) & 0x3FF  # leave headroom in the counter
        else:
            _counter += 1
            if _counter > _MAX_COUNTER:
                _last_ms += 1
                _counter = 0
        ms, counter = _last_ms, _counter
    rand_b = int.from_bytes(os.urandom(8)) & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= counter << 64
    value |= 0b10 << 62
    value |= rand_b
    return UUID(int=value)


def uuid7_timestamp_ms(value: UUID) -> int:
    """Millisecond Unix timestamp embedded in a UUIDv7."""
    return value.int >> 80
