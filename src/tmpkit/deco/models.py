"""Domain models used by the high-level Deco client API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ipaddress import IPv4Address
from macaddress import EUI48


class Connection(Enum):
    HOST_2G = "host_2g"
    HOST_5G = "host_5g"
    HOST_6G = "host_6g"
    GUEST_2G = "guest_2g"
    GUEST_5G = "guest_5g"
    GUEST_6G = "guest_6g"
    IOT_2G = "iot_2g"
    IOT_5G = "iot_5g"
    IOT_6G = "iot_6g"
    WIRED = "wired"
    UNKNOWN = "unknown"


@dataclass
class Device:
    """A connected client device as reported by Deco AppV2."""

    type: Connection
    macaddr: EUI48
    ipaddr: IPv4Address
    hostname: str
    packets_sent: int | None = None
    packets_received: int | None = None
    down_speed: int | None = None
    up_speed: int | None = None
    tx_rate: int | None = None
    rx_rate: int | None = None
    online_time: float | None = None
    traffic_usage: int | None = None
    signal: int | None = None
    active: bool = True


@dataclass
class Firmware:
    """Firmware information reported by Deco AppV2."""

    hardware_version: str
    model: str
    firmware_version: str


@dataclass
class Status:
    """Overall router status (WAN/LAN, wifi enable flags, connected devices)."""

    wan_macaddr: EUI48 | None = None
    lan_macaddr: EUI48 | None = None
    wan_ipv4_addr: IPv4Address | None = None
    lan_ipv4_addr: IPv4Address | None = None
    wan_ipv4_gateway: IPv4Address | None = None
    wired_total: int = 0
    wifi_clients_total: int = 0
    guest_clients_total: int = 0
    iot_clients_total: int | None = None
    clients_total: int = 0
    guest_2g_enable: bool | None = None
    guest_5g_enable: bool | None = None
    guest_6g_enable: bool | None = None
    iot_2g_enable: bool | None = None
    iot_5g_enable: bool | None = None
    iot_6g_enable: bool | None = None
    wifi_2g_enable: bool | None = None
    wifi_5g_enable: bool | None = None
    wifi_6g_enable: bool | None = None
    wan_ipv4_uptime: int | None = None
    mem_usage: float | None = None
    cpu_usage: float | None = None
    conn_type: str | None = None
    devices: list[Device] = field(default_factory=list)


@dataclass
class IPv4Status:
    """IPv4 status details parsed from the Deco IPv4 GET payload."""

    wan_macaddr: EUI48 | None = None
    wan_ipv4_ipaddr: IPv4Address | None = None
    wan_ipv4_gateway: IPv4Address | None = None
    wan_ipv4_conntype: str = ""
    wan_ipv4_netmask: IPv4Address | None = None
    wan_ipv4_pridns: IPv4Address | None = None
    wan_ipv4_snddns: IPv4Address | None = None
    lan_macaddr: EUI48 | None = None
    lan_ipv4_ipaddr: IPv4Address | None = None
    lan_ipv4_dhcp_enable: bool | None = None
    lan_ipv4_netmask: IPv4Address | None = None
    remote: bool | None = None
