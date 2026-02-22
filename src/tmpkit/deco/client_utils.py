"""Utilities for parsing and normalizing Deco client-list payload fields."""

from __future__ import annotations

import base64
import binascii
from typing import Any


def is_connected_client(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    for key in ("online", "is_online", "connected", "isConnected"):
        value = item.get(key)
        if isinstance(value, bool):
            return value
    status = item.get("status")
    if isinstance(status, str) and status.lower() in {"online", "connected"}:
        return True
    return False


def maybe_decode_name(value: object) -> str:
    if not isinstance(value, str):
        return "(unknown)"
    s = value.strip()
    if not s:
        return "(unknown)"

    # Heuristic: some firmwares return the alias/name Base64-encoded.
    if not all(ch.isalnum() or ch in "+/=" for ch in s):
        return value

    padded = s + "=" * ((4 - (len(s) % 4)) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
        decoded = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return value

    if not decoded or not all(ch.isprintable() or ch.isspace() for ch in decoded):
        return value
    return decoded


def client_rssi_level(item: object) -> str | None:
    """Best-effort extraction of RSSI/signal info for a client.

    For Deco TMP/AppV2 v1.10.5, connected clients may include:
      linked_device_info: { connection_type: ["band2_4"], signal_level: {"band2_4": 3, "band5": 0} }

    Values are *signal levels* (typically 0-3), not necessarily dBm RSSI.
    """

    if not isinstance(item, dict):
        return None

    linked = item.get("linked_device_info")
    if not isinstance(linked, dict):
        return None

    signal = linked.get("signal_level")
    if not isinstance(signal, dict):
        return None

    # Prefer the currently used connection type (band) if provided.
    conn = linked.get("connection_type")
    if isinstance(conn, list) and conn:
        band = conn[0]
        if isinstance(band, str):
            level = signal.get(band)
            if isinstance(level, int):
                return f"{band}:{level}"

    parts: list[str] = []
    for band, level in sorted(signal.items()):
        if isinstance(band, str) and isinstance(level, int):
            parts.append(f"{band}:{level}")

    return ",".join(parts) if parts else None


def client_signal_levels(item: object) -> dict[str, int] | None:
    """Return raw per-band signal levels (typically 0-3) for a connected client.

    Source field:
      linked_device_info.signal_level

    Notes:
    - Client responses usually use ints.
    - Some device/node responses use strings; we accept both here.
    """

    if not isinstance(item, dict):
        return None

    linked = item.get("linked_device_info")
    if not isinstance(linked, dict):
        return None

    signal = linked.get("signal_level")
    if not isinstance(signal, dict):
        return None

    out: dict[str, int] = {}
    for band, level in signal.items():
        if not isinstance(band, str):
            continue
        if isinstance(level, int):
            out[band] = level
        elif isinstance(level, str) and level.isdigit():
            out[band] = int(level)

    return out or None


def client_signal_max(item: object) -> int | None:
    levels = client_signal_levels(item)
    if not levels:
        return None
    return max(levels.values())


def extract_signal_fields(item: object) -> dict[str, Any]:
    """Extract all signal-ish fields from a client object.

    Today, Deco client objects typically only include signal info at:
      linked_device_info.signal_level

    This helper is intentionally generic (recursive scan) so we can print
    everything available without hardcoding a schema.
    """

    if not isinstance(item, dict):
        return {}

    found: dict[str, Any] = {}
    interesting = ("signal", "rssi", "snr")

    linked = item.get("linked_device_info")
    if isinstance(linked, dict):
        if "device_id" in linked:
            found["linked_device_info.device_id"] = linked.get("device_id")
        if "connection_type" in linked:
            found["linked_device_info.connection_type"] = linked.get("connection_type")

    def walk(o: object, path: str = "") -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                key = str(k)
                next_path = f"{path}.{key}" if path else key
                lk = key.lower()
                if any(token in lk for token in interesting):
                    found[next_path] = v
                walk(v, next_path)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(item)
    return found
