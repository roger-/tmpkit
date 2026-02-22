"""Adapters that map raw Deco client payloads into tmpkit device models."""

from __future__ import annotations

from typing import Any

from ipaddress import IPv4Address
from macaddress import EUI48

from tmpkit.deco.client_utils import client_signal_max, maybe_decode_name
from tmpkit.deco.macutil import normalize_mac48_str
from tmpkit.deco.models import Connection, Device


_CONNECTION_TYPE_MAP = {
    "wired": Connection.WIRED,
    "ethernet": Connection.WIRED,
    "lan": Connection.WIRED,
    "band2_4": Connection.HOST_2G,
    "band5": Connection.HOST_5G,
    "band5_1": Connection.HOST_5G,
    "band5_2": Connection.HOST_5G,
    "band6": Connection.HOST_6G,
    "band6_1": Connection.HOST_6G,
    "band6_2": Connection.HOST_6G,
}


def _parse_ipv4(value: object) -> IPv4Address:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return IPv4Address("0.0.0.0")
        try:
            return IPv4Address(text)
        except ValueError:
            pass
    return IPv4Address("0.0.0.0")


def _parse_mac(value: object) -> EUI48:
    norm = normalize_mac48_str(value)
    try:
        return EUI48(norm)
    except Exception:
        return EUI48("00:00:00:00:00:00")


def _maybe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            try:
                return int(s)
            except ValueError:
                return None
    return None


def _maybe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _map_connection_type(item: dict[str, Any]) -> Connection:
    linked = item.get("linked_device_info")
    if not isinstance(linked, dict):
        return Connection.UNKNOWN

    match linked.get("connection_type"):
        case [str() as conn0, *_]:
            return _CONNECTION_TYPE_MAP.get(conn0, Connection.UNKNOWN)
        case _:
            return Connection.UNKNOWN


def deco_client_to_device(item: object) -> Device | None:
    """Convert a single Deco AppV2 client dict to a tmpkit Device.

    Uses the 0-3 signal bars value from linked_device_info.signal_level (max across bands).
    """

    if not isinstance(item, dict):
        return None

    mac = normalize_mac48_str(item.get("mac"))
    ip = _parse_ipv4(item.get("ip"))
    name = maybe_decode_name(item.get("name"))

    conn = _map_connection_type(item)
    signal = client_signal_max(item)

    active = True
    online = item.get("online")
    if isinstance(online, bool):
        active = online

    dev = Device(conn, _parse_mac(mac), ip, name, signal=signal, active=active)

    for field_name in (
        "packets_sent",
        "packets_received",
        "tx_rate",
        "rx_rate",
        "traffic_usage",
        "up_speed",
        "down_speed",
    ):
        setattr(dev, field_name, _maybe_int(item.get(field_name)))

    dev.online_time = _maybe_float(item.get("online_time"))

    return dev


def deco_clients_to_devices(client_list: object) -> list[Device]:
    if not isinstance(client_list, list):
        return []

    return [dev for item in client_list if (dev := deco_client_to_device(item)) is not None]


def enrich_devices_with_client_list_speed(
    devices: list[Device], speed_payload: object
) -> None:
    """In-place enrichment using TMP_APPV2_OP_CLIENT_LIST_SPEED_GET.

    Expected payload shape:
      {"error_code": 0, "result": {"client_list_speed": [{"mac": "..", "up_speed": 1, "down_speed": 2, ...}, ...]}}
    """

    if not devices or not isinstance(speed_payload, dict):
        return
    result = speed_payload.get("result")
    if not isinstance(result, dict):
        return
    lst = result.get("client_list_speed")
    if not isinstance(lst, list):
        return

    by_mac: dict[EUI48, dict[str, Any]] = {}
    for item in lst:
        if not isinstance(item, dict):
            continue
        by_mac[_parse_mac(item.get("mac"))] = item

    int_fields = ("tx_rate", "rx_rate", "packets_sent", "packets_received", "traffic_usage")

    for dev in devices:
        payload = by_mac.get(dev.macaddr)
        if not isinstance(payload, dict):
            continue
        up = payload.get("up_speed")
        down = payload.get("down_speed")
        if isinstance(up, int):
            dev.up_speed = up
        if isinstance(down, int):
            dev.down_speed = down

        for field_name in int_fields:
            parsed = _maybe_int(payload.get(field_name))
            if parsed is not None:
                setattr(dev, field_name, parsed)

        online_time = _maybe_float(payload.get("online_time"))
        if online_time is not None:
            dev.online_time = online_time
