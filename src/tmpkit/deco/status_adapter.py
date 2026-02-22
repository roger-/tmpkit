"""High-level status/firmware parsers and request helpers for Deco AppV2."""

from __future__ import annotations

import logging
from ipaddress import IPv4Address
from typing import Any

from macaddress import EUI48

from tmpkit.deco.device_adapter import (
    deco_clients_to_devices,
    enrich_devices_with_client_list_speed,
)
from tmpkit.deco.client_utils import maybe_decode_name
from tmpkit.deco.macutil import normalize_mac48_str
from tmpkit.deco.models import Connection, Device, Firmware, IPv4Status, Status
from tmpkit.deco.opcodes import DecoAppV2Opcode
from tmpkit.lib.appv2 import TmpAppV2Session

logger = logging.getLogger(__name__)

_ZERO_IPV4 = IPv4Address("0.0.0.0")


def _parse_ipv4(value: object) -> IPv4Address:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return _ZERO_IPV4
        try:
            return IPv4Address(text)
        except ValueError:
            pass
    return _ZERO_IPV4


def _result_dict(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _dig(d: object, *path: str) -> object | None:
    cur: object = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _maybe_bool(value: object) -> bool | None:
    match value:
        case bool() as b:
            return b
        case int() as i if i in (0, 1):
            return bool(i)
        case str() as s:
            normalized = s.strip().lower()
            match normalized:
                case "true" | "1" | "yes" | "on" | "enabled":
                    return True
                case "false" | "0" | "no" | "off" | "disabled":
                    return False
                case _:
                    return None
        case _:
            return None


def enrich_status_from_ipv4_get(status: Status, payload: object) -> None:
    """Best-effort WAN/LAN IPv4 and MAC extraction from TMP_APPV2_OP_IPV4_GET."""

    result = _result_dict(payload)

    wan_mac = _dig(result, "wan", "ip_info", "mac")
    lan_mac = _dig(result, "lan", "ip_info", "mac")

    wan_ip = _dig(result, "wan", "ip_info", "ip")
    lan_ip = _dig(result, "lan", "ip_info", "ip")
    wan_gw = _dig(result, "wan", "ip_info", "gateway")

    conn = _dig(result, "wan", "dial_type")
    if status.conn_type is None and isinstance(conn, str) and conn.strip():
        status.conn_type = conn.strip()

    if isinstance(wan_mac, str) and wan_mac.strip():
        norm = normalize_mac48_str(wan_mac)
        if norm != "00:00:00:00:00:00":
            status.wan_macaddr = EUI48(norm)
    if isinstance(lan_mac, str) and lan_mac.strip():
        norm = normalize_mac48_str(lan_mac)
        if norm != "00:00:00:00:00:00":
            status.lan_macaddr = EUI48(norm)

    if isinstance(wan_ip, str) and wan_ip.strip():
        ip = _parse_ipv4(wan_ip)
        if ip != _ZERO_IPV4:
            status.wan_ipv4_addr = ip
    if isinstance(lan_ip, str) and lan_ip.strip():
        ip = _parse_ipv4(lan_ip)
        if ip != _ZERO_IPV4:
            status.lan_ipv4_addr = ip
    if isinstance(wan_gw, str) and wan_gw.strip():
        ip = _parse_ipv4(wan_gw)
        if ip != _ZERO_IPV4:
            status.wan_ipv4_gateway = ip


def enrich_status_from_internet_get(status: Status, payload: object) -> None:
    """Best-effort connection type and uptime extraction from TMP_APPV2_OP_INTERNET_GET."""

    result = _result_dict(payload)

    conn = result.get("dial_type")
    if status.conn_type is None and isinstance(conn, str) and conn.strip():
        status.conn_type = conn.strip()

    uptime = result.get("wan_uptime")
    match uptime:
        case int() as value:
            status.wan_ipv4_uptime = value
        case str() as raw if raw.strip().isdigit():
            status.wan_ipv4_uptime = int(raw.strip())


def enrich_status_from_wireless_get(status: Status, payload: object) -> None:
    """Best-effort wifi enable flags extraction from TMP_APPV2_OP_WIRELESS_GET."""

    result = _result_dict(payload)

    # Expected-ish shape:
    # band2_4: {host:{enable:bool}, guest:{enable:bool}}
    # band5_1: {host:{enable:bool}, guest:{enable:bool}}
    # band6: {host:{enable:bool}, guest:{enable:bool}}
    status.wifi_2g_enable = _maybe_bool(_dig(result, "band2_4", "host", "enable"))
    status.guest_2g_enable = _maybe_bool(_dig(result, "band2_4", "guest", "enable"))

    status.wifi_5g_enable = _maybe_bool(_dig(result, "band5_1", "host", "enable"))
    status.guest_5g_enable = _maybe_bool(_dig(result, "band5_1", "guest", "enable"))

    status.wifi_6g_enable = _maybe_bool(_dig(result, "band6", "host", "enable"))
    status.guest_6g_enable = _maybe_bool(_dig(result, "band6", "guest", "enable"))


def firmware_from_device_list_payload(payload: object) -> Firmware:
    """Parse Firmware from TMP_APPV2_OP_DEVICE_LIST_GET response."""

    device_list = _result_dict(payload).get("device_list")
    if not isinstance(device_list, list) or not device_list:
        return Firmware("", "", "")

    master: dict[str, Any] | None = None
    for item in device_list:
        if isinstance(item, dict) and item.get("role") == "master":
            master = item
            break

    chosen: dict[str, Any] = (
        master
        if master is not None
        else (device_list[0] if isinstance(device_list[0], dict) else {})
    )

    hardware = chosen.get("hardware_ver")
    model = chosen.get("device_model")
    software = chosen.get("software_ver")

    return Firmware(
        hardware_version=str(hardware) if hardware is not None else "",
        model=str(model) if model is not None else "",
        firmware_version=str(software) if software is not None else "",
    )


def node_devices_from_device_list_payload(
    payload: object, *, include_master: bool = False
) -> list[Device]:
    """Parse mesh nodes as Device entries from TMP_APPV2_OP_DEVICE_LIST_GET.

    This is used to surface slave nodes in Status.devices when requested.
    """

    device_list = _result_dict(payload).get("device_list")
    if not isinstance(device_list, list) or not device_list:
        return []

    out: list[Device] = []
    for item in device_list:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        match role:
            case "master" if not include_master:
                continue
            case "master" | "slave":
                pass
            case _:
                continue

        mac_raw = item.get("mac")
        ip_raw = item.get("ip")
        if not isinstance(mac_raw, str) or not mac_raw.strip():
            continue
        if not isinstance(ip_raw, str) or not ip_raw.strip():
            continue

        mac_norm = normalize_mac48_str(mac_raw)
        if mac_norm == "00:00:00:00:00:00":
            continue

        ip = _parse_ipv4(ip_raw)
        if ip == IPv4Address("0.0.0.0"):
            continue

        nickname = maybe_decode_name(
            item.get("custom_nickname") or item.get("nickname")
        )
        match role:
            case "slave":
                hostname = f"node:{nickname}" if nickname else "node:slave"
            case _:
                hostname = f"node:{nickname}" if nickname else "node:master"

        signal_level = item.get("signal_level")
        node_signal: int | None = None
        if isinstance(signal_level, dict):
            vals = [
                level
                for level in signal_level.values()
                if isinstance(level, int)
            ]
            vals.extend(
                int(level)
                for level in signal_level.values()
                if isinstance(level, str) and level.isdigit()
            )
            if vals:
                node_signal = max(vals)

        group_status = item.get("group_status")
        inet_status = item.get("inet_status")
        active = True
        if isinstance(group_status, str) and group_status.strip().lower() not in {
            "connected",
            "online",
        }:
            active = False
        if isinstance(inet_status, str) and inet_status.strip().lower() not in {
            "online"
        }:
            # Some nodes may still be connected but without internet; keep group_status as primary.
            pass

        # Nodes are not normal clients, but we can still expose a useful
        # connection type based on the backhaul info.
        node_conn = item.get("connection_type")
        node_type = Connection.UNKNOWN
        match node_conn:
            case list() as values:
                bands = {str(x) for x in values if isinstance(x, str)}
                if "band5" in bands:
                    node_type = Connection.HOST_5G
                elif "band2_4" in bands:
                    node_type = Connection.HOST_2G

        dev = Device(
            type=node_type,
            macaddr=EUI48(mac_norm),
            ipaddr=ip,
            hostname=hostname,
            signal=node_signal,
            active=active,
        )
        out.append(dev)

    return out


def recompute_status_counts(status: Status) -> None:
    """Recompute totals from Status.devices.

    This is used when we optionally append non-client devices (mesh nodes).
    """

    wired_total = 0
    wifi_clients_total = 0
    guest_clients_total = 0
    iot_clients_total: int | None = None

    for dev in status.devices:
        if not getattr(dev, "active", False):
            continue

        dtype = getattr(dev, "type", None)
        match dtype:
            case Connection.WIRED:
                wired_total += 1
            case Connection.GUEST_2G | Connection.GUEST_5G | Connection.GUEST_6G:
                guest_clients_total += 1
            case Connection.IOT_2G | Connection.IOT_5G | Connection.IOT_6G:
                if iot_clients_total is None:
                    iot_clients_total = 0
                iot_clients_total += 1
            case _:
                # Treat unknown/host as host-wifi.
                wifi_clients_total += 1

    status.wired_total = wired_total
    status.wifi_clients_total = wifi_clients_total
    status.guest_clients_total = guest_clients_total
    status.iot_clients_total = iot_clients_total
    status.clients_total = (
        wired_total
        + wifi_clients_total
        + guest_clients_total
        + (0 if iot_clients_total is None else iot_clients_total)
    )


def leases_by_mac_from_payload(payload: object) -> dict[EUI48, IPv4Address]:
    """Parse MAC->IP leases from TMP_APPV2_OP_CLIENT_LEASE_GET response.

    The APK models this as:
      {"error_code":0,"result":{"client_lease":[{"ip":"...","mac":"..."}, ...]}}
    """

    raw = _result_dict(payload).get("client_lease")
    if raw is None:
        return {}

    if isinstance(raw, list):
        items: list[object] = raw
    elif isinstance(raw, dict):
        # Some firmwares may return a map keyed by IP.
        items = list(raw.values())
    else:
        return {}

    out: dict[EUI48, IPv4Address] = {}
    for item in items:
        if not isinstance(item, dict):
            continue

        mac = normalize_mac48_str(item.get("mac"))
        ip = _parse_ipv4(item.get("ip"))

        if mac == "00:00:00:00:00:00":
            continue
        if ip == _ZERO_IPV4:
            continue

        out[EUI48(mac)] = ip

    return out


def enrich_devices_with_leases(devices: list[Any], lease_payload: object) -> None:
    """Best-effort in-place IP enrichment for Devices using lease table."""

    if not devices:
        return
    leases = leases_by_mac_from_payload(lease_payload)
    if not leases:
        return

    for dev in devices:
        mac = getattr(dev, "macaddr", None)
        ip = getattr(dev, "ipaddr", None)
        if not isinstance(mac, EUI48) or not isinstance(ip, IPv4Address):
            continue

        if ip != _ZERO_IPV4:
            continue

        leased = leases.get(mac)
        if leased is None:
            continue
        try:
            dev.ipaddr = leased
        except Exception:
            pass


def status_from_client_payloads(
    *,
    client_list_payload: object,
    speed_payload: object | None = None,
    lease_payload: object | None = None,
) -> Status:
    """Build a Status from AppV2 client payloads."""

    result = _result_dict(client_list_payload)
    client_list = result.get("client_list")

    devices = deco_clients_to_devices(
        client_list if isinstance(client_list, list) else []
    )

    if speed_payload is not None:
        enrich_devices_with_client_list_speed(devices, speed_payload)

    if lease_payload is not None:
        enrich_devices_with_leases(devices, lease_payload)

    # Expose connected devices only.
    connected = [d for d in devices if d.active]

    status = Status()
    status.devices = connected
    recompute_status_counts(status)

    return status


def deco_get_firmware(
    session: TmpAppV2Session, *, timeout_seconds: float = 8.0
) -> Firmware:
    logger.debug("Deco request: DEVICE_LIST_GET (firmware)")
    payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_DEVICE_LIST_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    return firmware_from_device_list_payload(payload)


def deco_get_status(
    session: TmpAppV2Session,
    *,
    timeout_seconds: float = 8.0,
    include_nodes: bool = False,
) -> Status:
    # Status-level info (WAN/LAN ip/mac, wifi enables, conn_type). All are read-only GET.
    status = Status()
    logger.debug("Deco request: IPV4_GET (status)")
    ipv4_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_IPV4_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    enrich_status_from_ipv4_get(status, ipv4_payload)
    logger.debug("Deco request: WIRELESS_GET (status)")
    wireless_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_WIRELESS_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    enrich_status_from_wireless_get(status, wireless_payload)
    logger.debug("Deco request: INTERNET_GET (status)")
    internet_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_INTERNET_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    enrich_status_from_internet_get(status, internet_payload)
    logger.debug("Deco request: CLIENT_LIST_GET (status)")
    client_list_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    logger.debug("Deco request: CLIENT_LIST_SPEED_GET (status)")
    speed_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_SPEED_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    logger.debug("Deco request: CLIENT_LEASE_GET (status)")
    lease_payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LEASE_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )

    client_status = status_from_client_payloads(
        client_list_payload=client_list_payload,
        speed_payload=speed_payload,
        lease_payload=lease_payload,
    )

    # Merge client-derived fields into the status object we already enriched.
    status.devices = client_status.devices
    for field_name in (
        "wired_total",
        "wifi_clients_total",
        "guest_clients_total",
        "iot_clients_total",
        "clients_total",
    ):
        setattr(status, field_name, getattr(client_status, field_name))

    if include_nodes:
        logger.debug("Deco request: DEVICE_LIST_GET (nodes)")
        device_list_payload = session.request_json(
            op_code=DecoAppV2Opcode.TMP_APPV2_OP_DEVICE_LIST_GET,
            params=None,
            timeout_seconds=float(timeout_seconds),
        )
        node_devices = node_devices_from_device_list_payload(
            device_list_payload, include_master=False
        )
        if node_devices:
            existing = {
                d.macaddr
                for d in status.devices
                if isinstance(getattr(d, "macaddr", None), EUI48)
            }
            for nd in node_devices:
                if nd.macaddr in existing:
                    continue
                status.devices.append(nd)
            recompute_status_counts(status)

    return status


