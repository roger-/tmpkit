from __future__ import annotations

import unittest

from ipaddress import IPv4Address
from macaddress import EUI48

from tmpkit.deco.status_adapter import (
    enrich_status_from_internet_get,
    enrich_status_from_ipv4_get,
    enrich_status_from_wireless_get,
    firmware_from_device_list_payload,
    ipv4_status_from_ipv4_get_payload,
    leases_by_mac_from_payload,
    status_from_client_payloads,
)
from tmpkit.deco.models import IPv4Status, Status


class TestDecoStatusAdapter(unittest.TestCase):
    def test_firmware_from_device_list_prefers_master(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "device_list": [
                    {
                        "role": "slave",
                        "hardware_ver": "0.9",
                        "device_model": "X5000",
                        "software_ver": "0.0.0",
                    },
                    {
                        "role": "master",
                        "hardware_ver": "1.0",
                        "device_model": "X5000",
                        "software_ver": "1.4.0 Build 20241212 Rel. 48194",
                    },
                ]
            },
        }

        fw = firmware_from_device_list_payload(payload)
        self.assertEqual(fw.hardware_version, "1.0")
        self.assertEqual(fw.model, "X5000")
        self.assertIn("1.4.0", fw.firmware_version)

    def test_leases_by_mac_from_payload(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "client_lease": [
                    {"ip": "198.51.100.50", "mac": "02-00-00-00-00-01"},
                    {"ip": "0.0.0.0", "mac": "02:00:00:00:00:02"},
                ]
            },
        }

        leases = leases_by_mac_from_payload(payload)
        self.assertEqual(
            leases[EUI48("02:00:00:00:00:01")], IPv4Address("198.51.100.50")
        )
        self.assertNotIn(EUI48("02:00:00:00:00:02"), leases)

    def test_leases_by_mac_from_payload_dict_shape(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "client_lease": {
                    "198.51.100.51": {
                        "ip": "198.51.100.51",
                        "mac": "02:00:00:00:00:11",
                    },
                }
            },
        }
        leases = leases_by_mac_from_payload(payload)
        self.assertEqual(
            leases[EUI48("02:00:00:00:00:11")], IPv4Address("198.51.100.51")
        )

    def test_status_from_client_payloads_counts_and_enriches(self) -> None:
        client_list_payload = {
            "error_code": 0,
            "result": {
                "client_list": [
                    {
                        "name": "RGV2aWNlMQ==",  # Device1
                        "mac": "02-00-00-00-00-01",
                        "ip": "0.0.0.0",
                        "online": True,
                        "linked_device_info": {
                            "connection_type": ["band2_4"],
                            "signal_level": {"band2_4": 3, "band5": 0},
                        },
                    },
                    {
                        "name": "RGV2aWNlMg==",  # Device2
                        "mac": "02:00:00:00:00:02",
                        "ip": "198.51.100.60",
                        "online": True,
                        "linked_device_info": {
                            "connection_type": ["wired"],
                        },
                    },
                    {
                        "name": "T2ZmbGluZQ==",  # Offline
                        "mac": "02:00:00:00:00:03",
                        "ip": "198.51.100.70",
                        "online": False,
                        "linked_device_info": {
                            "connection_type": ["band2_4"],
                        },
                    },
                ]
            },
        }

        speed_payload = {
            "error_code": 0,
            "result": {
                "client_list_speed": [
                    {"mac": "02-00-00-00-00-01", "up_speed": 10, "down_speed": 20},
                ]
            },
        }

        lease_payload = {
            "error_code": 0,
            "result": {
                "client_lease": [
                    {"ip": "198.51.100.50", "mac": "02-00-00-00-00-01"},
                ]
            },
        }

        status = status_from_client_payloads(
            client_list_payload=client_list_payload,
            speed_payload=speed_payload,
            lease_payload=lease_payload,
        )

        self.assertEqual(status.clients_total, 2)
        self.assertEqual(status.wired_total, 1)
        self.assertEqual(status.wifi_clients_total, 1)
        self.assertEqual(len(status.devices), 2)

        # Lease enrichment should fill missing IP.
        dev1 = next(
            d for d in status.devices if d.macaddr == EUI48("02:00:00:00:00:01")
        )
        self.assertEqual(dev1.ipaddr, IPv4Address("198.51.100.50"))
        self.assertEqual(dev1.up_speed, 10)
        self.assertEqual(dev1.down_speed, 20)

    def test_enrich_status_from_ipv4_get(self) -> None:
        status = Status()
        payload = {
            "error_code": 0,
            "result": {
                "wan": {
                    "dial_type": "dynamic_ip",
                    "ip_info": {
                        "mac": "02-00-00-00-00-01",
                        "ip": "1.2.3.4",
                        "gateway": "1.2.3.1",
                    },
                },
                "lan": {
                    "ip_info": {"mac": "02:00:00:00:00:02", "ip": "198.51.100.1"}
                },
            },
        }
        enrich_status_from_ipv4_get(status, payload)
        self.assertEqual(status.conn_type, "dynamic_ip")
        self.assertEqual(status.wan_macaddr, EUI48("02:00:00:00:00:01"))
        self.assertEqual(status.lan_macaddr, EUI48("02:00:00:00:00:02"))
        self.assertEqual(status.wan_ipv4_addr, IPv4Address("1.2.3.4"))
        self.assertEqual(status.lan_ipv4_addr, IPv4Address("198.51.100.1"))
        self.assertEqual(status.wan_ipv4_gateway, IPv4Address("1.2.3.1"))

    def test_ipv4_status_from_ipv4_get_payload(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "wan": {
                    "dial_type": "dynamic_ip",
                    "ip_info": {
                        "mac": "02-00-00-00-00-01",
                        "ip": "1.2.3.4",
                        "gateway": "1.2.3.1",
                        "mask": "255.255.255.0",
                        "dns1": "8.8.8.8",
                        "dns2": "1.1.1.1",
                    },
                },
                "lan": {
                    "ip_info": {
                        "mac": "02:00:00:00:00:02",
                        "ip": "198.51.100.1",
                        "mask": "255.255.255.0",
                    }
                },
            },
        }
        st = ipv4_status_from_ipv4_get_payload(payload)
        self.assertIsInstance(st, IPv4Status)
        self.assertEqual(st.wan_macaddr, EUI48("02:00:00:00:00:01"))
        self.assertEqual(st.wan_ipv4_ipaddr, IPv4Address("1.2.3.4"))
        self.assertEqual(st.wan_ipv4_gateway, IPv4Address("1.2.3.1"))
        self.assertEqual(st.wan_ipv4_netmask, IPv4Address("255.255.255.0"))
        self.assertEqual(st.wan_ipv4_pridns, IPv4Address("8.8.8.8"))
        self.assertEqual(st.wan_ipv4_snddns, IPv4Address("1.1.1.1"))
        self.assertEqual(st.wan_ipv4_conntype, "dynamic_ip")
        self.assertEqual(st.lan_macaddr, EUI48("02:00:00:00:00:02"))
        self.assertEqual(st.lan_ipv4_ipaddr, IPv4Address("198.51.100.1"))
        self.assertEqual(st.lan_ipv4_netmask, IPv4Address("255.255.255.0"))

    def test_enrich_status_from_wireless_get(self) -> None:
        status = Status()
        payload = {
            "error_code": 0,
            "result": {
                "band2_4": {"host": {"enable": True}, "guest": {"enable": False}},
                "band5_1": {"host": {"enable": 1}, "guest": {"enable": 0}},
            },
        }
        enrich_status_from_wireless_get(status, payload)
        self.assertIs(status.wifi_2g_enable, True)
        self.assertIs(status.guest_2g_enable, False)
        self.assertIs(status.wifi_5g_enable, True)
        self.assertIs(status.guest_5g_enable, False)

    def test_enrich_status_from_internet_get(self) -> None:
        status = Status()
        payload = {
            "error_code": 0,
            "result": {"dial_type": "pppoe", "wan_uptime": 1234},
        }
        enrich_status_from_internet_get(status, payload)
        self.assertEqual(status.conn_type, "pppoe")
        self.assertEqual(status.wan_ipv4_uptime, 1234)

    def test_enrich_status_from_internet_get_nested_ipv4_connect_type(self) -> None:
        status = Status()
        payload = {"error_code": 0, "result": {"ipv4": {"connect_type": "dynamic_ip"}}}
        enrich_status_from_internet_get(status, payload)
        self.assertIsNone(status.conn_type)


if __name__ == "__main__":
    unittest.main()
