from __future__ import annotations

import unittest

from ipaddress import IPv4Address
from macaddress import EUI48

from tmpkit.deco.device_adapter import (
    deco_client_to_device,
    deco_clients_to_devices,
    enrich_devices_with_client_list_speed,
)
from tmpkit.deco.models import Connection


class TestDecoDeviceAdapter(unittest.TestCase):
    def test_deco_client_to_device_basic(self) -> None:
        client = {
            "name": "RGV2aWNlIEFscGhh",  # Device Alpha
            "mac": "02-00-00-00-20-01",
            "ip": "198.51.100.70",
            "online": True,
            "packets_sent": 12,
            "packets_received": 34,
            "tx_rate": 144,
            "rx_rate": 72,
            "traffic_usage": 123456,
            "online_time": 10.5,
            "linked_device_info": {
                "connection_type": ["band2_4"],
                "signal_level": {"band2_4": 2, "band5": 0},
            },
        }
        dev = deco_client_to_device(client)
        assert dev is not None
        self.assertEqual(dev.hostname, "Device Alpha")
        self.assertEqual(dev.macaddr, EUI48("02:00:00:00:20:01"))
        self.assertEqual(dev.ipaddr, IPv4Address("198.51.100.70"))
        self.assertEqual(dev.type, Connection.HOST_2G)
        self.assertEqual(dev.signal, 2)
        self.assertTrue(dev.active)
        self.assertEqual(dev.packets_sent, 12)
        self.assertEqual(dev.packets_received, 34)
        self.assertEqual(dev.tx_rate, 144)
        self.assertEqual(dev.rx_rate, 72)
        self.assertEqual(dev.traffic_usage, 123456)
        self.assertAlmostEqual(dev.online_time or 0.0, 10.5)

    def test_deco_clients_to_devices_filters_non_dict(self) -> None:
        devices = deco_clients_to_devices([{"mac": "02-00-00-00-00-0a"}, 123])
        self.assertEqual(len(devices), 1)

    def test_enrich_devices_with_client_list_speed(self) -> None:
        client = {
            "name": "Device",
            "mac": "02-00-00-00-00-01",
            "ip": "198.51.100.10",
            "online": True,
            "linked_device_info": {
                "connection_type": ["band2_4"],
                "signal_level": {"band2_4": 1, "band5": 0},
            },
        }
        devices = deco_clients_to_devices([client])
        speed_payload = {
            "error_code": 0,
            "result": {
                "client_list_speed": [
                    {
                        "mac": "02-00-00-00-00-01",
                        "up_speed": 10,
                        "down_speed": 20,
                        "in_hnat": False,
                        "tx_rate": 300,
                        "rx_rate": 200,
                        "packets_sent": 7,
                        "packets_received": 9,
                        "traffic_usage": 555,
                        "online_time": 123,
                    }
                ]
            },
        }
        enrich_devices_with_client_list_speed(devices, speed_payload)
        self.assertEqual(devices[0].up_speed, 10)
        self.assertEqual(devices[0].down_speed, 20)
        self.assertEqual(devices[0].tx_rate, 300)
        self.assertEqual(devices[0].rx_rate, 200)
        self.assertEqual(devices[0].packets_sent, 7)
        self.assertEqual(devices[0].packets_received, 9)
        self.assertEqual(devices[0].traffic_usage, 555)
        self.assertEqual(devices[0].online_time, 123.0)


if __name__ == "__main__":
    unittest.main()
