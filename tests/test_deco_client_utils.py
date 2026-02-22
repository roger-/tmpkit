from __future__ import annotations

import unittest

from tmpkit.deco.client_utils import (
    client_rssi_level,
    client_signal_levels,
    client_signal_max,
    extract_signal_fields,
    is_connected_client,
    maybe_decode_name,
)


class TestDecoClientUtils(unittest.TestCase):
    def test_is_connected_client(self) -> None:
        self.assertTrue(is_connected_client({"online": True}))
        self.assertFalse(is_connected_client({"online": False}))
        self.assertTrue(is_connected_client({"status": "online"}))

    def test_maybe_decode_name(self) -> None:
        self.assertEqual(maybe_decode_name(""), "(unknown)")
        # "Device Alpha" base64
        self.assertEqual(maybe_decode_name("RGV2aWNlIEFscGhh"), "Device Alpha")

    def test_client_rssi_level_prefers_connected_band(self) -> None:
        client = {
            "online": True,
            "linked_device_info": {
                "connection_type": ["band2_4"],
                "signal_level": {"band2_4": 3, "band5": 0},
            },
        }
        self.assertEqual(client_rssi_level(client), "band2_4:3")

    def test_client_rssi_level_none_when_missing(self) -> None:
        self.assertIsNone(client_rssi_level({"online": True}))

    def test_client_signal_levels_and_max(self) -> None:
        client = {
            "online": True,
            "linked_device_info": {
                "connection_type": ["band2_4"],
                "signal_level": {"band2_4": 3, "band5": 0},
            },
        }
        self.assertEqual(client_signal_levels(client), {"band2_4": 3, "band5": 0})
        self.assertEqual(client_signal_max(client), 3)

    def test_client_signal_levels_accepts_strings(self) -> None:
        client = {
            "linked_device_info": {
                "signal_level": {"band2_4": "3", "band5": "0", "bad": "x"},
            }
        }
        self.assertEqual(client_signal_levels(client), {"band2_4": 3, "band5": 0})
        self.assertEqual(client_signal_max(client), 3)

    def test_extract_signal_fields(self) -> None:
        client = {
            "online": True,
            "linked_device_info": {
                "connection_type": ["band2_4"],
                "signal_level": {"band2_4": 3, "band5": 0},
            },
            "other": {"rssi": -55, "nested": [{"snr": 22}]},
        }
        fields = extract_signal_fields(client)
        self.assertIn("linked_device_info.connection_type", fields)
        self.assertIn("linked_device_info.signal_level", fields)
        self.assertIn("other.rssi", fields)
        self.assertIn("other.nested[0].snr", fields)

    def test_extract_signal_fields_non_dict(self) -> None:
        self.assertEqual(extract_signal_fields([1, 2, 3]), {})


if __name__ == "__main__":
    unittest.main()