def ipv4_status_from_ipv4_get_payload(payload: object) -> IPv4Status:
    """Parse IPv4Status from TMP_APPV2_OP_IPV4_GET."""

    result = _result_dict(payload)

    wan_ip_info = _dig(result, "wan", "ip_info")
    lan_ip_info = _dig(result, "lan", "ip_info")

    def mac_from(obj: object, key: str) -> EUI48 | None:
        if not isinstance(obj, dict):
            return None
        raw = obj.get(key)
        if not isinstance(raw, str) or not raw.strip():
            return None
        norm = normalize_mac48_str(raw)
        if norm == "00:00:00:00:00:00":
            return None
        return EUI48(norm)

    def ipv4_from(obj: object, key: str) -> IPv4Address | None:
        if not isinstance(obj, dict):
            return None
        raw = obj.get(key)
        if not isinstance(raw, str) or not raw.strip():
            return None
        ip = _parse_ipv4(raw)
        return None if ip == _ZERO_IPV4 else ip

    conntype = _dig(result, "wan", "dial_type")

    st = IPv4Status()
    st.wan_macaddr = mac_from(wan_ip_info, "mac")
    st.wan_ipv4_ipaddr = ipv4_from(wan_ip_info, "ip")
    st.wan_ipv4_gateway = ipv4_from(wan_ip_info, "gateway")
    st.wan_ipv4_netmask = ipv4_from(wan_ip_info, "mask")
    st.wan_ipv4_pridns = ipv4_from(wan_ip_info, "dns1")
    st.wan_ipv4_snddns = ipv4_from(wan_ip_info, "dns2")
    st.wan_ipv4_conntype = str(conntype).strip() if isinstance(conntype, str) else ""

    st.lan_macaddr = mac_from(lan_ip_info, "mac")
    st.lan_ipv4_ipaddr = ipv4_from(lan_ip_info, "ip")
    st.lan_ipv4_netmask = ipv4_from(lan_ip_info, "mask")

    return st


def deco_get_ipv4_status(
    session: TmpAppV2Session, *, timeout_seconds: float = 8.0
) -> IPv4Status:
    logger.debug("Deco request: IPV4_GET (ipv4_status)")
    payload = session.request_json(
        op_code=DecoAppV2Opcode.TMP_APPV2_OP_IPV4_GET,
        params=None,
        timeout_seconds=float(timeout_seconds),
    )
    return ipv4_status_from_ipv4_get_payload(payload)
