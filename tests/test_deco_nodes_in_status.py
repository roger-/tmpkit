from __future__ import annotations

import unittest

from ipaddress import IPv4Address
from macaddress import EUI48

from tmpkit.deco.status_adapter import node_devices_from_device_list_payload
from tmpkit.deco.models import Connection, Device, Status


class TestDecoNodesInStatus(unittest.TestCase):
    def test_node_devices_from_device_list_payload_slaves_only(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "device_list": [
                    {
                        "role": "master",
                        "ip": "198.51.100.29",
                        "mac": "02-00-00-00-10-01",
                        "custom_nickname": "TWFzdGVy",
                    },
                    {
                        "role": "slave",
                        "ip": "198.51.100.30",
                        "mac": "02-00-00-00-10-02",
                        "custom_nickname": "U2xhdmUx",
                    },
                    {
                        "role": "slave",
                        "ip": "198.51.100.28",
                        "mac": "02-00-00-00-10-03",
                        "custom_nickname": "U2xhdmUy",
                    },
                ]
            },
        }

        devs = node_devices_from_device_list_payload(payload, include_master=False)
        self.assertEqual(len(devs), 2)
        ips = {d.ipaddr for d in devs}
        self.assertEqual(
            ips, {IPv4Address("198.51.100.30"), IPv4Address("198.51.100.28")}
        )

        macs = {d.macaddr for d in devs}
        self.assertIn(EUI48("02:00:00:00:10:02"), macs)
        self.assertIn(EUI48("02:00:00:00:10:03"), macs)

    def test_node_type_from_connection_type(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "device_list": [
                    {
                        "role": "slave",
                        "ip": "198.51.100.30",
                        "mac": "02-00-00-00-10-02",
                        "connection_type": ["band5", "band2_4"],
                    },
                    {
                        "role": "slave",
                        "ip": "198.51.100.28",
                        "mac": "02-00-00-00-10-03",
                        "connection_type": ["band2_4"],
                    },
                ]
            },
        }
        devs = node_devices_from_device_list_payload(payload, include_master=False)
        types = {str(d.ipaddr): d.type for d in devs}
        self.assertEqual(types["198.51.100.30"], Connection.HOST_5G)
        self.assertEqual(types["198.51.100.28"], Connection.HOST_2G)

    def test_node_devices_include_master(self) -> None:
        payload = {
            "error_code": 0,
            "result": {
                "device_list": [
                    {
                        "role": "master",
                        "ip": "198.51.100.29",
                        "mac": "02-00-00-00-10-01",
                    },
                ]
            },
        }
        devs = node_devices_from_device_list_payload(payload, include_master=True)
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].ipaddr, IPv4Address("198.51.100.29"))

    def test_recompute_counts_includes_nodes(self) -> None:
        from tmpkit.deco.status_adapter import recompute_status_counts

        st = Status()
        st.devices = [
            Device(
                type=Connection.HOST_2G,
                macaddr=EUI48("02:00:00:00:30:01"),
                ipaddr=IPv4Address("198.51.100.10"),
                hostname="c1",
            ),
            Device(
                type=Connection.UNKNOWN,
                macaddr=EUI48("02:00:00:00:30:02"),
                ipaddr=IPv4Address("198.51.100.28"),
                hostname="node",
            ),
        ]
        recompute_status_counts(st)
        self.assertEqual(st.clients_total, 2)
        self.assertEqual(st.wifi_clients_total, 2)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
