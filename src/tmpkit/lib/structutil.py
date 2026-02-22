"""Small struct-unpack helpers with typed protocol error mapping."""

from __future__ import annotations

import struct
from typing import Any


def unpack_exact(
    struct_obj: struct.Struct, data: bytes, *, label: str, exc_type: type[Exception]
) -> tuple[Any, ...]:
    """Unpack using `struct_obj`, translating struct.error into `exc_type`.

    `struct.Struct.unpack()` requires an exact-size buffer; this helper keeps the
    caller's error type consistent across the library.
    """

    try:
        return struct_obj.unpack(data)
    except struct.error as e:
        raise exc_type(f"{label} must be {struct_obj.size} bytes") from e
